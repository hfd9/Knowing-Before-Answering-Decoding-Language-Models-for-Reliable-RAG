#!/usr/bin/env python3
"""Resume unattempted pilot items in a new 384-token run, preserving v1 unchanged."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import query_determinacy_pilot as core

V1 = core.ROOT / 'runs/qwen2.5-3b-query-determinacy-pilot-v1'
V1_ARCHIVE = core.ROOT / 'docs/review/2026-11-12-query-determinacy-pilot-v1/manifest.json'
RUN = core.ROOT / 'runs/qwen2.5-3b-query-determinacy-remaining-v2'
ARCHIVE = core.ROOT / 'docs/review/2026-11-12-query-determinacy-remaining-v2/manifest.json'
SCRIPT = Path(__file__).resolve()
LIMIT = 384
EXPECTED_V1 = {
    'manifest.json': '9c815e26d0038617cb4eeac4faf3974248a38ab6b83c0b66a84fbc1decad125e',
    'attempts/000.json': 'a083459924d293ea371e8b41c2adca61db3c3cc4cfbecc08c9f29a8a69554719',
    'records/000.json': 'cbb58076c9acb1f1f601d2090a59f2f46501698d257c608d9ee99d0e87fb3136',
}


def verify_v1():
    if V1.is_symlink() or not V1.is_dir():
        raise ValueError('original run missing or symlink')
    for directory in ('attempts', 'records'):
        path = V1 / directory
        if path.is_symlink() or sorted(x.name for x in path.iterdir()) != ['000.json']:
            raise ValueError('original journal differs from one-attempt state')
    for name, expected in EXPECTED_V1.items():
        path = V1 / name
        if path.is_symlink() or core.file_hash(path) != expected:
            raise ValueError('original run fingerprint changed: ' + name)
    if core.file_hash(V1_ARCHIVE) != EXPECTED_V1['manifest.json']:
        raise ValueError('original archived manifest changed')
    manifest = json.loads((V1 / 'manifest.json').read_text())
    attempt = json.loads((V1 / 'attempts/000.json').read_text())
    record = json.loads((V1 / 'records/000.json').read_text())
    first = manifest['items'][0]
    tok = core.tokenizer()
    data = core.inputs()
    rendered, ids = core.render(tok, data[first['id']])
    tokens = record['generated_token_ids']
    if (attempt != {'index': 0, 'id': first['id'], 'manifest_sha256': EXPECTED_V1['manifest.json']}
            or record['id'] != first['id'] or record['index'] != 0
            or record['attempt_sha256'] != EXPECTED_V1['attempts/000.json']
            or core.digest(data[first['id']].encode()) != first['prompt_sha256']
            or core.digest(rendered.encode()) != first['rendered_sha256']
            or core.ids_hash(ids) != first['token_ids_sha256']
            or core.ids_hash(tokens) != record['generated_token_ids_sha256']
            or tok.decode(tokens, skip_special_tokens=True) != record['output']
            or len(tokens) != 128 or any(t in manifest['generation']['eos_token_ids'] for t in tokens)):
        raise ValueError('original truncated record failed verification')
    return manifest


def build_manifest():
    original = verify_v1()
    rebuilt = core.build_manifest()
    if core.canonical(rebuilt) != V1_ARCHIVE.read_bytes() or rebuilt != original:
        raise ValueError('original full manifest no longer reproducible')
    manifest = dict(rebuilt)
    manifest['schema'] = 'query_determinacy_remaining_v2'
    manifest['items'] = rebuilt['items'][1:]
    manifest['count'] = len(manifest['items'])
    manifest['generation'] = dict(rebuilt['generation'], max_new_tokens=LIMIT)
    manifest['implementation_sha256'] = dict(rebuilt['implementation_sha256'],
        **{str(SCRIPT.relative_to(core.ROOT)): core.file_hash(SCRIPT)})
    manifest['original_run'] = {'source_fingerprints': EXPECTED_V1,
                                'attempted_id': original['items'][0]['id'],
                                'attempted_status': 'truncated_unscored_no_regeneration',
                                'planned_original_total': 144}
    if manifest['count'] != 143 or any(x['id'] == manifest['original_run']['attempted_id'] for x in manifest['items']):
        raise ValueError('remaining item list mismatch')
    if any(x['input_tokens'] + LIMIT > 32768 for x in manifest['items']):
        raise ValueError('input exceeds context budget')
    return manifest


def read_state(manifest, tok, data):
    if {x.name for x in RUN.iterdir()} != {'manifest.json', 'run.lock', 'attempts', 'records'}:
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
        if (attempt_path.name != f'{i:03d}.json' or record_path.name != f'{i:03d}.json'
                or attempt_path.is_symlink() or record_path.is_symlink()):
            raise ValueError('journal is not a regular ordered prefix')
        item = manifest['items'][i]
        attempt = json.loads(attempt_path.read_text())
        record = json.loads(record_path.read_text())
        rendered, ids = core.render(tok, data[item['id']])
        if (core.digest(data[item['id']].encode()) != item['prompt_sha256']
                or core.digest(rendered.encode()) != item['rendered_sha256']
                or core.ids_hash(ids) != item['token_ids_sha256'] or len(ids) != item['input_tokens']):
            raise ValueError('rendered prompt changed')
        if attempt != {'index': i, 'id': item['id'], 'manifest_sha256': core.file_hash(RUN / 'manifest.json')}:
            raise ValueError('attempt binding mismatch')
        tokens = record.get('generated_token_ids')
        if not isinstance(tokens, list) or not 1 <= len(tokens) <= LIMIT or any(type(t) is not int or t < 0 or t >= len(tok) for t in tokens):
            raise ValueError('invalid generated tokens')
        eos = manifest['generation']['eos_token_ids']
        if (any(t in eos for t in tokens[:-1]) or record.get('index') != i or record.get('id') != item['id']
                or record.get('attempt_sha256') != core.file_hash(attempt_path)
                or record.get('output') != tok.decode(tokens, skip_special_tokens=True)
                or record.get('generated_token_ids_sha256') != core.ids_hash(tokens)):
            raise ValueError('record binding or token decoding mismatch')
        if not record['output'].strip() or tokens[-1] not in eos:
            raise ValueError('empty or truncated output: preserve journal and stop')
    return {'records': len(records), 'attempts': len(attempts), 'total': manifest['count'],
            'state': 'complete_unreviewed' if len(records) == manifest['count'] else 'valid_prefix',
            'original_truncated_unscored': 1, 'semantic_review_completed': False}


def prepare():
    manifest = build_manifest()
    if RUN.exists() or RUN.is_symlink():
        raise ValueError('run directory exists; use inspect, never overwrite')
    RUN.mkdir(mode=0o700)
    (RUN / 'attempts').mkdir(mode=0o700)
    (RUN / 'records').mkdir(mode=0o700)
    (RUN / 'run.lock').touch(mode=0o600, exist_ok=False)
    core.write_new(RUN / 'manifest.json', manifest)
    return {'state': 'prepared_not_started', 'count': manifest['count'], 'first_attempt_not_repeated': True,
            'max_new_tokens': LIMIT, 'manifest_sha256': core.file_hash(RUN / 'manifest.json')}


def load_manifest():
    if (RUN / 'manifest.json').is_symlink() or ARCHIVE.is_symlink() or (RUN / 'manifest.json').read_bytes() != ARCHIVE.read_bytes():
        raise ValueError('run manifest differs from frozen archive')
    manifest = json.loads(ARCHIVE.read_text())
    if manifest.get('schema') != 'query_determinacy_remaining_v2' or manifest.get('count') != 143 or len(manifest.get('items', [])) != 143:
        raise ValueError('invalid manifest')
    if manifest['generation']['max_new_tokens'] != LIMIT or manifest['original_run']['source_fingerprints'] != EXPECTED_V1:
        raise ValueError('execution limits or original binding changed')
    return manifest


def collect(manifest, tok, data):
    core.validate_files(manifest, include_weights=True)
    state = read_state(manifest, tok, data)
    if state['state'] == 'complete_unreviewed':
        return state
    core.verify_device()
    import torch
    from transformers import AutoModelForCausalLM, GenerationConfig
    model = AutoModelForCausalLM.from_pretrained(str(core.MODEL), local_files_only=True, dtype=torch.bfloat16,
                                                device_map={'': 0}, attn_implementation='sdpa').eval()
    model.requires_grad_(False)
    cfg = GenerationConfig(max_new_tokens=LIMIT, do_sample=False, num_beams=1, use_cache=True,
                           eos_token_id=manifest['generation']['eos_token_ids'],
                           bos_token_id=model.generation_config.bos_token_id,
                           pad_token_id=tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id)
    for i in range(state['records'], manifest['count']):
        item = manifest['items'][i]
        _, ids = core.render(tok, data[item['id']])
        if core.ids_hash(ids) != item['token_ids_sha256']:
            raise ValueError('input changed before generation')
        attempt_path = RUN / 'attempts' / f'{i:03d}.json'
        core.write_new(attempt_path, {'index': i, 'id': item['id'], 'manifest_sha256': core.file_hash(RUN / 'manifest.json')})
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
        record = {'index': i, 'id': item['id'], 'attempt_sha256': core.file_hash(attempt_path),
                  'generated_token_ids': tokens, 'generated_token_ids_sha256': core.ids_hash(tokens),
                  'output': tok.decode(tokens, skip_special_tokens=True), 'elapsed_seconds': elapsed,
                  'completed_at': datetime.now(timezone.utc).isoformat()}
        core.write_new(RUN / 'records' / f'{i:03d}.json', record)
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
            core.RUN = RUN
            with core.locked():
                manifest = load_manifest()
                core.validate_files(manifest)
                verify_v1()
                tok, data = core.tokenizer(), core.inputs()
                result = collect(manifest, tok, data) if args.stage == 'collect' else read_state(manifest, tok, data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'STOP: {error}; preserve both run directories, do not retry or delete attempts.', file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == '__main__':
    main()
