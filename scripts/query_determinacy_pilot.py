#!/usr/bin/env python3
"""CPU preparation and user-executed, journaled GPU collection for the pilot."""
import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

import query_determinacy_material_audit as audit

ROOT = Path(__file__).resolve().parents[1]
MODEL = Path('/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct')
RUN = ROOT / 'runs/qwen2.5-3b-query-determinacy-pilot-v1'
REFERENCE = ROOT / 'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/relation-reference-snapshot.json'
ARCHIVE = ROOT / 'docs/review/2026-11-12-query-determinacy-pilot-v1/manifest.json'
IMPLEMENTATION = (Path(__file__).resolve(), Path(audit.__file__).resolve())
SEED = 42


def digest(value):
    return hashlib.sha256(value).hexdigest()


def file_hash(path):
    value = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(4 * 1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def ids_hash(ids):
    return digest(json.dumps(ids, ensure_ascii=False, separators=(',', ':')).encode())


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def write_new(path, value):
    data = canonical(value)
    with path.open('xb') as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


@contextmanager
def locked():
    if RUN.is_symlink() or not RUN.is_dir():
        raise ValueError('run directory missing or symlink')
    if (RUN / 'run.lock').is_symlink() or not (RUN / 'run.lock').is_file():
        raise ValueError('run lock missing or symlink')
    with (RUN / 'run.lock').open('a+b') as file:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(file, fcntl.LOCK_UN)


def inputs():
    with (audit.MATERIAL / 'prompts.jsonl').open(encoding='utf-8') as file:
        return {r['id']: r['prompt'] for r in map(json.loads, file)}


def ordered_ids():
    with (audit.MATERIAL / 'key.csv').open(encoding='utf-8-sig', newline='') as file:
        rows = list(csv.DictReader(file))
    rng = random.Random(SEED)
    rng.shuffle(rows)
    smoke_rules = (
        lambda r: r['任务族'] == '数值比较' and r['材料形式'] == '来源断言' and r['参考结论'] != '无法唯一确定',
        lambda r: r['任务族'] == '类别规则' and r['材料形式'] == '分列候选' and r['参考结论'] == '无法唯一确定',
        lambda r: r['任务族'] == '数值比较' and r['材料形式'] == '单来源假设',
        lambda r: r['任务族'] == '类别规则' and r['材料形式'] == '单来源假设',
    )
    smoke = [next(row['id'] for row in rows if rule(row)) for rule in smoke_rules]
    if len(set(smoke)) != 4:
        raise ValueError('smoke selection is not unique')
    return smoke + [row['id'] for row in rows if row['id'] not in smoke]


def tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(str(MODEL), local_files_only=True)


def render(tokenizer, prompt):
    text = tokenizer.apply_chat_template([{'role': 'user', 'content': prompt}], tokenize=False,
                                         add_generation_prompt=True)
    ids = tokenizer(text, add_special_tokens=False, truncation=False)['input_ids']
    return text, ids


def versions():
    return {name: importlib.metadata.version(name) for name in ('torch', 'transformers')}


def build_manifest():
    material = audit.audit()
    reference = json.loads(REFERENCE.read_text(encoding='utf-8'))
    if Path(reference['model']) != MODEL:
        raise ValueError('unexpected model reference')
    expected_files = reference['model_files_sha256']
    current_files = {name: file_hash(MODEL / name) for name in expected_files}
    if current_files != expected_files:
        raise ValueError('model file fingerprints differ from stored reference')
    tok = tokenizer()
    data = inputs()
    order = ordered_ids()
    if len(order) != 144 or set(order) != set(data):
        raise ValueError('run list mismatch')
    eos = json.loads((MODEL / 'generation_config.json').read_text())['eos_token_id']
    eos = eos if isinstance(eos, list) else [eos]
    details = []
    for item in order:
        prompt = data[item]
        text, ids = render(tok, prompt)
        if len(ids) + 128 > reference['context_tokens']:
            raise ValueError('prompt exceeds context budget')
        details.append({'id': item, 'prompt_sha256': digest(prompt.encode()),
                        'rendered_sha256': digest(text.encode()), 'token_ids_sha256': ids_hash(ids),
                        'input_tokens': len(ids)})
    return {'schema': 'query_determinacy_pilot_v1', 'materials_sha256': material['files_sha256'],
            'reference_sha256': file_hash(REFERENCE),
            'implementation_sha256': {str(p.relative_to(ROOT)): file_hash(p) for p in IMPLEMENTATION},
            'model': str(MODEL), 'model_files_sha256': current_files, 'versions': versions(),
            'seed': SEED, 'smoke_count': 4, 'count': len(details), 'items': details,
            'chat': 'native Qwen chat template, user prompt only, add_generation_prompt=True, no extra special tokens',
            'generation': {'max_new_tokens': 128, 'do_sample': False, 'num_beams': 1,
                           'use_cache': True, 'dtype': 'bfloat16', 'attention': 'sdpa',
                           'eos_token_ids': eos},
            'semantic_review_completed': False}


def validate_files(manifest, include_weights=False):
    if manifest['versions'] != versions():
        raise ValueError('runtime versions changed')
    for name, expected in manifest['materials_sha256'].items():
        if file_hash(audit.MATERIAL / name) != expected:
            raise ValueError('material fingerprint changed')
    if file_hash(REFERENCE) != manifest['reference_sha256']:
        raise ValueError('model reference fingerprint changed')
    for name, expected in manifest['implementation_sha256'].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError('implementation changed')
    for name, expected in manifest['model_files_sha256'].items():
        if include_weights or not name.endswith('.safetensors'):
            if file_hash(MODEL / name) != expected:
                raise ValueError('model file fingerprint changed: ' + name)


def read_state(manifest, tok, data):
    allowed = {'manifest.json', 'run.lock', 'attempts', 'records'}
    if {x.name for x in RUN.iterdir()} != allowed:
        raise ValueError('unexpected run directory files')
    for name in ('attempts', 'records'):
        if (RUN / name).is_symlink() or not (RUN / name).is_dir():
            raise ValueError('invalid journal directory')
    attempts = sorted((RUN / 'attempts').iterdir())
    records = sorted((RUN / 'records').iterdir())
    if len(attempts) != len(records):
        raise ValueError('unfinished attempt: preserve journal and stop')
    if len(records) > manifest['count']:
        raise ValueError('unexpected extra records')
    for i, (attempt_path, record_path) in enumerate(zip(attempts, records)):
        expected_name = f'{i:03d}.json'
        if attempt_path.name != expected_name or record_path.name != expected_name or attempt_path.is_symlink() or record_path.is_symlink():
            raise ValueError('journal is not a regular ordered prefix')
        item = manifest['items'][i]
        attempt = json.loads(attempt_path.read_text())
        record = json.loads(record_path.read_text())
        text, ids = render(tok, data[item['id']])
        if (digest(data[item['id']].encode()) != item['prompt_sha256'] or digest(text.encode()) != item['rendered_sha256']
                or ids_hash(ids) != item['token_ids_sha256'] or len(ids) != item['input_tokens']):
            raise ValueError('rendered prompt changed')
        if attempt != {'index': i, 'id': item['id'], 'manifest_sha256': file_hash(RUN / 'manifest.json')}:
            raise ValueError('attempt binding mismatch')
        tokens = record.get('generated_token_ids')
        if not isinstance(tokens, list) or not 1 <= len(tokens) <= 128 or any(type(t) is not int or t < 0 or t >= len(tok) for t in tokens):
            raise ValueError('invalid generated tokens')
        raw = tok.decode(tokens, skip_special_tokens=True)
        eos = manifest['generation']['eos_token_ids']
        if any(t in eos for t in tokens[:-1]):
            raise ValueError('tokens after EOS')
        if (record.get('index') != i or record.get('id') != item['id'] or record.get('attempt_sha256') != file_hash(attempt_path)
                or record.get('output') != raw or record.get('generated_token_ids_sha256') != ids_hash(tokens)):
            raise ValueError('record binding or token decoding mismatch')
        if not raw.strip() or tokens[-1] not in eos:
            raise ValueError('empty or truncated output: preserve journal and stop')
    return {'records': len(records), 'attempts': len(attempts), 'total': manifest['count'],
            'state': 'complete_unreviewed' if len(records) == manifest['count'] else 'valid_prefix',
            'semantic_review_completed': False}


def prepare():
    manifest = build_manifest()
    if RUN.exists() or RUN.is_symlink():
        raise ValueError('run directory exists; use inspect, never overwrite')
    RUN.mkdir(mode=0o700)
    (RUN / 'attempts').mkdir(mode=0o700)
    (RUN / 'records').mkdir(mode=0o700)
    (RUN / 'run.lock').touch(mode=0o600, exist_ok=False)
    write_new(RUN / 'manifest.json', manifest)
    return {'state': 'prepared_not_started', 'count': manifest['count'], 'smoke_count': 4,
            'min_input_tokens': min(x['input_tokens'] for x in manifest['items']),
            'max_input_tokens': max(x['input_tokens'] for x in manifest['items']),
            'manifest_sha256': file_hash(RUN / 'manifest.json'), 'run_directory': str(RUN)}


def load_manifest():
    path = RUN / 'manifest.json'
    if path.is_symlink() or not ARCHIVE.is_file() or ARCHIVE.is_symlink() or path.read_bytes() != ARCHIVE.read_bytes():
        raise ValueError('run manifest differs from frozen archive')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest.get('schema') != 'query_determinacy_pilot_v1' or manifest.get('count') != 144 or len(manifest.get('items', [])) != 144:
        raise ValueError('invalid manifest')
    return manifest


def verify_device():
    gpu = os.environ.get('CUDA_VISIBLE_DEVICES', '0')
    result = subprocess.run(['nvidia-smi', '-i', gpu, '--query-compute-apps=pid,process_name,used_memory',
                             '--format=csv,noheader'], text=True, capture_output=True, check=True)
    if result.stdout.strip():
        raise ValueError('GPU has active compute processes')
    import torch
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1 or not torch.cuda.is_bf16_supported():
        raise ValueError('one visible CUDA GPU with bfloat16 support required')


def collect(manifest, tok, data):
    validate_files(manifest, include_weights=True)
    state = read_state(manifest, tok, data)
    if state['state'] == 'complete_unreviewed':
        return state
    verify_device()
    import torch
    from transformers import AutoModelForCausalLM, GenerationConfig
    model = AutoModelForCausalLM.from_pretrained(str(MODEL), local_files_only=True, dtype=torch.bfloat16,
                                                device_map={'': 0}, attn_implementation='sdpa').eval()
    model.requires_grad_(False)
    cfg = GenerationConfig(max_new_tokens=128, do_sample=False, num_beams=1, use_cache=True,
                           eos_token_id=manifest['generation']['eos_token_ids'],
                           bos_token_id=model.generation_config.bos_token_id,
                           pad_token_id=tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id)
    for i in range(state['records'], manifest['count']):
        item = manifest['items'][i]
        _, ids = render(tok, data[item['id']])
        if ids_hash(ids) != item['token_ids_sha256']:
            raise ValueError('input changed before generation')
        attempt_path = RUN / 'attempts' / f'{i:03d}.json'
        write_new(attempt_path, {'index': i, 'id': item['id'], 'manifest_sha256': file_hash(RUN / 'manifest.json')})
        input_ids = torch.tensor([ids], dtype=torch.long, device='cuda:0')
        started = time.monotonic()
        torch.cuda.synchronize()
        with torch.inference_mode():
            output = model.generate(input_ids=input_ids, attention_mask=torch.ones_like(input_ids),
                                    generation_config=cfg, logits_to_keep=1)
        torch.cuda.synchronize()
        elapsed = time.monotonic() - started
        if output.ndim != 2 or output.shape[0] != 1 or output[0, :len(ids)].tolist() != ids:
            raise ValueError('invalid generation output prefix')
        tokens = output[0, len(ids):].tolist()
        record = {'index': i, 'id': item['id'], 'attempt_sha256': file_hash(attempt_path),
                  'generated_token_ids': tokens, 'generated_token_ids_sha256': ids_hash(tokens),
                  'output': tok.decode(tokens, skip_special_tokens=True), 'elapsed_seconds': elapsed,
                  'completed_at': datetime.now(timezone.utc).isoformat()}
        write_new(RUN / 'records' / f'{i:03d}.json', record)
        state = read_state(manifest, tok, data)
        print(json.dumps({'completed': state['records'], 'total': state['total'], 'smoke': i < 4}), flush=True)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'inspect', 'collect'))
    args = parser.parse_args()
    try:
        if args.stage == 'prepare':
            result = prepare()
        else:
            with locked():
                manifest = load_manifest()
                validate_files(manifest)
                tok, data = tokenizer(), inputs()
                result = collect(manifest, tok, data) if args.stage == 'collect' else read_state(manifest, tok, data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'STOP: {error}; preserve the run directory, do not retry or delete attempts.', file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == '__main__':
    main()
