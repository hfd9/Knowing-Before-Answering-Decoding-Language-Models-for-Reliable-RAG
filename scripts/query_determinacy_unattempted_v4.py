#!/usr/bin/env python3
"""Collect remaining pilot items with incremental validation and reviewed stops."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import query_determinacy_unattempted_v3 as base

core = base.core
RUN = core.ROOT / 'runs/qwen2.5-3b-query-determinacy-unattempted-v4'
ARCHIVE = core.ROOT / 'docs/review/2026-11-12-query-determinacy-unattempted-v4/manifest.json'
SCRIPT = Path(__file__).resolve()


def configure_paths():
    base.RUN = RUN
    base.ARCHIVE = ARCHIVE
    core.RUN = RUN


def build_manifest():
    result = base.build_manifest()
    result['schema'] = 'query_determinacy_unattempted_v4'
    result['implementation_sha256'] = dict(result['implementation_sha256'],
        **{str(SCRIPT.relative_to(core.ROOT)): core.file_hash(SCRIPT)})
    result['journal_validation'] = 'full replay at start/end; validate only newly written record while locked'
    return result


def load_manifest():
    if (RUN / 'manifest.json').is_symlink() or ARCHIVE.is_symlink() or (RUN / 'manifest.json').read_bytes() != ARCHIVE.read_bytes():
        raise ValueError('run manifest differs from frozen archive')
    manifest = json.loads(ARCHIVE.read_text())
    if (manifest.get('schema') != 'query_determinacy_unattempted_v4' or manifest.get('count') != 127
            or len(manifest.get('items', [])) != 127 or manifest['generation']['max_new_tokens'] != base.LIMIT):
        raise ValueError('invalid v4 manifest')
    return manifest


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


def verify_new_record(index, manifest, tok, data):
    """Validate one just-written row under the run lock, without replaying the prefix."""
    item = manifest['items'][index]
    ap, rp = (RUN / name / f'{index:03d}.json' for name in ('attempts', 'records'))
    if ap.is_symlink() or rp.is_symlink():
        raise ValueError('journal item cannot be a symlink')
    attempt, record = json.loads(ap.read_text()), json.loads(rp.read_text())
    rendered, ids = core.render(tok, data[item['id']])
    if (core.digest(data[item['id']].encode()) != item['prompt_sha256']
            or core.digest(rendered.encode()) != item['rendered_sha256']
            or core.ids_hash(ids) != item['token_ids_sha256'] or len(ids) != item['input_tokens']):
        raise ValueError('new record input mismatch')
    if attempt != {'index': index, 'id': item['id'], 'manifest_sha256': core.file_hash(RUN / 'manifest.json')}:
        raise ValueError('new attempt binding mismatch')
    tokens = record.get('generated_token_ids')
    if not isinstance(tokens, list) or len(tokens) > base.LIMIT or any(type(t) is not int or t < 0 or t >= len(tok) for t in tokens):
        raise ValueError('invalid new generated tokens')
    eos = manifest['generation']['eos_token_ids']
    output = tok.decode(tokens, skip_special_tokens=True)
    if (any(t in eos for t in tokens[:-1]) or record.get('index') != index or record.get('id') != item['id']
            or record.get('attempt_sha256') != core.file_hash(ap) or record.get('output') != output
            or record.get('generated_token_ids_sha256') != core.ids_hash(tokens)):
        raise ValueError('new record binding or decoded output mismatch')
    return base.technical_status(tokens, output, eos)


def collect(manifest, tok, data):
    core.validate_files(manifest, include_weights=True)
    state = base.read_state(manifest, tok, data)
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
    cfg = GenerationConfig(max_new_tokens=base.LIMIT, do_sample=False, num_beams=1, use_cache=True,
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
        if verify_new_record(i, manifest, tok, data) != 'complete':
            raise ValueError('technical failure saved; stop and ask assistant')
        print(json.dumps({'completed': i + 1, 'total': manifest['count']}), flush=True)
    return base.read_state(manifest, tok, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'inspect', 'ack', 'collect'))
    args = parser.parse_args()
    configure_paths()
    try:
        if args.stage == 'prepare':
            result = prepare()
        else:
            with core.locked():
                manifest = load_manifest()
                core.validate_files(manifest)
                base.verify_prior(manifest['prior_v2']['hashes'])
                tok, data = core.tokenizer(), core.inputs()
                state = base.read_state(manifest, tok, data)
                if args.stage == 'ack':
                    result = base.acknowledge(state)
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
