#!/usr/bin/env python3
"""Build unique source-text extraction prompts from an exposed synthetic set."""
import json
from pathlib import Path
import re
import query_determinacy_template_world_extraction as template

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'docs/review/2026-11-15-query-determinacy-oracle-dev-v1/material.jsonl'
OUT=ROOT/'docs/review/2026-11-15-query-determinacy-world-extract-dev-v1/material.jsonl'
INSTRUCTION=('请按文本中出现的先后顺序，只输出两个可能值组成的JSON字符串数组。'
             '数值仅输出数字，代码仅输出字母和数字，不要添加解释。')


def build():
    original=[json.loads(x) for x in OLD.read_text(encoding='utf-8').splitlines()]
    selected=[r for r in original if r['query']=='same_yes' and r['condition'] in ('dual_sources','dual_alternatives')]
    if len(selected)!=24:raise ValueError('expected 12 cases and two source forms')
    output=[]
    for row in selected:
        branches=template.branch_prompts(row['prompt']);values=[]
        for branch in branches:
            found=re.search(r'确定为([^。]+)。',branch.splitlines()[1])
            if not found:raise ValueError('cannot parse branch value')
            value=found.group(1)
            if row['family']=='number':
                if not re.fullmatch(r'\d+个单位',value):raise ValueError('invalid number')
                values.append(value[:-3])
            else:
                if not re.fullmatch(r'“[A-Z]\d”',value):raise ValueError('invalid code')
                values.append(value[1:-1])
        if len(values)!=2 or values[0]==values[1]:raise ValueError('invalid candidate pair')
        old_lines=row['prompt'].splitlines()
        prompt='\n'.join((old_lines[0],old_lines[1],INSTRUCTION))
        output.append({'id':row['case']+'__'+row['condition']+'__extract',
                       'source_id':row['id'],'case':row['case'],'family':row['family'],
                       'condition':row['condition'],'expected':values,'prompt':prompt})
    return output


def main():
    rows=build()
    if len({x['id'] for x in rows})!=24 or len({x['prompt'] for x in rows})!=24:raise ValueError('duplicate input')
    encoded=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows)
    if OUT.exists():
        if OUT.read_text(encoding='utf-8')!=encoded:raise ValueError('existing material differs')
        print('material matches')
    else:
        with OUT.open('x',encoding='utf-8') as f:f.write(encoded)
        print('created',OUT)


if __name__=='__main__':main()
