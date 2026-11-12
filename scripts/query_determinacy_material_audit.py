#!/usr/bin/env python3
"""Read-only, fail-closed audit of the supplied 144-item development pilot."""
import collections
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MATERIAL = ROOT / 'docs/查询可判定性_探索先导包'
FILES = ('README.md', 'prompts.jsonl', 'key.csv')
DUAL_PREFIX = '两份来源没有优先顺序。题设保证该字段只有一个实际值，恰好是下列两个不同值之一。'
SINGLE_PREFIX = '下面只考察一个假设情况。请把给定值视为该字段的实际值。'


def check(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def branch_answers(text, family):
    lines = text.splitlines()
    check(lines[0] == DUAL_PREFIX, 'world assumption missing')
    sources = {}
    for line in lines:
        match = re.fullmatch(r'来源([甲乙])：(.+)登记值为(.+)。', line)
        if match:
            side, field, value = match.groups()
            check(side not in sources, 'duplicate source')
            sources[side] = (field, value)
    check(set(sources) == {'甲', '乙'}, 'source parsing failed')
    check(sources['甲'][0] == sources['乙'][0] and sources['甲'][1] != sources['乙'][1], 'source fields/values inconsistent')
    questions = [line for line in lines if line.startswith('问题：')]
    check(len(questions) == 1, 'expected one question')
    question = questions[0]
    if family == '数值比较':
        match = re.fullmatch(r'问题：(.+)是否(大于|小于)(\d+)([^\d。？]+)？', question)
        check(match is not None, 'numeric question mismatch')
        field, op, target, unit = match.groups()
        check(field == sources['甲'][0], 'question asks another field')
        values = {}
        for side, (_, value) in sources.items():
            m = re.fullmatch(r'(\d+)([^\d]+)', value)
            check(m is not None and m.group(2) == unit, 'value or unit mismatch')
            values[side] = int(m.group(1))
        threshold = int(target)
        check(all(v != threshold for v in values.values()), 'boundary equality')
        answers = {side: '是' if (v > threshold if op == '大于' else v < threshold) else '否'
                   for side, v in values.items()}
    else:
        check(family == '类别规则', 'unknown family')
        match = re.fullmatch(r'问题：(.+)需要(.+)吗？', question)
        check(match is not None and sources['甲'][0] == match.group(1) + '的包装代码', 'category field mismatch')
        columns = ['蓝色外签', '防潮内袋', '双排封条']
        check(match.group(2) in columns and '代码｜' + '｜'.join(columns) in lines, 'table header mismatch')
        col = columns.index(match.group(2)) + 1
        table = {}
        for line in lines:
            parts = line.split('｜')
            if len(parts) == 4 and all(x in ('是', '否') for x in parts[1:]):
                check(parts[0] not in table, 'duplicate table code')
                table[parts[0]] = parts
        check(len(table) == 4 and all(v[1] in table for v in sources.values()), 'incomplete table')
        answers = {side: table[value][col] for side, (_, value) in sources.items()}
    return sources, answers


def audit():
    check(set(p.name for p in MATERIAL.iterdir() if p.is_file()) == set(FILES), 'unexpected material files')
    before = {name: sha(MATERIAL / name) for name in FILES}
    with (MATERIAL / 'prompts.jsonl').open(encoding='utf-8') as file:
        prompt_rows = [json.loads(line) for line in file]
    with (MATERIAL / 'key.csv').open(encoding='utf-8-sig', newline='') as file:
        keys = list(csv.DictReader(file))
    check(len(prompt_rows) == len(keys) == 144, 'expected 144 rows')
    check(all(set(r) == {'id', 'prompt'} and isinstance(r['prompt'], str) for r in prompt_rows), 'invalid prompt row')
    prompts = {r['id']: r['prompt'] for r in prompt_rows}
    check(len(prompts) == len({r['id'] for r in keys}) == 144 and set(prompts) == {r['id'] for r in keys}, 'IDs mismatch')
    grouped = collections.defaultdict(dict)
    for row in keys:
        slot = (row['材料形式'], row['单来源取值'])
        group = grouped[(row['底题'], row['问题'])]
        check(slot not in group, 'duplicate condition')
        group[slot] = row
    check(len(grouped) == 36 and len({case for case, _ in grouped}) == 12, 'base grid mismatch')
    expected_slots = {('来源断言', ''), ('分列候选', ''), ('单来源假设', '甲'), ('单来源假设', '乙')}
    outcome_counts = collections.Counter()
    family_counts = collections.Counter()
    case_results = collections.defaultdict(list)
    case_bodies = {}
    case_families = {}
    case_orders = {}
    split_sides = collections.Counter()
    for (case, question_id), group in grouped.items():
        check(set(group) == expected_slots, f'{case}/{question_id}: incomplete conditions')
        a, c = group[('来源断言', '')], group[('分列候选', '')]
        family = a['任务族']
        check(all(row['任务族'] == family for row in group.values()), 'family mismatch')
        assertion, candidate = prompts[a['id']], prompts[c['id']]
        check(assertion.count('登记值') == 2 and candidate == assertion.replace('登记值', '候选值'), 'wording pair mismatch')
        sources, answers = branch_answers(assertion, family)
        order = ''.join(re.findall(r'^来源([甲乙])：', assertion, re.M))
        check(order in ('甲乙', '乙甲') and a['来源顺序'] == c['来源顺序'] == order, 'order mismatch')
        outcome = answers['甲'] if answers['甲'] == answers['乙'] else '无法唯一确定'
        body = '\n'.join(line for line in assertion.splitlines() if not line.startswith('问题：'))
        check(case not in case_bodies or case_bodies[case] == body, 'same case has inconsistent materials')
        case_bodies[case], case_families[case], case_orders[case] = body, family, order
        if outcome == '无法唯一确定':
            split_sides[(family, answers['甲'])] += 1
        for row in group.values():
            check(row['甲分支真值'] == answers['甲'] and row['乙分支真值'] == answers['乙'], 'branch reference mismatch')
            expected = answers[row['单来源取值']] if row['材料形式'] == '单来源假设' else outcome
            check(row['参考结论'] == expected, 'reference answer mismatch')
        lines = assertion.splitlines()
        for side in ('甲', '乙'):
            row = group[('单来源假设', side)]
            field, value = sources[side]
            expected_lines = [SINGLE_PREFIX, f'来源{side}：在这个假设中，{field}为{value}。']
            expected_lines.extend(line for line in lines[1:] if not line.startswith(('来源甲：', '来源乙：')))
            check(prompts[row['id']] == '\n'.join(expected_lines) and row['来源顺序'] == side, 'single-source mismatch')
        outcome_counts[outcome] += 1
        family_counts[family] += 1
        case_results[case].append(outcome)
    check(all(sorted(x) == sorted(['是', '否', '无法唯一确定']) for x in case_results.values()), 'case outcomes mismatch')
    check(family_counts == {'数值比较': 18, '类别规则': 18}, 'family balance mismatch')
    order_counts = collections.Counter((case_families[case], case_orders[case]) for case in case_results)
    check(all(order_counts[(family, order)] == 3 for family in ('数值比较', '类别规则') for order in ('甲乙', '乙甲')), 'source order imbalance')
    check(all(split_sides[(family, value)] == 3 for family in ('数值比较', '类别规则') for value in ('是', '否')), 'split answer imbalance')
    check(before == {name: sha(MATERIAL / name) for name in FILES}, 'materials changed during audit')
    return {'files_sha256': before, 'prompts': 144, 'cases': len(case_results), 'questions': len(grouped),
            'condition_rows': {'来源断言': 36, '分列候选': 36, '单来源假设': 72},
            'question_outcomes': dict(outcome_counts), 'questions_by_family': dict(family_counts),
            'order_balance_per_family': {'甲乙': 3, '乙甲': 3}, 'split_source_jia_yes_no_per_family': {'是': 3, '否': 3},
            'branch_and_reference_checks': 144, 'dual_pairs': 36, 'single_source_checks': 72,
            'read_only': True, 'independent_blind_semantic_review': False}


if __name__ == '__main__':
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
