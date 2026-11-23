#!/usr/bin/env python3
"""Journaled shared-extraction development runner. Real collection is locked pending review.

The scheduler accepts public data only. Tests inject a CPU backend; the Qwen
adapter below is real but the command-line collection gate is deliberately closed.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import time

import query_determinacy_extract_v2 as extract

LIVE_GATE = False
SCHEMA = 'shared_live_development_v1'
MAX_NEW_TOKENS = 512
ROOT = Path(__file__).resolve().parents[1]
MODEL = Path('/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct')
PILOT_PUBLIC = ROOT / 'docs/review/2026-11-18-two-case-cpu-v1/public.json'
MODEL_REFERENCE = ROOT / 'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json'
CONTRACT = ROOT / 'docs/review/2026-11-23-shared-live-preparation-v1/protocol.md'
SCORER = ROOT / 'scripts/query_determinacy_shared_score.py'


def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def hash_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_new(path, data):
    with path.open('xb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def validate_public(public):
    if set(public) != {'schema', 'cases'} or public['schema'] not in ('two_world_development_public_v1', 'two_world_development12_public_v1'):
        raise ValueError('public schema rejected')
    cases = public['cases']
    if not isinstance(cases, list) or not cases or len({c.get('id') for c in cases}) != len(cases):
        raise ValueError('case identities invalid')
    for c in cases:
        if set(c) != {'id', 'domain', 'background', 'questions'} or c['domain'] not in ('integer', 'identifier'):
            raise ValueError('case fields invalid or contain reference')
        if not all(isinstance(c[k], str) and c[k] for k in ('id', 'background')):
            raise ValueError('invalid case')
        qs = c['questions']
        if not isinstance(qs, list) or len(qs) != 3 or len({q.get('id') for q in qs}) != 3:
            raise ValueError('three distinct questions required')
        if any(set(q) != {'id', 'text'} or not all(isinstance(q[k], str) and q[k] for k in ('id', 'text')) for q in qs):
            raise ValueError('invalid question')
    return cases


def slots(public):
    out = []
    for c in validate_public(public):
        for q in c['questions']:
            out.append((c, q, 'direct', None))
        out.append((c, None, 'extract', None))
        for q in c['questions']:
            out.append((c, q, 'joint', None))
            out.extend((c, q, 'branch', i) for i in (0, 1))
    return out


def prompt(kind, case, question, values=None, branch=None):
    base = ('仅依据下面的材料和题设回答。不要用外部知识。材料中冲突来源同时保留；'
            '两种可能性由题设规定，不可自行排除。\n材料：\n' + case['background'])
    if kind == 'extract':
        return base + ('\n提取冲突来源针对同一字段的两个不同候选值。只输出JSON数组，'
                       '保留原始数字或代码，不输出解释。')
    base += '\n问题：' + question['text']
    world = '{"value":"候选值","answer":"Y或N","citations":["材料中的原文"]}'
    if kind == 'direct':
        task = '\n先从材料找出两个候选并逐一在假设该值成立时判断，比较两个答案。'
    elif kind == 'joint':
        task = '\n上一步抽取得到候选：' + json.dumps(values, ensure_ascii=False) + '。这些只是待检验的候选而非已确认事实；请分别假设每个候选成立后判断。'
    elif kind == 'branch':
        return (base + '\n上一步抽取得到一个待检验的候选：' + json.dumps(values[branch], ensure_ascii=False)
                + '。只在这个值成立的临时假设下回答；这不是已确认事实。'
                  '\n只输出一个JSON对象，格式为' + world + '。'
                  'citations逐字引用材料中与该值及判断相关的原文。')
    else:
        raise ValueError('unknown kind')
    return (base + task + '\n如果两支均为是，最终为Y；均为否，最终为N；一是一个否为U。'
            '只输出JSON对象：{"final":"Y或N或U","worlds":[' + world + ',' + world + ']}。'
            'citations逐字引用材料中支持各分支的原文。')


def init_run(run, public, extra=None):
    validate_public(public)
    if run.exists() or run.is_symlink():
        raise ValueError('run exists')
    run.mkdir(mode=0o700)
    for name in ('attempts', 'records', 'preflights'):
        (run / name).mkdir(mode=0o700)
    (run / 'run.lock').touch(mode=0o600, exist_ok=False)
    data = encode(public)
    write_new(run / 'public.json', data)
    manifest = {'schema': SCHEMA, 'public_sha256': sha(data), 'slots': len(slots(public)),
                'runner_sha256': hash_file(Path(__file__)), 'parser_sha256': hash_file(Path(extract.__file__)),
                'scorer_sha256': hash_file(SCORER), 'contract_sha256': hash_file(CONTRACT),
                'generation': {'max_new_tokens': MAX_NEW_TOKENS, 'do_sample': False}, 'extra': extra or {}}
    write_new(run / 'manifest.json', encode(manifest))
    return manifest


@contextmanager
def locked(run):
    if run.is_symlink() or not run.is_dir() or (run / 'run.lock').is_symlink() or not (run / 'run.lock').is_file():
        raise ValueError('invalid run or lock')
    with (run / 'run.lock').open('rb') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def load_run(run):
    if {p.name for p in run.iterdir()} != {'manifest.json', 'public.json', 'run.lock', 'attempts', 'records', 'preflights'}:
        raise ValueError('unexpected run files')
    for name in ('manifest.json', 'public.json', 'attempts', 'records', 'preflights'):
        if (run / name).is_symlink():
            raise ValueError('symlink rejected')
    manifest = json.loads((run / 'manifest.json').read_bytes())
    raw = (run / 'public.json').read_bytes()
    public = json.loads(raw)
    if (manifest.get('schema') != SCHEMA or manifest.get('public_sha256') != sha(raw)
            or manifest.get('runner_sha256') != hash_file(Path(__file__))
            or manifest.get('parser_sha256') != hash_file(Path(extract.__file__))
            or manifest.get('scorer_sha256') != hash_file(SCORER)
            or manifest.get('contract_sha256') != hash_file(CONTRACT)
            or manifest.get('slots') != len(slots(public))):
        raise ValueError('manifest, public input or implementation changed')
    return manifest, public


def replay(run):
    manifest, public = load_run(run)
    sequence = slots(public)
    attempts, records = sorted((run/'attempts').iterdir()), sorted((run/'records').iterdir())
    if len(attempts) != len(records) or len(records) > len(sequence):
        raise ValueError('unfinished or extra attempt; preserve and stop')
    extracted, prior, technical_failure = {}, [], False
    manifest_hash = hash_file(run/'manifest.json')
    for i, (ap, rp) in enumerate(zip(attempts, records)):
        name = f'{i:04d}.json'
        if ap.name != name or rp.name != name or ap.is_symlink() or rp.is_symlink():
            raise ValueError('journal prefix invalid')
        case, question, kind, branch = sequence[i]
        parsed = extracted.get(case['id'])
        skip = kind in ('joint', 'branch') and (not parsed or parsed['status'] != 'parsed')
        values = parsed['values'] if not skip and parsed else None
        rendered = None if skip else prompt(kind, case, question, values, branch)
        attempt = json.loads(ap.read_bytes())
        expected = {'index': i, 'case': case['id'], 'question': question['id'] if question else None,
                    'kind': kind, 'branch': branch, 'prompt': rendered,
                    'prompt_sha256': sha(rendered.encode()) if rendered else None,
                    'manifest_sha256': manifest_hash}
        if attempt != expected:
            raise ValueError('attempt changed or candidate dependency mismatch')
        record = json.loads(rp.read_bytes())
        if record.get('index') != i or record.get('attempt_sha256') != hash_file(ap):
            raise ValueError('record binding mismatch')
        status = record.get('status')
        if status not in ('complete', 'truncated', 'empty', 'technical_failure', 'skipped_extract'):
            raise ValueError('invalid status')
        if skip != (status == 'skipped_extract'):
            raise ValueError('invalid skipped slot')
        if status == 'complete' and (not isinstance(record.get('output'), str) or not record['output'].strip()):
            raise ValueError('invalid complete output')
        if record.get('output_sha256') != sha(record.get('output', '').encode()):
            raise ValueError('record output hash mismatch')
        for token_field in ('input_token_ids', 'generated_token_ids'):
            if token_field in record and record.get(token_field + '_sha256') != sha(encode(record[token_field])):
                raise ValueError('record token hash mismatch')
        if kind == 'extract':
            extracted[case['id']] = extract.parse(record.get('output', ''), case['domain'], status == 'complete')
        if status in ('truncated', 'empty', 'technical_failure'):
            technical_failure = True
        prior.append({'attempt': attempt, 'record': record})
    return {'manifest': manifest, 'public': public, 'entries': prior, 'extracted': extracted,
            'blocked': technical_failure, 'count': len(prior), 'total': len(sequence)}


def collect(run, backend=None, preflight=None, backend_factory=None):
    """Run or resume a complete prefix; unfinished attempts and technical failures block."""
    with locked(run):
        state = replay(run)
        if state['blocked']:
            raise ValueError('technical failure preserved; manual audit required')
        sequence = slots(state['public'])
        if preflight is not None:
            preflight(state)
        if state['count'] == state['total']:
            return state
        if backend_factory is not None:
            backend = backend_factory()
        if backend is None:
            raise ValueError('backend missing')
        for i in range(state['count'], len(sequence)):
            case, question, kind, branch = sequence[i]
            parsed = state['extracted'].get(case['id'])
            skip = kind in ('joint', 'branch') and (not parsed or parsed['status'] != 'parsed')
            values = parsed['values'] if not skip and parsed else None
            rendered = None if skip else prompt(kind, case, question, values, branch)
            attempt = {'index': i, 'case': case['id'], 'question': question['id'] if question else None,
                       'kind': kind, 'branch': branch, 'prompt': rendered,
                       'prompt_sha256': sha(rendered.encode()) if rendered else None,
                       'manifest_sha256': hash_file(run/'manifest.json')}
            ap, rp = run/'attempts'/f'{i:04d}.json', run/'records'/f'{i:04d}.json'
            write_new(ap, encode(attempt))
            start = time.monotonic()
            if skip:
                result = {'status': 'skipped_extract', 'output': '', 'input_tokens': None, 'output_tokens': None}
            else:
                try:
                    result = backend(rendered, attempt)
                    if (not isinstance(result, dict) or result.get('status') not in ('complete', 'truncated', 'empty', 'technical_failure')
                            or not isinstance(result.get('output'), str)):
                        raise ValueError('backend returned invalid envelope')
                    if result['status'] == 'complete' and not result['output'].strip():
                        result['status'] = 'empty'
                except Exception as error:
                    result = {'status': 'technical_failure', 'output': '', 'input_tokens': None, 'output_tokens': None,
                              'error': type(error).__name__ + ': ' + str(error)}
            record = dict(result, index=i, attempt_sha256=hash_file(ap), elapsed_seconds=time.monotonic()-start,
                          completed_at=datetime.now(timezone.utc).isoformat())
            record['output_sha256'] = sha(record['output'].encode())
            for token_field in ('input_token_ids', 'generated_token_ids'):
                if token_field in record:
                    record[token_field + '_sha256'] = sha(encode(record[token_field]))
            write_new(rp, encode(record))
            if kind == 'extract':
                state['extracted'][case['id']] = extract.parse(record['output'], case['domain'], record['status'] == 'complete')
            if result['status'] in ('truncated', 'empty', 'technical_failure'):
                raise ValueError('technical failure preserved; manual audit required')
        return replay(run)


class QwenBackend:
    """User-executed adapter; construction accesses CUDA and requires prior device review."""
    def __init__(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(str(MODEL), local_files_only=True,
                      dtype=torch.bfloat16, device_map={'': 0}, attn_implementation='sdpa').eval()
        self.model.requires_grad_(False)
        eos = self.model.generation_config.eos_token_id
        self.eos = eos if isinstance(eos, list) else [eos]
        self.cfg = GenerationConfig(max_new_tokens=MAX_NEW_TOKENS, do_sample=False, num_beams=1, use_cache=True,
                                    eos_token_id=self.eos, bos_token_id=self.model.generation_config.bos_token_id,
                                    pad_token_id=self.tok.pad_token_id if self.tok.pad_token_id is not None else self.tok.eos_token_id)

    def __call__(self, text, _attempt):
        torch = self.torch
        rendered = self.tok.apply_chat_template([{'role': 'user', 'content': text}], tokenize=False, add_generation_prompt=True)
        ids = self.tok(rendered, add_special_tokens=False, truncation=False)['input_ids']
        if len(ids) + MAX_NEW_TOKENS > self.model.config.max_position_embeddings:
            raise ValueError('context limit exceeded')
        tensors = torch.tensor([ids], dtype=torch.long, device='cuda:0')
        torch.cuda.synchronize()
        with torch.inference_mode():
            output = self.model.generate(input_ids=tensors, attention_mask=torch.ones_like(tensors),
                                         generation_config=self.cfg, logits_to_keep=1)
        torch.cuda.synchronize()
        if output.ndim != 2 or output.shape[0] != 1 or output[0, :len(ids)].tolist() != ids:
            raise ValueError('output prefix mismatch')
        generated = output[0, len(ids):].tolist()
        raw = self.tok.decode(generated, skip_special_tokens=True)
        status = 'empty' if not raw.strip() else 'complete' if generated and generated[-1] in self.eos else 'truncated'
        return {'status': status, 'output': raw, 'input_tokens': len(ids), 'output_tokens': len(generated),
                'rendered_prompt': rendered, 'input_token_ids': ids, 'generated_token_ids': generated}


def environment_snapshot():
    """Hash locally pinned model files; CPU only, never reads answer references."""
    raw = MODEL_REFERENCE.read_bytes()
    snapshot = json.loads(raw)
    if Path(snapshot['model']) != MODEL:
        raise ValueError('model reference mismatch')
    expected = snapshot['model_files_sha256']
    actual = {name: hash_file(MODEL/name) for name in expected}
    if actual != expected:
        raise ValueError('model files changed')
    return {'model': str(MODEL), 'model_reference_sha256': sha(raw), 'model_files_sha256': actual,
            'versions': {x: importlib.metadata.version(x) for x in ('torch', 'transformers')},
            'context_tokens': snapshot['context_tokens']}


def verify_device():
    if os.environ.get('CUDA_VISIBLE_DEVICES', '0') != '0':
        raise ValueError('only physical GPU 0 is permitted by this candidate configuration')
    info = subprocess.run(['nvidia-smi', '-i', '0', '--query-gpu=uuid,name,memory.total,memory.used',
                           '--format=csv,noheader'], text=True, capture_output=True, check=True).stdout.strip()
    processes = subprocess.run(['nvidia-smi', '-i', '0', '--query-compute-apps=pid,process_name,used_memory',
                                '--format=csv,noheader'], text=True, capture_output=True, check=True).stdout.strip()
    if not info or processes:
        raise ValueError('GPU not identifiable or has active compute processes')
    import torch
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1 or not torch.cuda.is_bf16_supported():
        raise ValueError('one visible CUDA device with bfloat16 required')
    return {'nvidia_smi_gpu': info, 'compute_processes': processes,
            'torch_cuda': torch.version.cuda, 'device_name': torch.cuda.get_device_name(0),
            'visible_device_count': torch.cuda.device_count()}


def require_live_gate():
    if not LIVE_GATE:
        raise ValueError('real collection gate closed; review and release required')


def prepare_live(run):
    require_live_gate()
    raw = PILOT_PUBLIC.read_bytes()
    public = json.loads(raw)
    if len(validate_public(public)) != 2:
        raise ValueError('only two-case engineering pilot is permitted')
    env = environment_snapshot()
    return init_run(run, public, {'mode': 'user_gpu_pilot_only', 'source_public_sha256': sha(raw), 'environment': env})


def collect_live(run):
    require_live_gate()
    def preflight(state):
        extra = state['manifest']['extra']
        if extra.get('mode') != 'user_gpu_pilot_only' or extra.get('source_public_sha256') != hash_file(PILOT_PUBLIC):
            raise ValueError('pilot release binding mismatch')
        if extra.get('environment') != environment_snapshot():
            raise ValueError('runtime environment changed')
        if state['count'] < state['total']:
            device = verify_device()
            directory = run / 'preflights'
            existing = sorted(directory.iterdir())
            if any(p.is_symlink() or p.name != f'{i:04d}.json' for i, p in enumerate(existing)):
                raise ValueError('invalid device preflight journal')
            write_new(directory / f'{len(existing):04d}.json', encode({
                'device': device, 'checked_at': datetime.now(timezone.utc).isoformat(),
                'starting_slot': state['count'], 'manifest_sha256': hash_file(run/'manifest.json')}))
    # Hold the run lock across preflight, loading, and every scheduled call.
    return collect(run, preflight=preflight, backend_factory=QwenBackend)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('inspect', 'prepare', 'collect'))
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    if args.stage in ('prepare', 'collect'):
        # Gate is code-closed before model, device, run creation or mutation.
        if not LIVE_GATE:
            raise SystemExit('STOP: real collection gate closed; review and release required')
        result = prepare_live(args.run) if args.stage == 'prepare' else collect_live(args.run)
        print(json.dumps({'state': 'prepared' if args.stage == 'prepare' else 'complete',
                          'count': result.get('count', 0)}, ensure_ascii=False))
        return
    with locked(args.run):
        state = replay(args.run)
    print(json.dumps({'count': state['count'], 'total': state['total'], 'blocked': state['blocked']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
