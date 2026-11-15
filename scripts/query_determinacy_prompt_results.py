#!/usr/bin/env python3
"""Validate exact source archives and tabulate informed, manually reviewed labels."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'docs/review/2026-11-15-query-determinacy-development-results-v1'
NEW=ROOT/'docs/review/2026-11-15-query-determinacy-prompt-control-results-v1'
MATERIAL=ROOT/'docs/review/2026-11-15-query-determinacy-prompt-control-v1/material.jsonl'


def csv_rows(path):
    with path.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def category(row):
    value,reference=row['commitment'],row['reference']
    if value=='X':return 'unknown'
    if value=='T':return 'technical_missing'
    if value==reference:return 'correct'
    if value=='U':return 'overreserve'
    if reference=='U' and value in ('Y','N'):return 'unsupported_choice'
    return 'wrong'


def verify_archive(path,expected):
    files=json.loads(path.read_text(encoding='utf-8'))['files']
    if len(files)!=expected or len({x['path'] for x in files})!=expected:raise ValueError('archive file count')
    for f in files:
        raw=f['raw_utf8'].encode('utf-8')
        if hashlib.sha256(raw).hexdigest()!=f['sha256'] or (ROOT/f['path']).read_bytes()!=raw:
            raise ValueError('archived and live files differ: '+f['path'])
    return files


def analyze():
    oldfiles=verify_archive(OLD/'source-archive.json',145)
    newfiles=verify_archive(NEW/'source-archive.json',289)
    old={r['id']:r for r in csv_rows(OLD/'review.csv')}
    data={r['id']:r for r in map(json.loads,MATERIAL.read_text(encoding='utf-8').splitlines())}
    review=csv_rows(NEW/'review.csv')
    records={r['id']:r for r in (json.loads(f['raw_utf8']) for f in newfiles if '/records/' in f['path'])}
    if len(old)!=72 or len(data)!=144 or len(review)!=144 or len(records)!=144 or len({r['id'] for r in review})!=144:
        raise ValueError('input counts or uniqueness')
    if {r['id'] for r in review}!=set(data) or set(records)!=set(data):raise ValueError('input IDs mismatch')
    grid=collections.defaultdict(dict)
    for row in review:
        item=data[row['id']]
        if row['source_id'] not in old or any(row[k]!=item[k] for k in ('source_id','family','query','condition')):
            raise ValueError('row metadata mismatch')
        if row['variant']!=item['instruction_variant'] or row['reference']!=item['expected'] or int(row['index'])!=records[row['id']]['index']:
            raise ValueError('row reference or record mismatch')
        if row['commitment'] not in ('Y','N','U','X','T'):raise ValueError('invalid commitment')
        if row['commitment']=='T':raise ValueError('technical missing not expected after inspect')
        prior=old[row['source_id']]
        if any(row[k]!=prior[k] for k in ('family','query','condition','reference')):raise ValueError('prior reference mismatch')
        if row['variant'] in grid[row['source_id']]:raise ValueError('duplicate pair')
        grid[row['source_id']][row['variant']]=row
    if len(grid)!=72 or any(set(g)!={'plain','decompose'} for g in grid.values()):raise ValueError('incomplete paired grid')
    all_rows=[dict(row,variant='baseline') for row in old.values()]+review
    def counts(rows):return dict(collections.Counter(category(r) for r in rows))
    grouped={}
    for variant in ('baseline','plain','decompose'):
        for family in ('number','category'):
            for section in ('single','dual_determinate','dual_split'):
                selected=[r for r in all_rows if r['variant']==variant and r['family']==family and
                          (r['condition'].startswith('single') if section=='single' else
                           r['condition'].startswith('dual_') and ((r['reference']=='U')==(section=='dual_split')))]
                grouped[f'{variant}/{family}/{section}']={'n':len(selected),'counts':counts(selected)}
    pairs={}
    for variant in ('plain','decompose'):
        for section in ('dual_determinate','dual_split'):
            source_ids=[k for k,r in old.items() if r['condition'].startswith('dual_') and ((r['reference']=='U')==(section=='dual_split'))]
            pairs[f'baseline_to_{variant}/{section}']=dict(collections.Counter(
                f'{category(old[k])}->{category(grid[k][variant])}' for k in source_ids))
    return {'old_files':len(oldfiles),'new_files':len(newfiles),'review_rows':len(review),'paired_source_inputs':len(grid),
            'groups':grouped,'pair_transitions':pairs}


if __name__=='__main__':print(json.dumps(analyze(),ensure_ascii=False,indent=2,sort_keys=True))
