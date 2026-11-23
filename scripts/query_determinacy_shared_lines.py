"""Prompt rendering and strict line parsing for the two-case engineering rerun."""
import json
import re

import query_determinacy_extract_v2 as extract

VALUE_PATTERNS = {'integer': extract.INTEGER, 'identifier': extract.IDENTIFIER}
EVIDENCE = r'[A-Z][1-9][0-9]*'
WORLD = re.compile(r'W=([^|]+)\|([YN])\|(-|' + EVIDENCE + r'(?:,' + EVIDENCE + r')*)')
FINAL = re.compile(r'F=([YNU])')


def evidence_map(case):
    """Locate complete public source and rule spans without consulting answers."""
    background = case['background']
    sources = list(re.finditer(r'来源[甲乙]写：[^。]+。', background))
    if len(sources) != 2 or [m[0][2] for m in sources] != ['甲', '乙']:
        raise ValueError('expected two distinct sources in source order')
    spans = [(f'S{i}', m.start(), m.end()) for i, m in enumerate(sources, 1)]
    if case['domain'] == 'identifier':
        table_prefix = '规则表明确：'
        start = background.index(table_prefix) + len(table_prefix)
        table = re.fullmatch(r'([^；。]+)；([^；。]+)。', background[start:])
        if not table:
            raise ValueError('expected two rule spans in the public table')
        spans += [(f'R{i}', start + table.start(i), start + table.end(i)) for i in (1, 2)]
    result = {}
    for label, start, end in spans:
        result[label] = {
            'start_byte': len(background[:start].encode()),
            'end_byte': len(background[:end].encode()),
            'text': background[start:end],
        }
    return result


def prompt(kind, case, question, values=None, branch=None):
    background = case['background'].encode()
    for label, span in reversed(list(evidence_map(case).items())):
        start = span['start_byte']
        background = background[:start] + f'[{label}]'.encode() + background[start:]
    text = ('仅用材料和题设。保留两个来源及规则，候选值均只是临时假设。\n'
            '材料：\n' + background.decode())
    if kind == 'extract':
        return (text + '\n提取两个来源针对同一字段的两个不同值，只输出JSON数组。'
                       '保留原始数字或代码，不附单位或解释。')

    text += '\n问题：' + question['text']
    if kind == 'direct':
        text += '\n自行找出两个候选值，对两个世界分别判断。'
    elif kind == 'joint':
        text += '\n上一步实际抽取值：' + json.dumps(values, ensure_ascii=False) + '。按每一个假设分别判断。'
    elif kind == 'branch':
        text += '\n只按这个抽取值成立的临时假设判断：' + json.dumps(values[branch], ensure_ascii=False) + '。'
    else:
        raise ValueError('unknown call kind')
    text += ('\n世界行格式为 W=值|答案|证据ID。值只写数字或代码，不写单位。'
             '世界答案只能是 Y（是）或 N（否）。证据只写材料中支持这支判断的ID，不复抄原文。'
             '数值题写对应的来源ID，类别题写对应的来源和规则ID，以英文逗号分隔。无证据写-。')
    if kind == 'branch':
        return text + '\n只输出一条世界行。'
    return (text + '\n只输出两条世界行，然后输出一条 F=最终标签。'
                   '两支同为Y则填Y，同为N则填N，异答则填U。')


def parse(raw, domain, *, single_world):
    """A structurally valid unknown evidence ID is kept for scoring."""
    lines = raw.replace('\r\n', '\n').removesuffix('\n').split('\n')
    expected_length = 1 if single_world else 3
    if len(lines) != expected_length:
        raise ValueError('wrong line count')
    worlds = []
    for line in lines[:1 if single_world else 2]:
        match = WORLD.fullmatch(line)
        if not match or not VALUE_PATTERNS[domain].fullmatch(match[1]):
            raise ValueError('invalid world row')
        evidence = [] if match[3] == '-' else match[3].split(',')
        if len(set(evidence)) != len(evidence):
            raise ValueError('duplicate evidence ID')
        worlds.append({'value': match[1], 'answer': match[2], 'evidence_ids': evidence})
    if single_world:
        return None, worlds
    if worlds[0]['value'] == worlds[1]['value']:
        raise ValueError('duplicate world')
    match = FINAL.fullmatch(lines[2])
    if not match:
        raise ValueError('invalid final row')
    return match[1], worlds


def merge(answers):
    if len(answers) == 2 and all(answer in ('Y', 'N') for answer in answers):
        return answers[0] if answers[0] == answers[1] else 'U'
    return None
