#!/usr/bin/env python3
"""Fail-closed source-to-branch prompt extraction for one fixed synthetic template."""
import re

PREFIX='以下是虚构情境，请仅依据题设回答。'
SUFFIX='请仅输出一个答案：是、否或无法确定。'
AXIOM='代码是单个原子标签；不同代码互不相同，不存在包含或同义关系。'
SOURCE_TAIL='题设保证真实情况恰好是这两个值之一，两种情况都有可能，且没有其他信息可区分哪份资料正确。'
ALT_TAIL='题设保证真实情况恰好是这两个值之一，两种情况都有可能，且没有其他信息可以区分这两种情况。'
SOURCE=re.compile(r'资料甲称(?P<subject>[^；。]+?)为(?P<a>[^；。]+)；资料乙称其为(?P<b>[^；。]+)。')
ALT=re.compile(r'(?P<subject>[^；。]+?)有两个可能：(?P<a>[^；。]+?)或(?P<b>[^；。]+)。')
NUMBER=re.compile(r'\d+个单位')
CODE=re.compile(r'“[A-Z]\d”')


def branch_prompts(prompt):
    lines=prompt.splitlines()
    if len(lines)!=4 or lines[0]!=PREFIX or not lines[2].startswith('问题：') or lines[3]!=SUFFIX:
        raise ValueError('unrecognized outer template')
    evidence=lines[1]
    axiom=AXIOM if evidence.startswith(AXIOM) else ''
    rest=evidence[len(axiom):]
    m=SOURCE.match(rest)
    if m:
        tail=SOURCE_TAIL
    else:
        m=ALT.match(rest);tail=ALT_TAIL
    if not m or rest[m.end():]!=tail:raise ValueError('unrecognized source or exhaustiveness statement')
    subject,a,b=m['subject'],m['a'],m['b']
    if not re.fullmatch(r'虚构样本[HK]\d{2}的记录(?:数值|代码)',subject):
        raise ValueError('unrecognized record subject')
    numeric=subject.endswith('数值')
    validator=NUMBER if numeric else CODE
    if (numeric and axiom) or (not numeric and not axiom) or not validator.fullmatch(a) or not validator.fullmatch(b) or a==b:
        raise ValueError('invalid world values or atomic axiom')
    return [f'{PREFIX}\n{axiom}假设{subject}确定为{value}。\n{lines[2]}\n{SUFFIX}' for value in (a,b)]
