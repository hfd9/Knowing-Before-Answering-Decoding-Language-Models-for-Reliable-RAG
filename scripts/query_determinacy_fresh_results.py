#!/usr/bin/env python3
"""Check frozen sources and tabulate informed manual ratings for fresh development items."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'docs/review/2026-11-15-query-determinacy-fresh-results-v1'
MATERIAL=ROOT/'docs/review/2026-11-15-query-determinacy-fresh-dev-v1/material.jsonl'


def category(row):
    value,ref=row['commitment'],row['reference']
    if value=='T':return 'technical_missing'
    if value=='X':return 'unknown'
    if value==ref:return 'correct'
    if value=='U':return 'overreserve'
    if ref=='U' and value in ('Y','N'):return 'unsupported_choice'
    return 'wrong'


def analyze():
    sources=json.loads((RESULT/'source-archive.json').read_text(encoding='utf-8'))['files']
    if len(sources)!=388 or len({x['path'] for x in sources})!=388:raise ValueError('source count')
    for x in sources:
        raw=x['raw_utf8'].encode('utf-8')
        if hashlib.sha256(raw).hexdigest()!=x['sha256'] or (ROOT/x['path']).read_bytes()!=raw:raise ValueError('source changed')
    records={r['id']:r for r in (json.loads(x['raw_utf8']) for x in sources if '/records/' in x['path'])}
    failures={r['id']:r for r in (json.loads(x['raw_utf8']) for x in sources if '/automatic_failures/' in x['path'])}
    data={r['id']:r for r in map(json.loads,MATERIAL.read_text(encoding='utf-8').splitlines())}
    with (RESULT/'review.csv').open(encoding='utf-8',newline='') as f:review=list(csv.DictReader(f))
    if len(records)!=192 or len(data)!=192 or len(review)!=192 or len(failures)!=3:raise ValueError('row count')
    if len({r['id'] for r in review})!=192 or set(data)!={r['id'] for r in review} or set(data)!=set(records):raise ValueError('IDs mismatch')
    grid=collections.defaultdict(dict)
    for row in review:
        item=data[row['id']]
        if any(row[k]!=item[k] for k in ('case','family','query','condition')) or row['variant']!=item['instruction_variant']:
            raise ValueError('metadata mismatch')
        if row['reference']!=item['expected'] or int(row['index'])!=records[row['id']]['index']:
            raise ValueError('reference or index mismatch')
        if row['commitment'] not in ('Y','N','U','X','T') or (row['commitment']=='T')!=(row['id'] in failures):
            raise ValueError('judgment or failure mismatch')
        key=(row['case'],row['query'],row['condition'])
        if row['variant'] in grid[key]:raise ValueError('duplicate pair')
        grid[key][row['variant']]=row
    if len(grid)!=96 or any(set(g)!={'plain','decompose'} for g in grid.values()):raise ValueError('incomplete pairs')
    groups={}
    for variant in ('plain','decompose'):
        for family in ('number','category'):
            for section in ('single','dual_determinate','dual_split'):
                selection=[r for r in review if r['variant']==variant and r['family']==family and
                           (r['condition'].startswith('single') if section=='single' else
                            r['condition'].startswith('dual_') and ((r['reference']=='U')==(section=='dual_split')))]
                groups[f'{variant}/{family}/{section}']={'n':len(selection),'counts':dict(collections.Counter(category(r) for r in selection))}
    pairs={}
    for section in ('single','dual_determinate','dual_split'):
        if section=='single':
            selected=[g for g in grid.values() if g['plain']['condition'].startswith('single')]
        else:
            selected=[g for g in grid.values() if g['plain']['condition'].startswith('dual_') and ((g['plain']['reference']=='U')==(section=='dual_split'))]
        pairs[section]=dict(collections.Counter(f"{category(g['plain'])}->{category(g['decompose'])}" for g in selected))
    return {'source_files':len(sources),'review_rows':len(review),'technical_failures':len(failures),
            'paired_inputs':len(grid),'groups':groups,'pair_transitions_plain_to_decompose':pairs}


if __name__=='__main__':print(json.dumps(analyze(),ensure_ascii=False,sort_keys=True,indent=2))
