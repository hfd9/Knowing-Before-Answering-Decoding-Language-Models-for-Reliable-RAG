#!/usr/bin/env python3
"""Check the 96 exposed paraphrase inputs against old questions and finite worlds."""
import collections
import json
import re
from pathlib import Path

import query_determinacy_oracle_run as oracle
import query_determinacy_paraphrase_study as study
import query_determinacy_template_world_extraction as template

ROOT = Path(__file__).resolve().parents[1]
MATERIAL = ROOT / 'docs/review/2026-11-17-query-determinacy-paraphrase-dev-v1/material.jsonl'
PHRASES = {
    ('dual_sources', 1): ('真实值只能是以上两个值之一', '二者均有可能', '无法判断哪份档案正确'),
    ('dual_sources', 2): ('真实值恰好是这两个值之一', '两个值都可能', '不能判定哪份记录正确'),
    ('dual_sources', 3): ('真实值必为其中之一', '两种情况均有可能', '没有信息判断哪份记载正确'),
    ('dual_alternatives', 1): ('只能取', '两种情况均有可能', '没有信息指出究竟是哪一个'),
    ('dual_alternatives', 2): ('真实值不是', '两者均可能', '没有额外依据选定其中一个'),
    ('dual_alternatives', 3): ('可能值恰好是', '两种可能都存在', '不能作进一步区分'),
}


def audit():
    rows = [json.loads(x) for x in MATERIAL.read_text(encoding='utf-8').splitlines()]
    if rows != study.build():
        raise ValueError('candidate material differs from construction')
    old = oracle.inputs()
    groups = collections.Counter()
    for row in rows:
        if row['kind'] != 'extract':
            source = old[row['id'].removesuffix('__paraphrase')]
            lines = row['prompt'].splitlines()
            old_lines = source['prompt'].splitlines()
            if len(lines) != 4 or lines[0] != old_lines[0] or lines[2:] != old_lines[2:]:
                raise ValueError('question or outer template changed')
            if row['expected'] != source['expected'] or row['query'] != source['query']:
                raise ValueError('reference or query changed')
            groups['questions'] += 1
            continue
        evidence = row['prompt'].splitlines()[1]
        subject = '虚构样本' + row['case'] + '的记录' + ('数值' if row['family'] == 'number' else '代码')
        if evidence.count(subject) != 1 or (template.AXIOM in evidence) != (row['family'] == 'category'):
            raise ValueError('subject or atomic axiom mismatch')
        regex = r'(\d+)个单位' if row['family'] == 'number' else r'“([A-Z]\d)”'
        if re.findall(regex, evidence) != row['expected']:
            raise ValueError('world values or order differ')
        if not all(x in evidence for x in PHRASES[(row['condition'], row['style'])]):
            raise ValueError('world/exhaustiveness phrase missing')
        groups['backgrounds'] += 1
        groups[f"{row['family']}/{row['condition']}/{row['style']}"] += 1
    if groups['questions'] != 72 or groups['backgrounds'] != 24:
        raise ValueError('incorrect planned count')
    return dict(groups)


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, indent=2, sort_keys=True))
