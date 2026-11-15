#!/usr/bin/env python3
"""Independently extract literal values from fixed extraction prompt text."""
import collections
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
MATERIAL=ROOT/'docs/review/2026-11-15-query-determinacy-world-extract-dev-v1/material.jsonl'
OLD=ROOT/'docs/review/2026-11-15-query-determinacy-oracle-dev-v1/material.jsonl'


def audit(path=MATERIAL):
    rows=[json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
    old={r['id']:r for r in map(json.loads,OLD.read_text(encoding='utf-8').splitlines())}
    if len(rows)!=24 or len({r['id'] for r in rows})!=24 or len({r['prompt'] for r in rows})!=24:raise ValueError('bad count')
    groups=collections.defaultdict(set)
    for row in rows:
        lines=row['prompt'].splitlines();source=old[row['source_id']]
        if len(lines)!=3 or lines[:2]!=source['prompt'].splitlines()[:2]:raise ValueError('source differs')
        if row['case']!=source['case'] or row['family']!=source['family'] or row['condition']!=source['condition']:
            raise ValueError('metadata differs')
        evidence=lines[1]
        if row['family']=='number':values=re.findall(r'(\d+)个单位',evidence)
        elif row['family']=='category':values=re.findall(r'“([A-Z]\d)”',evidence)
        else:raise ValueError('unknown family')
        if len(values)!=2 or values[0]==values[1] or values!=row['expected']:raise ValueError('literal values differ')
        if row['condition'] in groups[row['case']]:raise ValueError('duplicate case and form')
        groups[row['case']].add(row['condition'])
    if len(groups)!=12 or any(x!={'dual_sources','dual_alternatives'} for x in groups.values()):raise ValueError('incomplete case forms')
    return {'items':len(rows),'cases':len(groups),'families':dict(collections.Counter(x['family'] for x in rows))}


if __name__=='__main__':print(json.dumps(audit(),ensure_ascii=False,indent=2))
