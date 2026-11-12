#!/usr/bin/env python3
"""Collect unattempted pilot items with reviewed technical-failure continuation."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import query_determinacy_pilot as core
import query_determinacy_remaining_v2 as prior

RUN = core.ROOT / 'runs/qwen2.5-3b-query-determinacy-unattempted-v3'
ARCHIVE = core.ROOT / 'docs/review/2026-11-12-query-determinacy-unattempted-v3/manifest.json'
SCRIPT = Path(__file__).resolve()
EXPECTED_LAST = '6a32901c7e9693b359d0475f51793cc049887bfcadc87c44d3a8568a9a46cc0f'
EXPECTED_MANIFEST = '3bbd219a273bdf96c4407bb42dbbba566f9a718c5c841cf1f3e6c3436c2d1ae8'
LIMIT = 384


def snapshot_v2():
    prior.verify_v1()
    manifest = prior.load_manifest()
    core.validate_files(manifest)
    if core.file_hash(prior.RUN / 'manifest.json') != EXPECTED_MANIFEST:
        raise ValueError('v2 manifest changed')
    for name in ('attempts', 'records'):
        path = prior.RUN / name
        if path.is_symlink() or sorted(x.name for x in path.iterdir()) != [f'{i:03d}.json' for i in range(16)]:
            raise ValueError('v2 is not the expected 16-attempt prefix')
    if core.file_hash(prior.RUN / 'records/015.json') != EXPECTED_LAST:
        raise ValueError('v2 truncated record changed')
    try:
        prior.read_state(manifest, core.tokenizer(), core.inputs())
    except ValueError as error:
        if str(error) != 'empty or truncated output: preserve journal and stop':
            raise
    else:
        raise ValueError('expected v2 last record to be truncated')
    files = {'manifest.json': EXPECTED_MANIFEST}
    for name in ('attempts', 'records'):
        for i in range(16):
            relative = f'{name}/{i:03d}.json'
            files[relative] = core.file_hash(prior.RUN / relative)
    return manifest, files


def verify_prior(expected):
    prior.verify_v1()
    if prior.RUN.is_symlink() or not prior.RUN.is_dir():
        raise ValueError('v2 run missing or symlink')
    for name in ('attempts', 'records'):
        path = prior.RUN / name
        if path.is_symlink() or sorted(x.name for x in path.iterdir()) != [f'{i:03d}.json' for i in range(16)]:
            raise ValueError('v2 journal changed')
    for name, expected_hash in expected.items():
        path = prior.RUN / name
        if path.is_symlink() or core.file_hash(path) != expected_hash:
            raise ValueError('v2 prior fingerprint changed: ' + name)
    if core.file_hash(prior.ARCHIVE) != EXPECTED_MANIFEST:
        raise ValueError('v2 archived manifest changed')


def build_manifest():
    previous, hashes = snapshot_v2()
    if core.canonical(prior.build_manifest()) != prior.ARCHIVE.read_bytes():
        raise ValueError('v2 frozen manifest cannot be rebuilt')
    result = dict(previous)
    result['schema'] = 'query_determinacy_unattempted_v3'
    result['items'] = previous['items'][16:]
    result['count'] = len(result['items'])
    result['implementation_sha256'] = dict(previous['implementation_sha256'],
        **{str(SCRIPT.relative_to(core.ROOT)): core.file_hash(SCRIPT)})
    result['prior_v2'] = {'hashes': hashes, 'attempted_ids': [x['id'] for x in previous['items'][:16]],
                          'complete_outputs': 15, 'technical_truncations': 1}
    if result['count'] != 127 or result['generation']['max_new_tokens'] != LIMIT:
        raise ValueError('v3 expected 127 unattempted items at the v2 limit')
    if set(result['prior_v2']['attempted_ids']) & {x['id'] for x in result['items']}:
        raise ValueError('attempted item included in v3')
    return result


def technical_status(tokens, text, eos):
    if not text.strip():
        return 'empty'
    if not tokens or tokens[-1] not in eos:
        return 'truncated_or_unexpected_stop'
    return 'complete'


def receipt_for(index, item_id, attempt_path, record_path, status):
    return {'index': index, 'id': item_id, 'attempt_sha256': core.file_hash(attempt_path),
            'record_sha256': core.file_hash(record_path), 'technical_status': status,
            'decision': 'reviewed_technical_failure_unscored_do_not_retry'}


def read_state(manifest, tok, data):
    if {p.name for p in RUN.iterdir()} != {'manifest.json', 'run.lock', 'attempts', 'records', 'decisions'}:
        raise ValueError('unexpected run files')
    for name in ('attempts', 'records', 'decisions'):
        path = RUN / name
        if path.is_symlink() or not path.is_dir():
            raise ValueError('invalid journal directory')
    attempts, records = (sorted((RUN / name).iterdir()) for name in ('attempts', 'records'))
    decisions = {p.name: p for p in (RUN / 'decisions').iterdir()}
    if len(attempts) != len(records) or len(records) > manifest['count']:
        raise ValueError('unfinished attempt or unexpected records; preserve and stop')
    used = set()
    failures = []
    for i, (ap, rp) in enumerate(zip(attempts, records)):
        name = f'{i:03d}.json'
        if ap.name != name or rp.name != name or ap.is_symlink() or rp.is_symlink():
            raise ValueError('journal is not a regular prefix')
        item = manifest['items'][i]
        attempt, record = json.loads(ap.read_text()), json.loads(rp.read_text())
        rendered, ids = core.render(tok, data[item['id']])
        if (core.digest(data[item['id']].encode()) != item['prompt_sha256']
                or core.digest(rendered.encode()) != item['rendered_sha256']
                or core.ids_hash(ids) != item['token_ids_sha256'] or len(ids) != item['input_tokens']):
            raise ValueError('rendered input changed')
        if attempt != {'index': i, 'id': item['id'], 'manifest_sha256': core.file_hash(RUN / 'manifest.json')}:
            raise ValueError('attempt binding changed')
        tokens = record.get('generated_token_ids')
        if not isinstance(tokens, list) or len(tokens) > LIMIT or any(type(t) is not int or t < 0 or t >= len(tok) for t in tokens):
            raise ValueError('invalid generated tokens')
        eos = manifest['generation']['eos_token_ids']
        text = tok.decode(tokens, skip_special_tokens=True)
        if (any(t in eos for t in tokens[:-1]) or record.get('index') != i or record.get('id') != item['id']
                or record.get('attempt_sha256') != core.file_hash(ap)
                or record.get('output') != text or record.get('generated_token_ids_sha256') != core.ids_hash(tokens)):
            raise ValueError('record binding or decoded output mismatch')
        status = technical_status(tokens, text, eos)
        if status != 'complete':
            failures.append({'index': i, 'id': item['id'], 'status': status})
            if name not in decisions:
                if i != len(records) - 1 or len(decisions) != len(used):
                    raise ValueError('unreviewed technical failure before later records')
                return {'state': 'blocked_technical_failure', 'records': len(records), 'attempts': len(attempts),
                        'total': manifest['count'], 'blocked': failures[-1], 'reviewed_failures': len(used)}
            receipt = decisions[name]
            if receipt.is_symlink() or json.loads(receipt.read_text()) != receipt_for(i, item['id'], ap, rp, status):
                raise ValueError('failure review receipt mismatch')
            used.add(name)
        elif name in decisions:
            raise ValueError('review receipt attached to complete record')
    if set(decisions) != used:
        raise ValueError('unexpected failure review receipt')
    return {'state': 'complete_unreviewed' if len(records) == manifest['count'] else 'valid_prefix',
            'records': len(records), 'attempts': len(attempts), 'total': manifest['count'],
            'reviewed_failures': len(used), 'technical_failures': failures}


def prepare():
    manifest = build_manifest()
    if RUN.exists() or RUN.is_symlink():
        raise ValueError('run directory exists; use inspect')
    RUN.mkdir(mode=0o700)
    for name in ('attempts', 'records', 'decisions'):
        (RUN / name).mkdir(mode=0o700)
    (RUN / 'run.lock').touch(mode=0o600, exist_ok=False)
    core.write_new(RUN / 'manifest.json', manifest)
    return {'state': 'prepared_not_started', 'count': manifest['count'],
            'manifest_sha256': core.file_hash(RUN / 'manifest.json')}


def load_manifest():
    if (RUN / 'manifest.json').is_symlink() or ARCHIVE.is_symlink() or (RUN / 'manifest.json').read_bytes() != ARCHIVE.read_bytes():
        raise ValueError('run manifest differs from frozen archive')
    manifest = json.loads(ARCHIVE.read_text())
    if manifest.get('schema') != 'query_determinacy_unattempted_v3' or manifest.get('count') != 127 or len(manifest.get('items', [])) != 127:
        raise ValueError('invalid v3 manifest')
    if manifest['generation']['max_new_tokens'] != LIMIT:
        raise ValueError('generation limit changed')
    return manifest


def acknowledge(state):
    if state['state'] != 'blocked_technical_failure':
        raise ValueError('no technical failure awaiting review')
    info = state['blocked']
    name = f"{info['index']:03d}.json"
    receipt = receipt_for(info['index'], info['id'], RUN / 'attempts' / name, RUN / 'records' / name, info['status'])
    core.write_new(RUN / 'decisions' / name, receipt)
    return {'state': 'failure_recorded_unscored', 'receipt': receipt}


def collect(manifest, tok, data):
    core.validate_files(manifest, include_weights=True)
    state = read_state(manifest, tok, data)
    if state['state'] == 'complete_unreviewed':
        return state
    if state['state'] != 'valid_prefix':
        raise ValueError('unreviewed technical failure; preserve and ask assistant')
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
        ap = RUN / 'attempts' / f'{i:03d}.json'
        core.write_new(ap, {'index': i, 'id': item['id'], 'manifest_sha256': core.file_hash(RUN / 'manifest.json')})
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
        record = {'index': i, 'id': item['id'], 'attempt_sha256': core.file_hash(ap),
                  'generated_token_ids': tokens, 'generated_token_ids_sha256': core.ids_hash(tokens),
                  'output': tok.decode(tokens, skip_special_tokens=True), 'elapsed_seconds': elapsed,
                  'completed_at': datetime.now(timezone.utc).isoformat()}
        core.write_new(RUN / 'records' / f'{i:03d}.json', record)
        state = read_state(manifest, tok, data)
        if state['state'] == 'blocked_technical_failure':
            raise ValueError('technical failure saved; stop and ask assistant')
        print(json.dumps({'completed': state['records'], 'total': state['total']}), flush=True)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'inspect', 'ack', 'collect'))
    args = parser.parse_args()
    try:
        if args.stage == 'prepare':
            result = prepare()
        else:
            core.RUN = RUN
            with core.locked():
                manifest = load_manifest()
                core.validate_files(manifest)
                verify_prior(manifest['prior_v2']['hashes'])
                tok, data = core.tokenizer(), core.inputs()
                state = read_state(manifest, tok, data)
                if args.stage == 'ack':
                    result = acknowledge(state)
                elif args.stage == 'collect':
                    result = collect(manifest, tok, data)
                else:
                    result = state
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'STOP: {error}; preserve all run directories, do not retry or delete attempts.', file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == '__main__':
    main()
