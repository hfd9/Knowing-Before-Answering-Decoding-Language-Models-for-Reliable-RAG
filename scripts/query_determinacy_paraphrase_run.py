#!/usr/bin/env python3
"""Freeze and collect the 96 exposed-template paraphrase development inputs."""
import argparse
import json
import random
import subprocess
import sys
from pathlib import Path

import query_determinacy_dev_run as base
import query_determinacy_paraphrase_audit as audit
import query_determinacy_paraphrase_study as study

ROOT = base.ROOT
RUN = ROOT / 'runs/qwen2.5-3b-query-determinacy-paraphrase-dev-v1'
ARCHIVE = ROOT / 'docs/review/2026-11-17-query-determinacy-paraphrase-dev-v1/manifest.json'
DEPENDENCIES = base.SCRIPTS + [
    Path(__file__).resolve(), Path(audit.__file__).resolve(), Path(study.__file__).resolve(),
    Path(study.branch.__file__).resolve(), Path(study.paraphrase.__file__).resolve(),
    Path(study.oracle.__file__).resolve(), Path(study.oracle_audit.__file__).resolve(),
    Path(study.oracle.material.__file__).resolve(), Path(study.oracle.audit.__file__).resolve(),
    Path(study.extractor.__file__).resolve(), Path(study.answer_parser.__file__).resolve(),
    Path(study.evaluator.__file__).resolve(), Path(study.branch.old.__file__).resolve(),
    Path(study.branch.template.__file__).resolve(), Path(study.paraphrase.prior.__file__).resolve(),
    ROOT / 'docs/review/2026-11-15-query-determinacy-oracle-dev-v1/material.jsonl',
    ROOT / 'docs/review/2026-11-15-query-determinacy-oracle-results-v1/source-archive.json',
    ROOT / 'docs/review/2026-11-17-query-determinacy-paraphrase-dev-v1/informed-background-review.csv',
]


def inputs():
    audit.audit()
    rows = [json.loads(x) for x in audit.MATERIAL.read_text(encoding='utf-8').splitlines()]
    return {row['id']: row for row in rows}


def ordered(data):
    rows = list(data.values())
    random.Random(21711).shuffle(rows)
    rules = [lambda x: x['kind'] == 'extract' and x['family'] == 'number' and x['condition'] == 'dual_sources',
             lambda x: x['kind'] == 'extract' and x['family'] == 'category' and x['condition'] == 'dual_alternatives',
             lambda x: x['kind'] == 'direct' and x['family'] == 'number' and x['condition'] == 'dual_alternatives',
             lambda x: x['kind'] == 'direct' and x['family'] == 'category' and x['condition'] == 'dual_sources']
    smoke = [next(x for x in rows if rule(x)) for rule in rules]
    ids = {x['id'] for x in smoke}
    if len(ids) != 4:
        raise ValueError('smoke collision')
    return smoke + [x for x in rows if x['id'] not in ids]


def build_manifest():
    data = inputs()
    study.cached_branches()
    reference = json.loads(base.core.REFERENCE.read_text(encoding='utf-8'))
    if Path(reference['model']) != base.core.MODEL:
        raise ValueError('model mismatch')
    weights = {name: base.core.file_hash(base.core.MODEL / name) for name in reference['model_files_sha256']}
    if weights != reference['model_files_sha256']:
        raise ValueError('model files changed')
    tok = base.core.tokenizer()
    items = []
    for row in ordered(data):
        rendered, ids = base.core.render(tok, row['prompt'])
        if len(ids) + base.LIMIT > reference['context_tokens']:
            raise ValueError('context too long')
        items.append({'id': row['id'], 'prompt_sha256': base.core.digest(row['prompt'].encode()),
                      'rendered_sha256': base.core.digest(rendered.encode()), 'token_ids_sha256': base.core.ids_hash(ids),
                      'input_tokens': len(ids)})
    eos = json.loads((base.core.MODEL / 'generation_config.json').read_text())['eos_token_id']
    if not isinstance(eos, list):
        eos = [eos]
    return {'schema': 'query_determinacy_paraphrase_dev_v1', 'count': 96, 'smoke_count': 4, 'seed': 21711,
            'items': items, 'material_sha256': base.core.file_hash(audit.MATERIAL),
            'reference_sha256': base.core.file_hash(base.core.REFERENCE),
            'implementation_sha256': {str(p.relative_to(ROOT)): base.core.file_hash(p) for p in DEPENDENCIES},
            'model': str(base.core.MODEL), 'model_files_sha256': weights, 'versions': base.core.versions(),
            'generation': {'max_new_tokens': base.LIMIT, 'do_sample': False, 'num_beams': 1, 'dtype': 'bfloat16',
                           'attention': 'sdpa', 'use_cache': True, 'eos_token_ids': eos},
            'failure_policy': 'smoke failure stops; later technical failure saved and skipped without retry; structural failure stops',
            'parser': 'frozen extraction JSON and answer parsers; cached branch prompt exact match; no gold correction',
            'semantic_review_completed': False, 'semantic_review_note': 'informed author review only; not independent'}


def configure():
    base.RUN = RUN
    base.core.RUN = RUN
    base.audit.MATERIAL = audit.MATERIAL


def prepare():
    if RUN.exists() or RUN.is_symlink() or ARCHIVE.exists():
        raise ValueError('run or archive exists; do not overwrite')
    manifest = build_manifest()
    base.core.write_new(ARCHIVE, manifest)
    RUN.mkdir(mode=0o700)
    for name in ('attempts', 'records', 'automatic_failures'):
        (RUN / name).mkdir(mode=0o700)
    (RUN / 'run.lock').touch(mode=0o600, exist_ok=False)
    base.core.write_new(RUN / 'manifest.json', manifest)
    return {'state': 'prepared_not_started', 'count': len(manifest['items']),
            'manifest_sha256': base.core.file_hash(ARCHIVE),
            'min_tokens': min(x['input_tokens'] for x in manifest['items']),
            'max_tokens': max(x['input_tokens'] for x in manifest['items'])}


def load_manifest():
    if ARCHIVE.is_symlink() or (RUN / 'manifest.json').is_symlink() or ARCHIVE.read_bytes() != (RUN / 'manifest.json').read_bytes():
        raise ValueError('manifest differs from archive')
    manifest = json.loads(ARCHIVE.read_text())
    if manifest.get('schema') != 'query_determinacy_paraphrase_dev_v1' or manifest.get('count') != 96 or len(manifest['items']) != 96:
        raise ValueError('invalid manifest')
    return manifest


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('stage', choices=('prepare', 'inspect', 'collect'))
    args = cli.parse_args()
    try:
        if args.stage == 'prepare':
            result = prepare()
        else:
            data = inputs()
            configure()
            with base.core.locked():
                manifest = load_manifest()
                base.validate_files(manifest)
                tok = base.core.tokenizer()
                result = base.collect(manifest, tok, data) if args.stage == 'collect' else base.read_state(manifest, tok, data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'STOP: {error}; preserve run, do not delete or retry attempts', file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == '__main__':
    main()
