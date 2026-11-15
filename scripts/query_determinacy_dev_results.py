#!/usr/bin/env python3
"""Verify archived sources and count pre-existing informed manual judgments."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RESULT=ROOT/'docs/review/2026-11-15-query-determinacy-development-results-v1'
MATERIAL=ROOT/'docs/review/2026-11-15-query-determinacy-development-v1/material.jsonl'


def sha(data):return hashlib.sha256(data).hexdigest()


def category(row):
    if row['commitment']=='T':return 'technical_missing'
    if row['commitment']=='X':return 'unknown'
    if row['reference']==row['commitment']:return 'correct'
    if row['commitment']=='U':return 'overreserve'
    if row['reference']=='U' and row['commitment'] in ('Y','N'):return 'unsupported_choice'
    return 'wrong'


def analyze():
    archived=json.loads((RESULT/'source-archive.json').read_text(encoding='utf-8'))['files']
    if len(archived)!=145 or len({x['path'] for x in archived})!=145:raise ValueError('unexpected source archive')
    for entry in archived:
        raw=entry['raw_utf8'].encode()
        if sha(raw)!=entry['sha256'] or (ROOT/entry['path']).read_bytes()!=raw:raise ValueError('source mismatch: '+entry['path'])
    data={r['id']:r for r in map(json.loads,MATERIAL.read_text(encoding='utf-8').splitlines())}
    with (RESULT/'review.csv').open(encoding='utf-8',newline='') as file: rows=list(csv.DictReader(file))
    if len(rows)!=72 or len({r['id'] for r in rows})!=72 or {r['id'] for r in rows}!=set(data):raise ValueError('review IDs do not match material')
    records={r['id']:r for r in (json.loads(x['raw_utf8']) for x in archived if '/records/' in x['path'])}
    if len(records)!=72:raise ValueError('record count')
    for row in rows:
        item=data[row['id']];record=records[row['id']]
        if any(row[key]!=item[key] for key in ('family','query','condition')) or row['reference']!=item['expected'] or int(row['index'])!=record['index']:
            raise ValueError('review mapping mismatch')
        if row['commitment'] not in ('Y','N','U','X','T'):raise ValueError('invalid judgment')
        if row['commitment']=='T':raise ValueError('inspect found no technical failures')
    grid=collections.defaultdict(dict)
    for row in rows:grid[(data[row['id']]['case'],row['query'])][row['condition']]=row
    counts={}
    for condition in ('single_a','single_b','dual_sources','dual_alternatives'):
        for family in ('number','category'):
            for query in ('same_yes','same_no','split'):
                selected=[r for r in rows if r['condition']==condition and r['family']==family and r['query']==query]
                counts[f'{condition}/{family}/{query}']=dict(collections.Counter(category(r) for r in selected))
    summary={'rows':len(rows),'by_condition':{c:dict(collections.Counter(category(r) for r in rows if r['condition']==c)) for c in ('single_a','single_b','dual_sources','dual_alternatives')},
             'single_by_family':{f:dict(collections.Counter(category(r) for r in rows if r['condition'].startswith('single') and r['family']==f)) for f in ('number','category')},
             'dual_by_reference':{f'{c}/{kind}':dict(collections.Counter(category(r) for r in rows if r['condition']==c and ((r['reference']=='U')== (kind=='split')))) for c in ('dual_sources','dual_alternatives') for kind in ('determinate','split')},
             'pair_transitions':dict(collections.Counter(f"{category(g['dual_sources'])}->{category(g['dual_alternatives'])}" for g in grid.values())),
             'cells':counts,'source_count':len(archived),'explanation_flags':dict(collections.Counter(r['explanation'] for r in rows))}
    return summary


if __name__=='__main__':print(json.dumps(analyze(),ensure_ascii=False,indent=2,sort_keys=True))
