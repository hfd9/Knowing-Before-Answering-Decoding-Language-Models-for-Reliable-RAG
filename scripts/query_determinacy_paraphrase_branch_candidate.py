#!/usr/bin/env python3
"""Strict adapter for six exposed synthetic paraphrase templates, not a general parser."""
import re

import query_determinacy_model_world_replay as old
import query_determinacy_template_world_extraction as template

SUBJECT = r'(?P<subject>虚构样本[HK]\d{2}的记录(?:数值|代码))'
VALUE_A = r'(?P<a>\d+个单位|“[A-Z]\d”)'
VALUE_B = r'(?P<b>\d+个单位|“[A-Z]\d”)'
TEMPLATES = [
    '档案甲记载' + SUBJECT + '是' + VALUE_A + '；档案乙记载同一记录是' + VALUE_B + '。题设保证真实值只能是以上两个值之一，二者均有可能，无法判断哪份档案正确。',
    '第一份记录给出' + VALUE_A + '，第二份记录给出' + VALUE_B + '，它们都指' + SUBJECT + '。题设保证真实值恰好是这两个值之一，两个值都可能，现有信息不能判定哪份记录正确。',
    SUBJECT + '有两份不一致的记载：' + VALUE_A + '、' + VALUE_B + '。题设保证真实值必为其中之一，两种情况均有可能，但没有信息判断哪份记载正确。',
    '已知' + SUBJECT + '只能取' + VALUE_A + '或' + VALUE_B + '，两种情况均有可能，题设没有信息指出究竟是哪一个。',
    '关于' + SUBJECT + '，真实值不是' + VALUE_A + '就是' + VALUE_B + '；题设保证两者均可能且没有额外依据选定其中一个。',
    SUBJECT + '的可能值恰好是' + VALUE_A + '、' + VALUE_B + '；题设保证两种可能都存在，现有信息不能作进一步区分。',
]
PATTERNS = [re.compile(pattern) for pattern in TEMPLATES]


def branch_prompts(prompt, predicted_values):
    lines = prompt.splitlines()
    if len(lines) != 4 or lines[0] != template.PREFIX or not lines[2].startswith('问题：') or lines[3] != template.SUFFIX:
        raise ValueError('unrecognized outer template')
    evidence = lines[1]
    axiom = template.AXIOM if evidence.startswith(template.AXIOM) else ''
    rest = evidence[len(axiom):]
    matches = [m for p in PATTERNS if (m := p.fullmatch(rest))]
    if len(matches) != 1:
        raise ValueError('unrecognized paraphrase')
    subject, a, b = (matches[0][k] for k in ('subject', 'a', 'b'))
    number = subject.endswith('数值')
    validator = template.NUMBER if number else template.CODE
    if (number and axiom) or (not number and not axiom) or not validator.fullmatch(a) or not validator.fullmatch(b) or a == b:
        raise ValueError('invalid source syntax')
    # Source values only validate the fixed input syntax. Old interface constructs
    # the two actual branches solely from predicted_values, never from a or b.
    canonical = f'{subject}有两个可能：{a}或{b}。{template.ALT_TAIL}'
    lines[1] = axiom + canonical
    return old.prompts_from_candidates('\n'.join(lines), predicted_values)
