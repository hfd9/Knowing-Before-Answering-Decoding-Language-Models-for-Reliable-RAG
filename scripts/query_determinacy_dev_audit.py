#!/usr/bin/env python3
"""Independently parse rendered development prompts to check finite-world keys."""
import collections
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
MATERIAL=ROOT/'docs/review/2026-11-15-query-determinacy-development-v1/material.jsonl'


def audit(path=MATERIAL):
    rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    if len(rows)!=72 or len({r['id'] for r in rows})!=72: raise ValueError('wrong number or duplicate IDs')
    grid=collections.defaultdict(dict)
    for row in rows:
        lines=row['prompt'].splitlines()
        if len(lines)!=4 or not lines[2].startswith('问题：'): raise ValueError('invalid prompt structure')
        evidence,question=lines[1],lines[2]
        if row['condition'].startswith('dual_'):
            if '恰好是这两个值之一' not in evidence or '两种情况都有可能' not in evidence or '没有其他信息' not in evidence:
                raise ValueError('missing world conditions')
        if row['family']=='number':
            values=[int(x) for x in re.findall(r'(\d+)个单位',evidence)]
            matches=re.findall(r'大于(\d+)',question)
            if len(matches)!=1: raise ValueError('invalid numeric question')
            threshold=int(matches[0]); truth=[v>threshold for v in values]
        elif row['family']=='category':
            values=re.findall(r'“([^”]+)”',evidence)
            choices=re.findall(r'“([^”]+)”',question)
            if not choices or len(choices)>2: raise ValueError('invalid category question')
            truth=[value in choices for value in values]
        else: raise ValueError('unknown family')
        dual=row['condition'].startswith('dual_')
        if len(values)!=(2 if dual else 1): raise ValueError('incorrect number of worlds')
        if dual:
            if set(values)!={row['world_a'],row['world_b']} or len(set(values))!=2: raise ValueError('wrong worlds')
        elif values[0]!=row['world_a' if row['condition']=='single_a' else 'world_b']:
            raise ValueError('wrong single world')
        answer=('U' if len(set(truth))==2 else ('Y' if truth[0] else 'N'))
        if row['expected']!=answer: raise ValueError('reference differs from rendered prompt')
        expected_dual={'same_yes':'Y','same_no':'N','split':'U'}[row['query']]
        if dual and answer!=expected_dual: raise ValueError('query family is incorrect')
        if (row['case'],row['query']) in grid and row['condition'] in grid[(row['case'],row['query'])]:
            raise ValueError('duplicate condition')
        grid[(row['case'],row['query'])][row['condition']]=(question,answer,row['world_answers'])
    wanted={'single_a','single_b','dual_sources','dual_alternatives'}
    if len(grid)!=18 or any(set(g)!=wanted or len({v[0] for v in g.values()})!=1 for g in grid.values()):
        raise ValueError('condition grid or questions mismatch')
    for g in grid.values():
        expected=[g['single_a'][1],g['single_b'][1]]
        if any(v[2]!=expected for v in g.values()): raise ValueError('world answer mapping mismatch')
    return {'rows':len(rows),'cases':len({r['case'] for r in rows}),
            'questions':len(grid),'conditions':dict(collections.Counter(r['condition'] for r in rows)),
            'families':dict(collections.Counter(r['family'] for r in rows))}


if __name__=='__main__': print(json.dumps(audit(),ensure_ascii=False,indent=2))
