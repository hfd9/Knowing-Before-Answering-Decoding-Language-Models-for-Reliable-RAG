"""Build author-constructed development cases and narrow rule references; no model."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def decision(operator, amount, threshold):
    if operator == '>=':
        return amount >= threshold
    if operator == '>':
        return amount > threshold
    raise ValueError('unsupported operator')


def build(data):
    rules = data['rules']
    if len(rules) != 2 or len({r['id'] for r in rules}) != 2:
        raise ValueError('expected two distinct rules')
    cases, reference = [], {}
    for rule in rules:
        old, new = rule['old_date'], rule['new_date']
        if not old < new or not rule['old_threshold'] < rule['new_threshold']:
            raise ValueError('invalid version order')
        for category, amount in (('same', rule['same_amount']), ('different', rule['different_amount'])):
            branches = {old: decision(rule['comparison'], amount, rule['old_threshold']),
                        new: decision(rule['comparison'], amount, rule['new_threshold'])}
            if (len(set(branches.values())) == 1) != (category == 'same'):
                raise ValueError('pair category differs')
            for state, event_date in (('missing', None), ('old', old), ('new', new)):
                case_id = f'{rule["id"]}/{category}/{state}'
                fact = rule['facts_template'].format(amount=amount)
                if event_date is not None:
                    fact += f' The {rule["event"]} date is {event_date}.'
                else:
                    fact += f' The {rule["event"]} date is not provided.'
                case = {'id': case_id, 'rule_id': rule['id'], 'question': rule['question'],
                        'facts_and_date_status': fact, 'old_date': old, 'new_date': new,
                        'event': rule['event'], 'evidence': rule['evidence'], 'metadata': rule['metadata']}
                cases.append(case)
                evaluated = branches if event_date is None else {event_date: branches[event_date]}
                reference[case_id] = {'category': category, 'amount': amount, 'event_date': event_date,
                                      'branches': evaluated, 'independently_reviewed': False}
    return {'status': data['status'], 'cases': cases}, {'status': 'informed_author_not_legal_gold', 'cases': reference}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    public, reference = build(json.loads((HERE / 'rules.json').read_text()))
    for name, obj in (('public.json', public), ('reference.json', reference)):
        path = HERE / name
        if args.verify:
            if path.read_bytes() != encode(obj):
                raise ValueError(f'{name} differs')
        else:
            with path.open('xb') as out:
                out.write(encode(obj))
    print('Development materials replayed.' if args.verify else 'Development materials written.')
