#!/usr/bin/env python3
"""Independently parse 144 formatted finite-world development inputs."""
import collections
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
MATERIAL=ROOT/'docs/review/2026-11-15-query-determinacy-oracle-dev-v1/material.jsonl'


def audit(path=MATERIAL):
    rows=[json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
    if len(rows)!=144 or len({r['id'] for r in rows})!=144:raise ValueError('bad row count')
    grid=collections.defaultdict(dict)
    for row in rows:
        lines=row['prompt'].splitlines()
        if len(lines)!=4 or lines[-1]!='请仅输出一个答案：是、否或无法确定。':raise ValueError('prompt shape or output instruction')
        evidence,question=lines[1],lines[2];dual=row['condition'].startswith('dual_')
        if dual and not all(x in evidence for x in ('恰好是这两个值之一','两种情况都有可能','没有其他信息')):
            raise ValueError('world conditions missing')
        if row['family']=='number':
            values=[int(x) for x in re.findall(r'(\d+)个单位',evidence)]
            thresholds=re.findall(r'大于(\d+)',question)
            if len(thresholds)!=1:raise ValueError('threshold missing')
            answers=[v>int(thresholds[0]) for v in values]
        elif row['family']=='category':
            if '单个原子标签' not in evidence or '不同代码互不相同' not in evidence:raise ValueError('atomic axiom missing')
            values=re.findall(r'“([^”]+)”',evidence); choices=re.findall(r'“([^”]+)”',question)
            if len(choices) not in (1,2):raise ValueError('invalid choices')
            answers=[v in choices for v in values]
        else:raise ValueError('family')
        if len(values)!=(2 if dual else 1):raise ValueError('world count')
        worlds={row['world_a'],row['world_b']} if dual else {row['world_a' if row['condition']=='single_a' else 'world_b']}
        if set(values)!=worlds:raise ValueError('world mismatch')
        answer='U' if len(set(answers))>1 else ('Y' if answers[0] else 'N')
        if answer!=row['expected']:raise ValueError('rendered answer mismatch')
        if dual and answer!={'same_yes':'Y','same_no':'N','split':'U'}[row['query']]:raise ValueError('wrong query kind')
        key=(row['case'],row['query'])
        if row['condition'] in grid[key]:raise ValueError('duplicate condition')
        grid[key][row['condition']]=(question,answer,row['world_answers'])
    if len(grid)!=36:raise ValueError('wrong grid count')
    for group in grid.values():
        if set(group)!={'single_a','single_b','dual_sources','dual_alternatives'} or len({x[0] for x in group.values()})!=1:
            raise ValueError('missing or different question')
        answers=[group['single_a'][1],group['single_b'][1]]
        if any(x[2]!=answers for x in group.values()):raise ValueError('world mapping differs')
    return {'count':len(rows),'cases':len({r['case'] for r in rows}),'questions':len(grid)}


if __name__=='__main__':print(json.dumps(audit(),ensure_ascii=False,indent=2))
