"""Frozen raw-text baseline and shared evaluator for the delegation diagnostic."""
import json
import re

from query_determinacy_rule_applicability import normalize


SLOTS = ('W1', 'W2')
RECORDS = (*SLOTS, 'R1', 'R2', 'R3', 'F1')
ANSWER = {'准入': 'Y', '不准入': 'N'}
NAME = r'(?P<{}>[一-龥]{{1,10}}组)'
GRANTOR = '「' + NAME.format('grantor') + '」'
RECIPIENT = '「' + NAME.format('recipient') + '」'
ACTIVE = GRANTOR + r'(?:授权|委托)' + RECIPIENT
PASSIVE = RECIPIENT + r'(?:获|受)' + GRANTOR + r'(?:授权|委托)'
SIGN = r'(?:签发|核发)复核单'
DIRECTION = re.compile(rf'(?:{ACTIVE})')
REVERSE_WORD_ORDER = re.compile(rf'(?:{PASSIVE})')
CONDITION = re.compile(rf'本件(?:若|如)(?:由)?(.+?){SIGN}')
EFFECT = re.compile(r'(?:则)?改按本条判为(准入|不准入)，优先于(R[12])。')
GRANT = re.compile(rf'本件(?:唯一一项授权是|仅有一项授权：)(.+?)(?:为本件)?{SIGN}。')
SOURCE = re.compile(r'本件类别为「([^」]+)」。')
DEFAULT = re.compile(r'「([^」]+)」类别按本条判为(准入|不准入)。')


def edge(text):
    for pattern in (DIRECTION, REVERSE_WORD_ORDER):
        match = pattern.fullmatch(text)
        if match:
            return match.groupdict()
    return None


def structured_from_parser(records):
    """Parse the visible exception rule and grant, conserving unknowns."""
    exception = None
    condition, _, effect = records['R3'].partition('，')
    condition_match = CONDITION.fullmatch(condition)
    effect_match = EFFECT.fullmatch(effect)
    if condition_match and effect_match:
        required = edge(condition_match[1])
        if required:
            exception = dict(required, answer=ANSWER[effect_match[1]], overrides=effect_match[2])

    grant_match = GRANT.fullmatch(records['F1'])
    grant = edge(grant_match[1]) if grant_match else None
    if grant is None:
        legacy = normalize('delegation', records['F1'], include_proxy=True)
        if legacy:
            grant = {'grantor': legacy['from'], 'recipient': legacy['to']}
    return {'exception': exception, 'grant': grant}


def context(records):
    """Read the fixed-form source categories and default clauses from the input."""
    worlds = {slot: SOURCE.fullmatch(records[slot]) for slot in SLOTS}
    defaults = {rule: DEFAULT.fullmatch(records[rule]) for rule in ('R1', 'R2')}
    if not all((*worlds.values(), *defaults.values())):
        raise ValueError('invalid source category or default clause')
    by_category = {match[1]: (rule, ANSWER[match[2]]) for rule, match in defaults.items()}
    if len(by_category) != 2 or {match[1] for match in worlds.values()} != set(by_category):
        raise ValueError('source records must conflict and map to two distinct default rules')
    return {slot: by_category[match[1]] for slot, match in worlds.items()}


def validate_structure(value):
    if not isinstance(value, dict) or set(value) != {'exception', 'grant'}:
        raise ValueError('expected exception and grant fields')
    for field, extras in (('exception', {'answer', 'overrides'}), ('grant', set())):
        obj = value[field]
        if obj is None:
            continue
        if not isinstance(obj, dict) or set(obj) != extras | {'grantor', 'recipient'}:
            raise ValueError(f'invalid {field} fields')
        if any(not isinstance(obj[role], str) or not obj[role].strip() for role in ('grantor', 'recipient')):
            raise ValueError(f'invalid {field} roles')
        if field == 'exception' and (obj['answer'] not in ('Y', 'N') or obj['overrides'] not in ('R1', 'R2')):
            raise ValueError('invalid exception conclusion or priority')
    return value


def merge(answers):
    if any(answer == 'X' for answer in answers):
        return 'X'
    return answers[0] if answers[0] == answers[1] else 'U'


def solve(records, structure):
    """Apply the extracted edge and priority, without consulting author references."""
    validate_structure(structure)
    exception, grant = structure['exception'], structure['grant']
    worlds = {}
    for slot, (default_rule, default_answer) in context(records).items():
        if exception is None or (exception['overrides'] == default_rule and grant is None):
            worlds[slot] = {'applies': None, 'rule': None, 'answer': 'X', 'evidence': []}
            continue
        relevant = exception['overrides'] == default_rule
        applies = relevant and all(exception[key] == grant[key] for key in ('grantor', 'recipient'))
        worlds[slot] = {
            'applies': applies,
            'rule': 'R3' if applies else default_rule,
            'answer': exception['answer'] if applies else default_answer,
            'evidence': [slot, default_rule, 'R3', *(['F1'] if relevant else [])],
        }
    return {'worlds': worlds, 'final': merge([worlds[slot]['answer'] for slot in SLOTS])}


def unique_object(pairs):
    obj = dict(pairs)
    if len(obj) != len(pairs):
        raise ValueError('duplicate JSON field')
    return obj


def response_object(raw):
    text = raw.strip()
    fence = re.fullmatch(r'```(?:json)?\n(.*?)\n```', text, re.DOTALL)
    return json.loads(fence[1] if fence else text, object_pairs_hook=unique_object)
