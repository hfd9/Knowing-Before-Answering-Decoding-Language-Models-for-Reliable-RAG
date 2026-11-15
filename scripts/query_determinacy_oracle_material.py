#!/usr/bin/env python3
"""Build fresh synthetic development material for an oracle-world pipeline test."""
import json
from pathlib import Path
import query_determinacy_fresh_material as template

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/review/2026-11-15-query-determinacy-oracle-dev-v1/material.jsonl'
NUM=[('H01',13,21,9,25,17),('H02',38,26,22,42,32),('H03',47,55,43,59,51),
     ('H04',62,50,46,66,56),('H05',71,81,67,85,76),('H06',94,84,80,98,89)]
CAT=[('K01','A1','B2','C3','D4'),('K02','E5','F6','G7','H8'),('K03','J1','K2','L3','M4'),
     ('K04','N5','P6','Q7','R8'),('K05','S1','T2','V3','W4'),('K06','X5','Y6','Z7','A8')]
SUFFIX='请仅输出一个答案：是、否或无法确定。'


def build():
    before=(template.NUM,template.CAT,template.INSTRUCTIONS)
    try:
        template.NUM=NUM;template.CAT=CAT;template.INSTRUCTIONS={'format':SUFFIX}
        result=template.build()
    finally:
        template.NUM,template.CAT,template.INSTRUCTIONS=before
    if len(result)!=144 or len({x['id'] for x in result})!=144:raise ValueError('wrong material count')
    return result


def main():
    encoded=''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in build())
    if OUT.exists():
        if OUT.read_text(encoding='utf-8')!=encoded:raise ValueError('existing material differs')
        print('material matches')
    else:
        with OUT.open('x',encoding='utf-8') as f:f.write(encoded)
        print('created',OUT)


if __name__=='__main__':main()
