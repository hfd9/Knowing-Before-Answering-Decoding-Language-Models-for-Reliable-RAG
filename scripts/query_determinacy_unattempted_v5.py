#!/usr/bin/env python3
"""Collect remaining items; retain empty/truncated outputs and continue without retries."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import query_determinacy_unattempted_v4 as previous

core, base = previous.core, previous.base
RUN = core.ROOT / 'runs/qwen2.5-3b-query-determinacy-unattempted-v5'
ARCHIVE = core.ROOT / 'docs/review/2026-11-12-query-determinacy-unattempted-v5/manifest.json'
SCRIPT = Path(__file__).resolve()
PRIOR_RUN = core.ROOT / 'runs/qwen2.5-3b-query-determinacy-unattempted-v4'
PRIOR_MANIFEST = '540561dc9b961a868f0f3abfff30ef54fd67effc7f5a692189964eb7f4ead67f'
PRIOR_LAST = '11b7de78c27c081e5ebb22c5f1b761a5ba3be79074d8210228c2342c0fc14632'
LIMIT = 384


def snapshot_previous():
    previous.configure_paths()
    manifest = previous.load_manifest()
    core.validate_files(manifest, include_weights=True)
    base.verify_prior(manifest['prior_v2']['hashes'])
    for name in ('attempts', 'records'):
        path = PRIOR_RUN / name
        if path.is_symlink() or sorted(p.name for p in path.iterdir()) != [f'{i:03d}.json' for i in range(4)]:
            raise ValueError('v4 is not the expected four-attempt prefix')
    if (PRIOR_RUN / 'decisions').is_symlink() or list((PRIOR_RUN / 'decisions').iterdir()):
        raise ValueError('unexpected v4 failure decisions')
    if core.file_hash(PRIOR_RUN / 'manifest.json') != PRIOR_MANIFEST or core.file_hash(PRIOR_RUN / 'records/003.json') != PRIOR_LAST:
        raise ValueError('v4 manifest or last record changed')
    state = base.read_state(manifest, core.tokenizer(), core.inputs())
    if (state.get('state') != 'blocked_technical_failure' or state.get('records') != 4
            or state['blocked']['index'] != 3 or state['blocked']['status'] != 'truncated_or_unexpected_stop'):
        raise ValueError('v4 did not end with the expected technical failure')
    hashes = {'manifest.json': PRIOR_MANIFEST}
    for name in ('attempts', 'records'):
        for i in range(4):
            rel = f'{name}/{i:03d}.json'
            hashes[rel] = core.file_hash(PRIOR_RUN / rel)
    return manifest, hashes


def verify_previous(manifest):
    base.verify_prior(manifest['prior_v2']['hashes'])
    prior_archive = core.ROOT / 'docs/review/2026-11-12-query-determinacy-unattempted-v4/manifest.json'
    if core.file_hash(prior_archive) != PRIOR_MANIFEST:
        raise ValueError('archived v4 manifest changed')
    for name in ('attempts', 'records'):
        path = PRIOR_RUN / name
        if path.is_symlink() or sorted(p.name for p in path.iterdir()) != [f'{i:03d}.json' for i in range(4)]:
            raise ValueError('v4 journal changed')
    if (PRIOR_RUN / 'decisions').is_symlink() or list((PRIOR_RUN / 'decisions').iterdir()):
        raise ValueError('v4 decisions changed')
    for name, expected in manifest['prior_v4']['hashes'].items():
        path = PRIOR_RUN / name
        if path.is_symlink() or core.file_hash(path) != expected:
            raise ValueError('v4 prior fingerprint changed: ' + name)


def build_manifest():
    old, hashes = snapshot_previous()
    result = dict(old)
    result['schema'] = 'query_determinacy_unattempted_v5'
    result['items'] = old['items'][4:]
    result['count'] = len(result['items'])
    result['implementation_sha256'] = dict(old['implementation_sha256'],
        **{str(SCRIPT.relative_to(core.ROOT)): core.file_hash(SCRIPT)})
    result['prior_v4'] = {'hashes': hashes, 'attempted_ids': [x['id'] for x in old['items'][:4]],
                          'complete_outputs': 3, 'technical_truncations': 1}
    result['failure_policy'] = 'save and automatically mark empty or no-EOS as unscored, continue to next unattempted item; structural faults stop'
    if result['count'] != 123 or result['generation']['max_new_tokens'] != LIMIT:
        raise ValueError('expected 123 unattempted items at the original v2 token limit')
    if set(result['prior_v4']['attempted_ids']) & {x['id'] for x in result['items']}:
        raise ValueError('already attempted v4 item included')
    return result


def failure_receipt(index, item_id, status):
    return {'index': index, 'id': item_id, 'technical_status': status,
            'attempt_sha256': core.file_hash(RUN / 'attempts' / f'{index:03d}.json'),
            'record_sha256': core.file_hash(RUN / 'records' / f'{index:03d}.json'),
            'decision': 'automatic_technical_failure_unscored_do_not_retry'}


def read_state(manifest, tok, data):
    if {x.name for x in RUN.iterdir()} != {'manifest.json', 'run.lock', 'attempts', 'records', 'automatic_failures'}:
        raise ValueError('unexpected run directory files')
    for name in ('attempts', 'records', 'automatic_failures'):
        path = RUN / name
        if path.is_symlink() or not path.is_dir():
            raise ValueError('invalid journal directory')
    attempts, records = (sorted((RUN / name).iterdir()) for name in ('attempts', 'records'))
    receipts = {p.name: p for p in (RUN / 'automatic_failures').iterdir()}
    if len(attempts) != len(records) or len(records) > manifest['count']:
        raise ValueError('unfinished attempt or unexpected record: preserve and stop')
    failures = []
    used = set()
    previous.RUN = RUN
    for i, (ap, rp) in enumerate(zip(attempts, records)):
        name = f'{i:03d}.json'
        if ap.name != name or rp.name != name or ap.is_symlink() or rp.is_symlink():
            raise ValueError('journal is not a regular ordered prefix')
        status = previous.verify_new_record(i, manifest, tok, data)
        if status != 'complete':
            if name not in receipts or receipts[name].is_symlink():
                raise ValueError('technical failure lacks automatic receipt; preserve and stop')
            expected = failure_receipt(i, manifest['items'][i]['id'], status)
            if json.loads(receipts[name].read_text()) != expected:
                raise ValueError('automatic failure receipt mismatch')
            used.add(name)
            failures.append({'index': i, 'id': manifest['items'][i]['id'], 'status': status})
        elif name in receipts:
            raise ValueError('failure receipt attached to complete record')
    if set(receipts) != used:
        raise ValueError('unexpected automatic failure receipt')
    return {'state': 'complete_unreviewed' if len(records) == manifest['count'] else 'valid_prefix',
            'attempts': len(attempts), 'records': len(records), 'total': manifest['count'],
            'technically_complete': len(records) - len(failures), 'technical_failures': failures,
            'semantic_review_completed': False}


def prepare():
    manifest = build_manifest()
    if RUN.exists() or RUN.is_symlink():
        raise ValueError('run directory exists; use inspect')
    RUN.mkdir(mode=0o700)
    for name in ('attempts', 'records', 'automatic_failures'):
        (RUN / name).mkdir(mode=0o700)
    (RUN / 'run.lock').touch(mode=0o600, exist_ok=False)
    core.write_new(RUN / 'manifest.json', manifest)
    return {'state': 'prepared_not_started', 'count': manifest['count'],
            'manifest_sha256': core.file_hash(RUN / 'manifest.json')}


def load_manifest():
    if (RUN / 'manifest.json').is_symlink() or ARCHIVE.is_symlink() or (RUN / 'manifest.json').read_bytes() != ARCHIVE.read_bytes():
        raise ValueError('run manifest differs from frozen archive')
    manifest = json.loads(ARCHIVE.read_text())
    if (manifest.get('schema') != 'query_determinacy_unattempted_v5' or manifest.get('count') != 123
            or len(manifest.get('items', [])) != 123 or manifest['generation']['max_new_tokens'] != LIMIT):
        raise ValueError('invalid v5 manifest')
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
    failures = len(state['technical_failures'])
    previous.RUN = RUN
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
        status = previous.verify_new_record(i, manifest, tok, data)
        if status != 'complete':
            core.write_new(RUN / 'automatic_failures' / f'{i:03d}.json', failure_receipt(i, item['id'], status))
            failures += 1
        print(json.dumps({'processed': i + 1, 'total': manifest['count'], 'technical_status': status,
                          'technical_failures_in_v5': failures}, ensure_ascii=False), flush=True)
    return read_state(manifest, tok, data)


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
                verify_previous(manifest)
                tok, data = core.tokenizer(), core.inputs()
                result = collect(manifest, tok, data) if args.stage == 'collect' else read_state(manifest, tok, data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'STOP: {error}; preserve all run directories, do not retry or delete attempts.', file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == '__main__':
    main()
