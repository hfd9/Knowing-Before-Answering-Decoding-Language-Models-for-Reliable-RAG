#!/usr/bin/env python3
"""Independently count saved outputs and compare the prior matched development replay."""
import collections
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'docs/review/2026-11-18-query-determinacy-paraphrase-results-v1'
source = json.loads((out / 'source-archive.json').read_text())['files']
records = {r['id']: r for r in (json.loads(f['raw_utf8']) for f in source if '/records/' in f['path'])}
material_path = root / 'docs/review/2026-11-17-query-determinacy-paraphrase-dev-v1/material.jsonl'
materials = {x['id']: x for x in map(json.loads, material_path.read_text().splitlines())}
items = json.loads((out / 'items.json').read_text())
extract = json.loads((out / 'extraction.json').read_text())
summary = json.loads((out / 'summary.json').read_text())
assert len(records) == len(materials) == 96 and len(items) == 72 and len(extract) == 24

for row in extract:
    try:
        val = json.loads(records[row['id']]['output'])
    except json.JSONDecodeError:
        val = None
    ok = isinstance(val, list) and len(val) == 2 and all(type(x) is str and x for x in val) and val[0] != val[1]
    expected = materials[row['id']]['expected']
    cls = ('exact_order' if val == expected else 'correct_reversed' if val == expected[::-1] else 'incorrect') if ok else 'invalid'
    assert row['score'] == cls

for row in items:
    raw = records[row['id']]['output'].strip()
    if raw and raw[-1] in '。.!！':
        raw = raw[:-1].rstrip()
    direct = {'是': 'Y', '否': 'N', '无法确定': 'U'}.get(raw, 'X')
    assert direct == row['direct'] and row['reference'] == materials[row['id']]['expected']
    for method in ('direct', 'combined'):
        code = direct if method == 'direct' else row['combined']['code']
        ref = row['reference']
        cls = ('technical_missing' if code == 'T' else 'invalid_or_unresolved' if code == 'X'
               else 'correct' if code == ref else 'overreserve' if code == 'U'
               else 'unsupported_choice' if ref == 'U' else 'wrong')
        assert cls == row[method + '_class']
    bg = next(x for x in extract if x['id'] == row['background_id'])
    if bg['score'] == 'invalid':
        assert row['combined']['code'] == 'X' and row['combined']['reason'] == 'extraction_invalid'
    else:
        a, b = row['combined']['branch_codes']
        expected = a if a == b and a in ('Y', 'N') else 'U' if {a, b} == {'Y', 'N'} else 'T' if 'T' in (a, b) else 'X'
        assert row['combined']['code'] == expected

for cond in ('dual_sources', 'dual_alternatives'):
    group = [x for x in items if x['condition'] == cond]
    for method in ('direct', 'combined'):
        assert dict(collections.Counter(x[method + '_class'] for x in group)) == summary['by_condition'][cond][method]
    for q in ('same_yes', 'same_no', 'split'):
        subgroup = [x for x in group if x['query'] == q]
        assert len(subgroup) == 12
        for method in ('direct', 'combined'):
            assert dict(collections.Counter(x[method + '_class'] for x in subgroup)) == summary['by_condition_query'][cond + '/' + q][method]

old_path = root / 'docs/review/2026-11-15-query-determinacy-model-world-replay-v1/items.json'
old = {x['id']: x for x in json.loads(old_path.read_text())}
assert len(old) == 72
comparison = {}
for cond in ('dual_sources', 'dual_alternatives'):
    group = [x for x in items if x['condition'] == cond]
    matches = [(old[x['id'].removesuffix('__paraphrase')], x) for x in group]
    assert all(a['reference'] == b['reference'] and a['case'] == b['case'] and a['query'] == b['query'] for a, b in matches)
    comparison[cond] = {method: dict(collections.Counter(a[method + '_class'] + ' -> ' + b[method + '_class']
                                                       for a, b in matches)) for method in ('direct', 'combined')}
print(json.dumps({'independent_count': 'passed', 'matched_old_items': 72, 'old_to_paraphrase': comparison}, ensure_ascii=False, indent=2))
