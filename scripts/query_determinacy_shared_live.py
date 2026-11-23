#!/usr/bin/env python3
"""Journaled shared-extraction runner for a released two-case user GPU pilot."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import query_determinacy_extract_v2 as extract

SCHEMA = 'shared_live_development_v1'
MAX_NEW_TOKENS = 512
ROOT = Path(__file__).resolve().parents[1]
MODEL = Path('/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct')
PILOT_PUBLIC = ROOT / 'docs/review/2026-11-18-two-case-cpu-v1/public.json'
MODEL_REFERENCE = ROOT / 'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json'
CONTRACT = ROOT / 'docs/review/2026-11-23-shared-live-preparation-v1/protocol.md'
SCORER = ROOT / 'scripts/query_determinacy_shared_score.py'
RELEASE = ROOT / 'docs/review/2026-11-23-shared-pilot-release-v1/release.json'
PILOT_RUN = ROOT / 'runs/qwen2.5-3b-query-determinacy-shared-pilot-v1'
PILOT_CASES = ['D7M4', 'N3K6']
PILOT_SLOTS = 26
PILOT_MODE = 'user_gpu_pilot_only'
GENERATION = {'max_new_tokens': MAX_NEW_TOKENS, 'do_sample': False, 'num_beams': 1,
              'device': 'cuda:0', 'dtype': 'bfloat16', 'attention': 'sdpa', 'use_cache': True,
              'logits_to_keep': 1}


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
    world = '{"value":"候选值","answer":"填写单个字母","citations":["材料中的原文"]}'
    citation_rule = ('每支answer只能填Y或N，value必须是字符串。citations逐字复制该值对应的完整来源句（含来源名和句号）；'
                     '如有规则表，另复制该代码对应的整条规则，从代码开始，保留内部标点，不包含分隔符或末尾句号。')
    if kind == 'direct':
        task = '\n先从材料找出两个候选并逐一在假设该值成立时判断，比较两个答案。'
    elif kind == 'joint':
        task = '\n上一步抽取得到候选：' + json.dumps(values, ensure_ascii=False) + '。这些只是待检验的候选而非已确认事实；请分别假设每个候选成立后判断。'
    elif kind == 'branch':
        return (base + '\n上一步抽取得到一个待检验的候选：' + json.dumps(values[branch], ensure_ascii=False)
                + '。只在这个值成立的临时假设下回答；这不是已确认事实。'
                  '\n只输出一个JSON对象，结构示例：' + world + '。' + citation_rule)
    else:
        raise ValueError('unknown kind')
    return (base + task + '\n如果两支均为是，最终填Y；均为否填N；一是一个否填U。'
            '只输出JSON对象，结构示例：{"final":"填写单个字母","worlds":[' + world + ',' + world + ']}。'
            + citation_rule)


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
                'generation': GENERATION, 'extra': extra or {}}
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
            or manifest.get('generation') != GENERATION
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
    real = manifest['extra'].get('mode') == PILOT_MODE
    tokenizer = None
    if real:
        validate_pilot_binding(run, manifest, public)
        if records:
            tokenizer = load_tokenizer()
        check_preflights(run, manifest_hash, len(records))
    for i, (ap, rp) in enumerate(zip(attempts, records)):
        if technical_failure:
            raise ValueError('record follows a terminal technical failure')
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
        seconds = record.get('elapsed_seconds')
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('invalid call duration')
        for token_field in ('input_token_ids', 'generated_token_ids'):
            if token_field in record and record.get(token_field + '_sha256') != sha(encode(record[token_field])):
                raise ValueError('record token hash mismatch')
        if real and status in ('complete', 'empty', 'truncated'):
            verify_tokens(tokenizer, rendered, record, manifest['extra']['environment'])
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
            if state['manifest']['extra'].get('mode') == PILOT_MODE:
                print(f'{i + 1}/{len(sequence)} {case["id"]} {kind}: {record["status"]}', flush=True)
            if kind == 'extract':
                state['extracted'][case['id']] = extract.parse(record['output'], case['domain'], record['status'] == 'complete')
            if result['status'] in ('truncated', 'empty', 'technical_failure'):
                raise ValueError('technical failure preserved; manual audit required')
        return replay(run)


def load_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True)


def tokenize(tokenizer, text):
    rendered = tokenizer.apply_chat_template([{'role': 'user', 'content': text}], tokenize=False,
                                             add_generation_prompt=True)
    return rendered, tokenizer(rendered, add_special_tokens=False, truncation=False)['input_ids']


def output_status(raw, generated, eos):
    if not raw.strip():
        return 'empty'
    return 'complete' if generated and generated[-1] in eos else 'truncated'


def verify_tokens(tokenizer, prompt_text, record, environment):
    rendered, ids = tokenize(tokenizer, prompt_text)
    generated = record.get('generated_token_ids')
    eos = environment['eos_token_ids']
    if (record.get('rendered_prompt') != rendered or record.get('input_token_ids') != ids
            or record.get('input_tokens') != len(ids) or len(ids) + MAX_NEW_TOKENS > environment['context_tokens']
            or not isinstance(generated, list) or len(generated) > MAX_NEW_TOKENS
            or any(type(t) is not int or not 0 <= t < len(tokenizer) for t in generated)
            or any(t in eos for t in generated[:-1]) or record.get('output_tokens') != len(generated)):
        raise ValueError('real journal token or prompt mismatch')
    raw = tokenizer.decode(generated, skip_special_tokens=True)
    if record['output'] != raw or record['status'] != output_status(raw, generated, eos):
        raise ValueError('real journal decoded output or EOS mismatch')


class QwenBackend:
    """User-executed adapter; construction accesses CUDA and requires prior device review."""
    def __init__(self):
        import torch
        from transformers import AutoModelForCausalLM, GenerationConfig
        self.torch = torch
        self.tok = load_tokenizer()
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
        rendered, ids = tokenize(self.tok, text)
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
        status = output_status(raw, generated, self.eos)
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
    versions = {x: importlib.metadata.version(x) for x in ('torch', 'transformers', 'accelerate', 'tokenizers', 'safetensors')}
    if any(versions[x] != snapshot['runtime_versions'][x] for x in ('torch', 'transformers')):
        raise ValueError('use the pinned kba-rag runtime')
    eos = json.loads((MODEL / 'generation_config.json').read_bytes())['eos_token_id']
    eos = eos if isinstance(eos, list) else [eos]
    if eos != snapshot['eos_token_ids']:
        raise ValueError('EOS configuration differs from pinned model snapshot')
    return {'model': str(MODEL), 'model_reference_sha256': sha(raw), 'model_files_sha256': actual,
            'versions': versions, 'context_tokens': snapshot['context_tokens'], 'eos_token_ids': eos}


def verify_device():
    info = subprocess.run(['nvidia-smi', '-i', '0', '--query-gpu=uuid,name,memory.free',
                           '--format=csv,noheader,nounits'], text=True, capture_output=True, check=True,
                          timeout=15).stdout.strip()
    uuid, name, free = (field.strip() for field in info.split(','))
    if not uuid.startswith('GPU-') or int(free) < 10 * 1024:
        raise ValueError('GPU 0 needs at least 10 GiB free VRAM for the engineering pilot')
    processes = subprocess.run(['nvidia-smi', '-i', uuid, '--query-compute-apps=pid,process_name,used_memory',
                                '--format=csv,noheader'], text=True, capture_output=True, check=True,
                               timeout=15).stdout.strip()
    if processes:
        raise ValueError('GPU 0 has active compute processes')
    os.environ['CUDA_VISIBLE_DEVICES'] = uuid
    import torch
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1 or not torch.cuda.is_bf16_supported():
        raise ValueError('one visible CUDA device with bfloat16 required')
    return {'gpu_uuid': uuid, 'gpu_name': name, 'free_mib': int(free),
            'torch_cuda': torch.version.cuda, 'device_name': torch.cuda.get_device_name(0),
            'visible_device_count': torch.cuda.device_count()}


def pilot_files():
    paths = (PILOT_PUBLIC, Path(__file__).resolve(), Path(extract.__file__).resolve(), SCORER, CONTRACT,
             MODEL_REFERENCE, ROOT / 'shared_pilot.sh')
    return {str(p.relative_to(ROOT)): hash_file(p) for p in paths}


def read_pilot_release(run):
    if run.absolute() != PILOT_RUN or run.is_symlink() or run.parent.resolve() != PILOT_RUN.parent:
        raise ValueError('use the fixed two-case pilot run directory')
    if not RELEASE.is_file() or RELEASE.is_symlink():
        raise ValueError('two-case release missing')
    raw = RELEASE.read_bytes()
    release = json.loads(raw)
    if (release.get('schema') != 'shared_live_pilot_release_v1' or release.get('collection_allowed') is not True
            or release.get('executor') != 'user' or release.get('case_ids') != PILOT_CASES
            or release.get('slots') != PILOT_SLOTS or release.get('files_sha256') != pilot_files()):
        raise ValueError('two-case release or frozen inputs changed')
    return release, sha(raw)


def validate_pilot_binding(run, manifest, public):
    release, digest = read_pilot_release(run)
    if ([c['id'] for c in public['cases']] != PILOT_CASES or public != json.loads(PILOT_PUBLIC.read_bytes())
            or manifest['slots'] != PILOT_SLOTS
            or manifest['extra'] != {'mode': PILOT_MODE, 'release_sha256': digest,
                                     'environment': release['environment']}):
        raise ValueError('pilot release binding mismatch')
    return release


def check_preflights(run, manifest_hash, records):
    entries = sorted((run / 'preflights').iterdir())
    if records and not entries:
        raise ValueError('device preflight missing')
    starts = []
    for index, path in enumerate(entries):
        if path.is_symlink() or path.name != f'{index:04d}.json':
            raise ValueError('invalid device preflight journal')
        data = json.loads(path.read_bytes())
        start = data.get('starting_slot')
        if (data.get('manifest_sha256') != manifest_hash or type(start) is not int
                or not 0 <= start <= records or (starts and start < starts[-1])):
            raise ValueError('invalid device preflight binding')
        starts.append(start)
    if starts and starts[0] != 0:
        raise ValueError('initial device preflight missing')
    return len(entries)


def prepare_live(run):
    release, digest = read_pilot_release(run)
    public = json.loads(PILOT_PUBLIC.read_bytes())
    if [c['id'] for c in validate_public(public)] != PILOT_CASES or len(slots(public)) != PILOT_SLOTS:
        raise ValueError('only the released two-case schedule is permitted')
    return init_run(run, public, {'mode': PILOT_MODE, 'release_sha256': digest, 'environment': release['environment']})


def collect_live(run):
    def preflight(state):
        release = validate_pilot_binding(run, state['manifest'], state['public'])
        if state['count'] < state['total']:
            if release['environment'] != environment_snapshot():
                raise ValueError('runtime environment changed')
            device = verify_device()
            manifest_hash = hash_file(run/'manifest.json')
            index = check_preflights(run, manifest_hash, state['count'])
            write_new(run / 'preflights' / f'{index:04d}.json', encode({
                'device': device, 'checked_at': datetime.now(timezone.utc).isoformat(),
                'starting_slot': state['count'], 'manifest_sha256': manifest_hash}))
    # Hold the run lock across preflight, loading, and every scheduled call.
    return collect(run, preflight=preflight, backend_factory=QwenBackend)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('inspect', 'prepare', 'collect'))
    parser.add_argument('run', type=Path)
    parser.add_argument('--user-executed', action='store_true')
    args = parser.parse_args()
    try:
        if args.stage != 'inspect':
            if not args.user_executed:
                raise ValueError('GPU pilot requires --user-executed')
            read_pilot_release(args.run)
            if args.stage == 'prepare':
                prepare_live(args.run)
                print(f'Prepared {PILOT_SLOTS} slots.', flush=True)
                return
            state = collect_live(args.run)
        else:
            with locked(args.run):
                state = replay(args.run)
        print(json.dumps({'count': state['count'], 'total': state['total'], 'blocked': state['blocked']},
                         ensure_ascii=False))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'STOP: {error}. Keep the run directory and report the error.', file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == '__main__':
    main()
