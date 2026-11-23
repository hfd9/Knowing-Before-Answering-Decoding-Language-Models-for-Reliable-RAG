"""Finite applicability check for the authored, fixed-world CPU examples."""
from datetime import date
import re

SCOPE = re.compile(r'台账记载：「([^」]+)」和「([^」]+)」是(同一件物品的两个|两件不同物品的)登记名。')
DATE = re.compile(r'本件于([0-9]{4})年([0-9]{1,2})月([0-9]{1,2})日完成核验。')
GRANT = re.compile(r'([一-龥]+组)授权([一-龥]+组)为本件签发豁免。')
PROXY = re.compile(r'这次能替([一-龥]+组)为本件签发豁免的是([一-龥]+组)。')


def normalize(kind, text, *, include_proxy=False):
    """Extract typed facts from known sentence structures, leaving other wording unresolved."""
    if kind == 'scope':
        match = SCOPE.fullmatch(text)
        if match:
            return {'first': match[1], 'second': match[2], 'same': match[3] == '同一件物品的两个'}
    elif kind == 'date':
        match = DATE.fullmatch(text)
        if match:
            try:
                return {'date': date(*map(int, match.groups())).isoformat()}
            except ValueError:
                return None
    elif kind == 'delegation':
        match = GRANT.fullmatch(text)
        if match is None and include_proxy:
            match = PROXY.fullmatch(text)
        if match:
            # Both supported constructions place the authority first and the recipient second.
            return {'from': match[1], 'to': match[2]}
    else:
        raise ValueError(f'unknown condition type: {kind}')
    return None


def evaluate(kind, target, fact):
    """Use explicit conditions and rule priority, retaining unavailable applicability as X."""
    applies = None
    if fact is not None:
        if kind == 'scope':
            if ({fact['first'], fact['second']} == {target['first'], target['second']}
                    and type(fact['same']) is bool):
                applies = fact['same']
        elif kind == 'date':
            applies = date.fromisoformat(fact['date']) >= date.fromisoformat(target['cutoff'])
        elif kind == 'delegation':
            applies = all(fact[key] == target[key] for key in ('from', 'to'))
        else:
            raise ValueError(f'unknown condition type: {kind}')
    if applies is None:
        second = {'rule': None, 'answer': 'X', 'evidence': []}
    elif applies:
        second = {'rule': 'R3', 'answer': 'Y', 'evidence': ['W2', 'R2', 'R3', 'F1']}
    else:
        second = {'rule': 'R2', 'answer': 'N', 'evidence': ['W2', 'R2', 'R3', 'F1']}
    final = {'X': None, 'Y': 'Y', 'N': 'U'}[second['answer']]
    return {'exception_applies': applies, 'worlds': {
        'W1': {'rule': 'R1', 'answer': 'Y', 'evidence': ['W1', 'R1']},
        'W2': second,
    }, 'final': final}
