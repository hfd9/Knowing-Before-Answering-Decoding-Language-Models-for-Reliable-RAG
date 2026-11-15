#!/usr/bin/env python3
"""Post-hoc oracle-world composition of previously reviewed single-world answers."""
import collections
import csv
import json
from pathlib import Path

import query_determinacy_source_results as source

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'docs/review/2026-11-15-query-determinacy-fresh-results-v1'
NEW=ROOT/'docs/review/2026-11-15-query-determinacy-source-order-results-v1'


def combine(a,b):
    if 'T' in (a,b):return 'T'
    if a not in ('Y','N') or b not in ('Y','N'):return 'X'
    return a if a==b else 'U'


def classify(code,reference):
    if code=='T':return 'technical_missing'
    if code=='X':return 'unknown'
    if code==reference:return 'correct'
    if code=='U':return 'overreserve'
    if reference=='U':return 'unsupported_choice'
    return 'wrong'


def evaluate():
    source.analyze()  # Check both immutable archives and explicitly recorded old correction.
    rows=source.readcsv(OLD/'review.csv')
    correction=source.readcsv(NEW/'prior-correction.csv')
    if len(correction)!=1:raise ValueError('missing recorded correction')
    corrections={c['id']:c for c in correction}
    grid=collections.defaultdict(dict)
    for row in rows:
        if row['id'] in corrections:
            fix=corrections[row['id']]
            if row['commitment']!=fix['old_commitment']:raise ValueError('correction mismatch')
            row=dict(row,commitment=fix['corrected_commitment'])
        key=(row['case'],row['query'],row['variant'])
        if row['condition'] in grid[key]:raise ValueError('duplicate condition')
        grid[key][row['condition']]=row
    result=[]
    for (case,query,variant),g in sorted(grid.items()):
        if set(g)!={'single_a','single_b','dual_sources','dual_alternatives'}:raise ValueError('incomplete problem')
        ref=g['dual_sources']['reference']
        if ref!=g['dual_alternatives']['reference']:raise ValueError('dual references differ')
        a,b=g['single_a']['commitment'],g['single_b']['commitment']
        combined=combine(a,b)
        result.append({'case':case,'query':query,'variant':variant,'family':g['single_a']['family'],
                       'single_a_id':g['single_a']['id'],'single_a':a,'single_b_id':g['single_b']['id'],'single_b':b,
                       'reference':ref,'combined':combined,'combined_class':classify(combined,ref),
                       'sources_id':g['dual_sources']['id'],'sources':g['dual_sources']['commitment'],
                       'sources_class':classify(g['dual_sources']['commitment'],ref),
                       'alternatives_id':g['dual_alternatives']['id'],'alternatives':g['dual_alternatives']['commitment'],
                       'alternatives_class':classify(g['dual_alternatives']['commitment'],ref)})
    if len(result)!=48:raise ValueError('unexpected problem count')
    summary={}
    for variant in ('plain','decompose'):
        selected=[r for r in result if r['variant']==variant]
        if len(selected)!=24:raise ValueError('unexpected per-variant count')
        summary[variant]={'planned_questions':24}
        for method in ('combined','sources','alternatives'):
            summary[variant][method]=dict(collections.Counter(r[method+'_class'] for r in selected))
        for section in ('same','split'):
            section_rows=[r for r in selected if (r['reference']=='U')==(section=='split')]
            summary[variant][section]={method:dict(collections.Counter(r[method+'_class'] for r in section_rows)) for method in ('combined','sources','alternatives')}
    return result,summary


if __name__=='__main__':
    _,summary=evaluate();print(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True))
