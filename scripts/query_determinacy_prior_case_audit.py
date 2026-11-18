#!/usr/bin/env python3
"""Read-only audit of old branch cases and paraphrase extraction failures."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
review = ROOT / 'docs/review'
prior = json.loads((review / '2026-11-15-query-determinacy-oracle-results-v1/source-archive.json').read_text())['files']
if len(prior) != 289 or len({x['path'] for x in prior}) != 289:
    raise ValueError('prior archive file set mismatch')
for item in prior:
    if hashlib.sha256(item['raw_utf8'].encode()).hexdigest() != item['sha256']:
        raise ValueError('prior archive checksum mismatch')
records = {r['id']: r for f in prior if '/records/' in f['path'] for r in [json.loads(f['raw_utf8'])]}
material = [json.loads(line) for line in (review / '2026-11-15-query-determinacy-oracle-dev-v1/material.jsonl').read_text().splitlines()]
branches = [{'id': x['id'], 'prompt': x['prompt'], 'expected': x['expected'], 'output': records[x['id']]['output']}
            for x in material if x['case'] in ('K04', 'K05') and x['query'] == 'same_yes'
            and x['condition'] in ('single_a', 'single_b')]
if len(branches) != 4 or any(x['expected'] != 'Y' for x in branches):
    raise ValueError('unexpected branches')
rows = json.loads((review / '2026-11-18-query-determinacy-paraphrase-results-v1/items.json').read_text())
remaining = [r for r in rows if r['combined_class'] == 'overreserve']
if len(remaining) != 4 or {(x['case'], x['query']) for x in remaining} != {('K04', 'same_yes'), ('K05', 'same_yes')}:
    raise ValueError('unexpected residual rows')
extractions = json.loads((review / '2026-11-18-query-determinacy-paraphrase-results-v1/extraction.json').read_text())
failures = [x for x in extractions if x['score'] == 'invalid']
if len(failures) != 3:
    raise ValueError('unexpected extraction failures')
print(json.dumps({'branches': branches,
                  'remaining': [{'id': x['id'], 'reference': x['reference'], 'branch_codes': x['combined']['branch_codes']} for x in remaining],
                  'extraction_failures': failures}, ensure_ascii=False, indent=2, sort_keys=True))
