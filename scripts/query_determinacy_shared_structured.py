"""Controlled two-case engineering interface. Candidate slots are public source IDs."""
from functools import lru_cache
from itertools import combinations, product
import json
import re

import query_determinacy_shared_lines as lines

FENCE = re.compile(r'```json\n([^\n]+)\n```')
SOURCE = {
    'integer': re.compile(r'来源[甲乙]写：这次校准的读数是(0|[1-9][0-9]{0,8})([一-龥]+)。'),
    'identifier': re.compile(r'来源[甲乙]写：本次检测代码是([A-Za-z0-9][A-Za-z0-9_-]{0,63})。'),
}
QUESTION = re.compile(r'该次校准读数是否(超过|低于)(0|[1-9][0-9]{0,8})([一-龥]+)？')


def extract_candidates(raw, domain):
    """Accept bare arrays and a whole, single JSON fence. Preserve raw bytes at the caller."""
    original = lines.extract.parse(raw, domain)
    if original['status'] == 'parsed':
        return dict(original, encoding='bare')
    text = raw.replace('\r\n', '\n').removesuffix('\n')
    match = FENCE.fullmatch(text) if len(raw) <= lines.extract.MAX_OUTPUT_CHARS else None
    if match is not None:
        wrapped = lines.extract.parse(match[1], domain)
        if wrapped['status'] == 'parsed':
            return dict(wrapped, encoding='single_json_fence')
    return dict(original, encoding=None)


def materials(case):
    spans = lines.evidence_map(case)
    source = {}
    for key in ('S1', 'S2'):
        match = SOURCE[case['domain']].fullmatch(spans[key]['text'])
        if not match:
            raise ValueError('unrecognized public source syntax')
        source[key] = {'value': match[1], 'unit': match[2] if case['domain'] == 'integer' else None}
    if source['S1']['value'] == source['S2']['value']:
        raise ValueError('duplicate public source values')
    return spans, source


def bind(values, sources):
    """Map actual extraction to source slots. Never repair, add or reorder a value."""
    if values is None or len(values) != 2 or len(set(values)) != 2:
        return None
    lookup = {entry['value']: key for key, entry in sources.items()}
    return tuple(lookup[v] for v in values) if set(values) == set(lookup) else None


def prompt(kind, case, question, source_slots, spans, sources):
    if kind == 'extract':
        return lines.prompt('extract', case, None)
    raw = case['background'].encode()
    for label, span in reversed(list(spans.items())):
        i = span['start_byte']
        raw = raw[:i] + f'[{label}]'.encode() + raw[i:]
    text = ('根据材料分别作答。将来源中的值作为临时假设。\n材料：\n'
            + raw.decode() + '\n问题：' + question['text'])
    if kind == 'direct':
        text += '\n分别假设 S1 与 S2 报告的实际值成立。'
    else:
        values = '、'.join(f'{label}={sources[label]["value"]}' for label in source_slots)
        text += '\n按实际抽取得到的候选分别判断：' + values + '。'
    text += ('\n每个假设一行，格式为 来源=判断|证据。判断写 Y（是）、N（否）或 X（无法判断）。'
             '证据填写该判断所用来源或规则 ID，多个用英文逗号分隔。无证据或判断为 X 时写 -。'
             '只输出' + '、'.join(source_slots) + '对应的行，按给定顺序，不另写最终标签。')
    return text


@lru_cache(maxsize=8)
def responses(source_slots, evidence_ids):
    """Allow all evidence subsets and both decisions equally. X records abstention."""
    subsets = tuple(','.join(group) for n in range(1, len(evidence_ids)+1)
                    for group in combinations(evidence_ids, n))
    choices = tuple(f'{answer}|{item}' for answer in 'YN' for item in ('-', *subsets)) + ('X|-',)
    options = {}
    for picked in product(choices, repeat=len(source_slots)):
        text = '\n'.join(f'{slot}={choice}' for slot, choice in zip(source_slots, picked))
        options[text] = tuple((slot, choice[0], tuple(choice[2:].split(',')) if choice[2:] != '-' else ())
                              for slot, choice in zip(source_slots, picked))
    return options


def token_prefixes(tokenizer, options, eos_ids):
    """Compile character-domain options to all canonical token prefixes."""
    prefixes = {}
    for response in options:
        ids = tokenizer(response, add_special_tokens=False)['input_ids']
        if not ids or set(ids).intersection(eos_ids) or tokenizer.decode(ids, skip_special_tokens=True) != response:
            raise ValueError('output text does not round-trip through the pinned tokenizer')
        path = tuple(ids)
        for i, token in enumerate(path):
            prefixes.setdefault(path[:i], set()).add(token)
        prefixes.setdefault(path, set()).update(eos_ids)
    return {path: sorted(token_ids) for path, token_ids in prefixes.items()}


def numeric_comparison(question, bound, sources):
    query = QUESTION.fullmatch(question)
    if query is None or bound is None or any(sources[slot]['unit'] != query[3] for slot in bound):
        return None
    worlds = []
    for slot in bound:
        value, threshold = int(sources[slot]['value']), int(query[2])
        yes = value > threshold if query[1] == '超过' else value < threshold
        worlds.append((slot, 'Y' if yes else 'N', (slot,)))
    return tuple(worlds)


def ensure_worlds(worlds, sources):
    return [{'slot': slot, 'value': sources[slot]['value'], 'answer': label, 'evidence_ids': list(evidence)}
            for slot, label, evidence in worlds]


def final(worlds):
    return lines.merge([world['answer'] for world in worlds])
