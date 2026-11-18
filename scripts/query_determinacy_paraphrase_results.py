#!/usr/bin/env python3
"""Seal and replay the completed paraphrase development run on CPU."""
import argparse
import datetime
import hashlib
import json

import query_determinacy_paraphrase_run as run
import query_determinacy_paraphrase_study as study

ROOT = run.ROOT
OUT = ROOT / 'docs/review/2026-11-18-query-determinacy-paraphrase-results-v1'
ARCHIVE = OUT / 'source-archive.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def serialized(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def seal():
    if ARCHIVE.exists():
        raise ValueError('archive already exists; use verify')
    paths = [run.RUN / 'manifest.json']
    for folder in ('attempts', 'records'):
        paths.extend(sorted((run.RUN / folder).glob('*.json')))
    if len(paths) != 193 or any(p.is_symlink() for p in paths):
        raise ValueError('expected 193 ordinary source files')
    if any((run.RUN / 'automatic_failures').iterdir()):
        raise ValueError('technical failures require separate treatment')
    files = []
    for p in paths:
        raw = p.read_bytes()
        files.append({'path': str(p.relative_to(ROOT)), 'sha256': sha(raw), 'raw_utf8': raw.decode('utf-8')})
    OUT.mkdir(parents=True, exist_ok=True)
    with ARCHIVE.open('xb') as f:
        f.write(serialized({'schema': 'paraphrase_sources_v1', 'files': files}))
    return {'sources_sealed': len(files), 'archive_sha256': sha(ARCHIVE.read_bytes())}


def calculate():
    archive = json.loads(ARCHIVE.read_bytes())
    files = archive['files']
    if archive['schema'] != 'paraphrase_sources_v1' or len(files) != 193 or len({x['path'] for x in files}) != 193:
        raise ValueError('bad archive')
    for entry in files:
        raw = entry['raw_utf8'].encode('utf-8')
        if sha(raw) != entry['sha256'] or (ROOT / entry['path']).read_bytes() != raw:
            raise ValueError('archive or live source mismatch: ' + entry['path'])
    if (run.RUN / 'manifest.json').read_bytes() != run.ARCHIVE.read_bytes():
        raise ValueError('manifest archive mismatch')
    records = {r['id']: r for r in (json.loads(x['raw_utf8']) for x in files if '/records/' in x['path'])}
    if len(records) != 96:
        raise ValueError('record ID mismatch')
    items = run.inputs()
    rows, summary = study.evaluate(items, records, set())
    extraction = []
    for item in items.values():
        if item['kind'] == 'extract':
            record = records[item['id']]
            status, values = study.extractor.parse(record['output'])
            extraction.append({'id': item['id'], 'case': item['case'], 'condition': item['condition'],
                               'reference': item['expected'], 'output': record['output'], 'parsed': values,
                               'parse_status': status, 'score': study.extractor.score(record['output'], item['expected'])})
    manifest = run.load_manifest()
    eos = set(manifest['generation']['eos_token_ids'])
    ordered = [records[x['id']] for x in manifest['items']]
    stats = {'record_count': len(ordered), 'attempt_count': 96,
             'eos_count': sum(bool(x['generated_token_ids']) and x['generated_token_ids'][-1] in eos for x in ordered),
             'empty_output_count': sum(not x['output'].strip() for x in ordered),
             'max_token_count': max(len(x['generated_token_ids']) for x in ordered),
             'elapsed_generation_seconds_sum': sum(x['elapsed_seconds'] for x in ordered),
             'first_completed_at': ordered[0]['completed_at'], 'last_completed_at': ordered[-1]['completed_at']}
    t0 = datetime.datetime.fromisoformat(stats['first_completed_at'])
    t1 = datetime.datetime.fromisoformat(stats['last_completed_at'])
    stats['first_to_last_record_seconds'] = (t1 - t0).total_seconds()
    if stats['eos_count'] != 96 or stats['empty_output_count'] != 0:
        raise ValueError('unexpected EOS or empty output')
    return {'items.json': rows, 'summary.json': summary, 'extraction.json': extraction, 'technical.json': stats}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('stage', choices=('seal', 'analyze', 'verify'))
    args = cli.parse_args()
    if args.stage == 'seal':
        result = seal()
    else:
        results = calculate()
        for name, value in results.items():
            data = serialized(value)
            path = OUT / name
            if args.stage == 'analyze':
                with path.open('xb') as f:
                    f.write(data)
            elif path.read_bytes() != data:
                raise ValueError('result mismatch: ' + name)
        result = {'stage': args.stage, 'sources': 193, 'items': len(results['items.json']),
                  'extractions': len(results['extraction.json']), 'summary': results['summary.json'],
                  'technical': results['technical.json']}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
