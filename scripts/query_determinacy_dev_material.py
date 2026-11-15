#!/usr/bin/env python3
"""Generate a small, exposed finite-world development set; no model calls."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/review/2026-11-15-query-determinacy-development-v1/material.jsonl'

CASES = [
    {'id':'N01','family':'number','label':'青色容器','a':12,'b':20,'low':8,'high':24,'middle':16},
    {'id':'N02','family':'number','label':'琥珀容器','a':27,'b':17,'low':13,'high':31,'middle':22},
    {'id':'N03','family':'number','label':'银色容器','a':34,'b':42,'low':30,'high':46,'middle':38},
    {'id':'C01','family':'category','label':'青色徽记','a':'松','b':'竹','other':['梅','兰']},
    {'id':'C02','family':'category','label':'琥珀徽记','a':'云','b':'星','other':['月','日']},
    {'id':'C03','family':'category','label':'银色徽记','a':'山','b':'川','other':['林','海']},
]


def construct():
    rows=[]
    for case in CASES:
        a,b=case['a'],case['b']
        if case['family']=='number':
            queries=[('same_yes',f"这个数值是否大于{case['low']}？",lambda x: x>case['low']),
                     ('same_no',f"这个数值是否大于{case['high']}？",lambda x: x>case['high']),
                     ('split',f"这个数值是否大于{case['middle']}？",lambda x: x>case['middle'])]
            datum=lambda value:f'{value}个单位'
            fact='记录的数值'
        else:
            queries=[('same_yes',f'这个类别是否属于“{a}”或“{b}”？',lambda x: x in (a,b)),
                     ('same_no',f"这个类别是否属于“{case['other'][0]}”或“{case['other'][1]}”？",lambda x: x in case['other']),
                     ('split',f'这个类别是否为“{a}”？',lambda x: x==a)]
            datum=lambda value:f'“{value}”'
            fact='记录的类别'
        values=(a,b) if case['id'][-1] in ('1','3') else (b,a)
        for qid,question,evaluate in queries:
            answers=['Y' if evaluate(x) else 'N' for x in (a,b)]
            for condition in ('single_a','single_b','dual_sources','dual_alternatives'):
                if condition.startswith('single'):
                    value=a if condition=='single_a' else b
                    evidence=f'在本题中，假设{case["label"]}{fact}确定为{datum(value)}。'
                    ref=answers[0 if condition=='single_a' else 1]
                elif condition=='dual_sources':
                    evidence=(f'资料甲称{case["label"]}{fact}为{datum(values[0])}；资料乙称其为{datum(values[1])}。'
                              '题设保证真实情况恰好是这两个值之一，两种情况都有可能，且没有其他信息可区分哪份资料正确。')
                    ref=answers[0] if answers[0]==answers[1] else 'U'
                else:
                    evidence=(f'{case["label"]}{fact}有两个可能：{datum(values[0])}或{datum(values[1])}。'
                              '题设保证真实情况恰好是这两个值之一，两种情况都有可能，且没有其他信息可以区分这两种情况。')
                    ref=answers[0] if answers[0]==answers[1] else 'U'
                prompt=f'以下是虚构情境，请仅依据题设回答。\n{evidence}\n问题：{question}\n请简短回答；如无法唯一确定，请说明。'
                rows.append({'id':f"{case['id']}_{qid}_{condition}",'case':case['id'],'family':case['family'],
                             'query':qid,'condition':condition,'world_a':a,'world_b':b,
                             'world_answers':answers,'expected':ref,'prompt':prompt})
    return rows


def main():
    rows=construct()
    assert len(rows)==72 and len({r['id'] for r in rows})==72
    output=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows)
    if OUT.exists():
        if OUT.read_text(encoding='utf-8')!=output: raise ValueError('existing material differs; never overwrite')
        print('existing material matches')
    else:
        with OUT.open('x',encoding='utf-8') as f:f.write(output)
        print('created',OUT)


if __name__=='__main__': main()
