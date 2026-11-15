#!/usr/bin/env python3
"""Verify source journals and summarize manual source-order comparisons and correction."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'docs/review/2026-11-15-query-determinacy-fresh-results-v1'
NEW=ROOT/'docs/review/2026-11-15-query-determinacy-source-order-results-v1'
MATERIAL=ROOT/'docs/review/2026-11-15-query-determinacy-source-order-v1/material.jsonl'


def readcsv(path):
    with path.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def verify(path,count):
    data=json.loads(path.read_text(encoding='utf-8'))['files']
    if len(data)!=count or len({x['path'] for x in data})!=count:raise ValueError('source count mismatch')
    for x in data:
        raw=x['raw_utf8'].encode('utf-8')
        if hashlib.sha256(raw).hexdigest()!=x['sha256'] or (ROOT/x['path']).read_bytes()!=raw:
            raise ValueError('source mismatch: '+x['path'])
    return data


def analyze():
    verify(OLD/'source-archive.json',388)
    newfiles=verify(NEW/'source-archive.json',34)
    failures={r['id'] for r in (json.loads(x['raw_utf8']) for x in newfiles if '/automatic_failures/' in x['path'])}
    records={r['id']:r for r in (json.loads(x['raw_utf8']) for x in newfiles if '/records/' in x['path'])}
    old={r['id']:r for r in readcsv(OLD/'review.csv')}
    corrections=readcsv(NEW/'prior-correction.csv')
    if len(old)!=192 or len(corrections)!=1:raise ValueError('prior or correction count')
    for fix in corrections:
        if old[fix['id']]['commitment']!=fix['old_commitment'] or int(old[fix['id']]['index'])!=int(fix['prior_index']):
            raise ValueError('prior correction does not match original')
        old[fix['id']]=dict(old[fix['id']],commitment=fix['corrected_commitment'])
    data={r['id']:r for r in map(json.loads,MATERIAL.read_text(encoding='utf-8').splitlines())}
    review=readcsv(NEW/'review.csv')
    if len(data)!=16 or len(review)!=16 or len(records)!=16 or len(failures)!=1 or {r['id'] for r in review}!=set(data):
        raise ValueError('new item count')
    cases=collections.defaultdict(dict)
    for row in review:
        item=data[row['id']];record=records[row['id']]
        if any(row[k]!=item[k] for k in ('source_id','case','family')) or row['variant']!=item['source_variant']:
            raise ValueError('metadata mismatch')
        if int(row['index'])!=record['index'] or row['reference']!=item['expected'] or row['commitment'] not in ('U','N','Y','X','T'):
            raise ValueError('reference/index/judgment mismatch')
        if (row['commitment']=='T')!=(row['id'] in failures):raise ValueError('failure mismatch')
        if row['variant'] in cases[row['case']]:raise ValueError('duplicate variant')
        cases[row['case']][row['variant']]=row['commitment']
        cases[row['case']]['family']=row['family']
        cases[row['case']]['original_sources']=old[row['source_id']]['commitment']
        alt_id=f"{row['case']}_split_dual_alternatives__decompose"
        cases[row['case']]['original_alternatives']=old[alt_id]['commitment']
    if len(cases)!=8 or any(set(v)!={'swap_labels','swap_order','family','original_sources','original_alternatives'} for v in cases.values()):
        raise ValueError('pair grid incomplete')
    counts={}
    for family in ('number','category'):
        for condition in ('original_sources','swap_labels','swap_order','original_alternatives'):
            counts[f'{family}/{condition}']=dict(collections.Counter(x[condition] for x in cases.values() if x['family']==family))
    return {'new_source_files':len(newfiles),'old_source_files':388,'cases':dict(sorted(cases.items())),
            'counts':counts,'prior_correction_count':len(corrections)}


if __name__=='__main__':print(json.dumps(analyze(),ensure_ascii=False,sort_keys=True,indent=2))
