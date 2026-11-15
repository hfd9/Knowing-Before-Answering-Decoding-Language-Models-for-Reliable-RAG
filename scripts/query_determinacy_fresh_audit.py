#!/usr/bin/env python3
"""Parse rendered fresh development prompts and verify the explicit answer sets."""
import collections
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
MATERIAL=ROOT/'docs/review/2026-11-15-query-determinacy-fresh-dev-v1/material.jsonl'


def audit(path=MATERIAL):
    rows=[json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
    if len(rows)!=192 or len({r['id'] for r in rows})!=192:raise ValueError('bad item count or duplicate')
    groups=collections.defaultdict(dict)
    for row in rows:
        lines=row['prompt'].splitlines()
        if len(lines)!=4 or not lines[2].startswith('问题：'):raise ValueError('prompt shape')
        evidence,question=lines[1],lines[2]
        dual=row['condition'].startswith('dual_')
        if dual and not all(s in evidence for s in ('恰好是这两个值之一','两种情况都有可能','没有其他信息')):
            raise ValueError('world conditions absent')
        if row['family']=='number':
            values=[int(s) for s in re.findall(r'(\d+)个单位',evidence)]
            matches=re.findall(r'大于(\d+)',question)
            if len(matches)!=1:raise ValueError('threshold')
            answers=[v>int(matches[0]) for v in values]
        elif row['family']=='category':
            if '单个原子标签' not in evidence or '不同代码互不相同' not in evidence:raise ValueError('missing label axiom')
            values=re.findall(r'“([^”]+)”',evidence);choices=re.findall(r'“([^”]+)”',question)
            if len(choices) not in (1,2):raise ValueError('bad choice list')
            answers=[v in choices for v in values]
        else:raise ValueError('bad family')
        if len(values)!=(2 if dual else 1):raise ValueError('bad world count')
        expected_worlds={row['world_a'],row['world_b']} if dual else {row['world_a' if row['condition']=='single_a' else 'world_b']}
        if set(values)!=expected_worlds:raise ValueError('bad world values')
        derived='U' if len(set(answers))>1 else ('Y' if answers[0] else 'N')
        if row['expected']!=derived:raise ValueError('reference differs from rendered problem')
        if dual and derived!={'same_yes':'Y','same_no':'N','split':'U'}[row['query']]:raise ValueError('query type')
        key=(row['case'],row['query'],row['instruction_variant'])
        if row['condition'] in groups[key]:raise ValueError('duplicate condition')
        groups[key][row['condition']]=(question,derived,row['world_answers'])
    wanted={'single_a','single_b','dual_sources','dual_alternatives'}
    if len(groups)!=48:raise ValueError('bad grid size')
    for grid in groups.values():
        if set(grid)!=wanted or len({x[0] for x in grid.values()})!=1:raise ValueError('grid mismatch')
        correct=[grid['single_a'][1],grid['single_b'][1]]
        if any(item[2]!=correct for item in grid.values()):raise ValueError('world mapping mismatch')
    return {'items':len(rows),'cases':len({r['case'] for r in rows}),'groups':len(groups),
            'variants':dict(collections.Counter(r['instruction_variant'] for r in rows))}


if __name__=='__main__':print(json.dumps(audit(),ensure_ascii=False,indent=2))
