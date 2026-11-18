#!/usr/bin/env python3
"""Author-generated controlled development material; no model calls."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/review/2026-11-18-two-case-cpu-v1'
NUMERICS = [
    ('R8C2', '虚构储罐的单次补水量', '升', 17, 43, 8, 60, 29),
    ('T4L7', '虚构转盘的单次转速', '转', 72, 28, 16, 90, 50),
    ('B6Q9', '虚构电缆的标记长度', '厘米', 26, 64, 15, 81, 45),
    ('F2J8', '虚构装箱批次的板片数量', '片', 83, 35, 21, 99, 57),
    ('H5P3', '虚构反应室的加热时长', '分钟', 42, 76, 31, 94, 60),
]
CATEGORIES = [
    ('W2A8', '虚构货箱的本次封装代码', 'A42', 'B57', '密封防尘', '露天堆放', '短途运输'),
    ('J8E4', '虚构元件的本次包装代码', 'C18', 'D63', '隔热存储', '高压浸泡', '快速拆封'),
    ('P7S6', '虚构容器的本次保护代码', 'E29', 'F74', '遮光保存', '明火烘烤', '常温陈列'),
    ('V5D2', '虚构样盒的本次运输代码', 'G31', 'H86', '防震运输', '水下存放', '折叠收纳'),
    ('Y4N8', '虚构展品的本次安放代码', 'J47', 'K92', '室内存放', '直接冲洗', '悬挂陈列'),
]


def qid(case, text):
    return 'Q' + hashlib.sha256((case + '\0' + text).encode()).hexdigest()[:12]


def numeric(row):
    case, subject, unit, first, second, low, high, middle = row
    if not (low < min(first, second) < middle < max(first, second) < high):
        raise ValueError('numeric construction invalid')
    a = f'来源甲写：{subject}是{first}{unit}。'
    b = f'来源乙写：{subject}是{second}{unit}。'
    background = (f'{subject}只有一个整数值。{a}{b}两份记载针对同一对象和同一次记录，彼此冲突。'
                  '题设规定实际值恰为这两个记载值之一，两种情况均可能，无法确定哪条记载正确。')
    questions, labels = [], {}
    for threshold in (low, high, middle):
        text = f'{subject}是否超过{threshold}{unit}？'
        key = qid(case, text)
        vals = ['Y' if value > threshold else 'N' for value in (first, second)]
        labels[key] = {'world_answers': vals, 'final': vals[0] if vals[0] == vals[1] else 'U',
                       'rationale': f'分别比较{first}、{second}与{threshold}。'}
        questions.append({'id': key, 'text': text})
    return {'id': case, 'domain': 'integer', 'background': background,
            'questions': sorted(questions, key=lambda x: x['id'])}, {
                'worlds': [{'value': str(first), 'source_quote': a}, {'value': str(second), 'source_quote': b}],
                'questions': labels}


def category(row):
    case, subject, first, second, both, neither, split = row
    a = f'来源甲写：{subject}是{first}。'
    b = f'来源乙写：{subject}是{second}。'
    first_yes = case in ('W2A8', 'P7S6', 'Y4N8')
    ra = f'{first}适合{both}，不适合{neither}，' + ('' if first_yes else '不') + f'适合{split}'
    rb = f'{second}适合{both}，不适合{neither}，' + ('不' if first_yes else '') + f'适合{split}'
    background = (f'{subject}只有一个代码。{a}{b}两份记载针对同一对象和同一次记录，彼此冲突。'
                  '题设规定实际代码恰为这两个记载代码之一，两种情况均可能，无法确定哪条记载正确。'
                  f'规则表明确：{ra}；{rb}。')
    questions, labels = [], {}
    split_values = ['Y', 'N'] if first_yes else ['N', 'Y']
    for attribute, vals in ((both, ['Y', 'Y']), (neither, ['N', 'N']), (split, split_values)):
        text = f'按规则表，该对象是否适合{attribute}？'
        key = qid(case, text)
        labels[key] = {'world_answers': vals, 'final': vals[0] if vals[0] == vals[1] else 'U',
                       'rationale': f'分别依据{first}与{second}的{attribute}规则。'}
        questions.append({'id': key, 'text': text})
    return {'id': case, 'domain': 'identifier', 'background': background,
            'questions': sorted(questions, key=lambda x: x['id'])}, {
                'worlds': [{'value': first, 'source_quote': a, 'rule_quote': ra},
                           {'value': second, 'source_quote': b, 'rule_quote': rb}], 'questions': labels}


def build():
    public = json.loads((BASE / 'public.json').read_bytes())
    reference = json.loads((BASE / 'reference.json').read_bytes())
    if len(public['cases']) != 2 or len(reference['cases']) != 2:
        raise ValueError('unexpected two-case input')
    for item in NUMERICS:
        case, ref = numeric(item)
        public['cases'].append(case)
        reference['cases'][case['id']] = ref
    for item in CATEGORIES:
        case, ref = category(item)
        public['cases'].append(case)
        reference['cases'][case['id']] = ref
    if len(public['cases']) != 12 or len(reference['cases']) != 12:
        raise ValueError('unexpected number of cases')
    public['schema'] = 'two_world_development12_public_v1'
    reference['schema'] = 'two_world_development12_reference_v1'
    return public, reference


def write():
    public, reference = build()
    for name, obj in (('public-12-v2.json', public), ('reference-12-v2.json', reference)):
        with (BASE / name).open('x', encoding='utf-8') as stream:
            json.dump(obj, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write('\n')


if __name__ == '__main__':
    write()
