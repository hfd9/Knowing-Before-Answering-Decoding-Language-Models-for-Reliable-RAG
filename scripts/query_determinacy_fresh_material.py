#!/usr/bin/env python3
"""Generate fresh, exposed development items with explicit atomic labels."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/review/2026-11-15-query-determinacy-fresh-dev-v1/material.jsonl'
NUM=[('F01',11,19,7,23,15),('F02',28,18,14,32,23),('F03',31,41,27,45,36),('F04',54,44,40,58,49)]
CAT=[('G01','M7','Q2','B4','Z8'),('G02','H3','K9','T5','V6'),
     ('G03','P8','D2','L7','W4'),('G04','J6','S3','X9','N5')]
INSTRUCTIONS={'plain':'请简短回答。','decompose':'请逐一判断题设允许的每个可能值对问题的答案，再给出最终结论。'}


def build():
    result=[]
    for family,cases in [('number',NUM),('category',CAT)]:
        for case,a,b,x,y,*z in cases:
            if family=='number':
                q=[('same_yes',f'这个数值是否大于{x}？',lambda value:value>x),
                   ('same_no',f'这个数值是否大于{y}？',lambda value:value>y),
                   ('split',f'这个数值是否大于{z[0]}？',lambda value:value>z[0])]
                datum=lambda v:f'{v}个单位'
                prefix=f'虚构样本{case}的记录数值'
                axiom=''
            else:
                q=[('same_yes',f'该代码是否在集合{{“{a}”，“{b}”}}中？',lambda value:value in (a,b)),
                   ('same_no',f'该代码是否在集合{{“{x}”，“{y}”}}中？',lambda value:value in (x,y)),
                   ('split',f'该代码是否等于“{a}”？',lambda value:value==a)]
                datum=lambda v:f'“{v}”'
                prefix=f'虚构样本{case}的记录代码'
                axiom='代码是单个原子标签；不同代码互不相同，不存在包含或同义关系。'
            values=(a,b) if int(case[-1])%2 else (b,a)
            for query,question,truth in q:
                answers=['Y' if truth(v) else 'N' for v in (a,b)]
                for condition in ('single_a','single_b','dual_sources','dual_alternatives'):
                    if condition.startswith('single'):
                        value=a if condition=='single_a' else b
                        evidence=f'假设{prefix}确定为{datum(value)}。'
                        expected=answers[0 if condition=='single_a' else 1]
                    elif condition=='dual_sources':
                        evidence=(f'资料甲称{prefix}为{datum(values[0])}；资料乙称其为{datum(values[1])}。'
                                  '题设保证真实情况恰好是这两个值之一，两种情况都有可能，且没有其他信息可区分哪份资料正确。')
                        expected=answers[0] if answers[0]==answers[1] else 'U'
                    else:
                        evidence=(f'{prefix}有两个可能：{datum(values[0])}或{datum(values[1])}。'
                                  '题设保证真实情况恰好是这两个值之一，两种情况都有可能，且没有其他信息可以区分这两种情况。')
                        expected=answers[0] if answers[0]==answers[1] else 'U'
                    for variant,instruction in INSTRUCTIONS.items():
                        prompt=f'以下是虚构情境，请仅依据题设回答。\n{axiom}{evidence}\n问题：{question}\n{instruction}'
                        result.append({'id':f'{case}_{query}_{condition}__{variant}','case':case,'family':family,
                                       'query':query,'condition':condition,'instruction_variant':variant,
                                       'world_a':a,'world_b':b,'world_answers':answers,'expected':expected,'prompt':prompt})
    return result


def main():
    rows=build();assert len(rows)==192 and len({r['id'] for r in rows})==192
    encoded=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
    if OUT.exists():
        if OUT.read_text(encoding='utf-8')!=encoded:raise ValueError('existing material differs')
        print('material matches')
    else:
        with OUT.open('x',encoding='utf-8') as f:f.write(encoded)
        print('created',OUT)


if __name__=='__main__':main()
