"""Construct six paired cases for each rule and scope-distractor condition."""
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'scripts'))
import query_determinacy_date_multi_pilot as prior


prior.PACK = HERE
public, reference = prior.materials()
rules = {item['id']: item for item in prior.pilot.read(HERE / 'rules.json')}
base = deepcopy((public, reference))
for rule, profile in base[0]['profiles'].items():
    data = rules[rule]
    cutoff = date.fromisoformat(data['effective'])
    old = (cutoff - timedelta(days=1)).isoformat()
    now = cutoff.isoformat()
    distractors = {
        'amount': ' Administrative example fee: $17.',
        'dates': f' The administrative review window runs from {old} through {now}.',
        'both': f' The administrative example fee is $17, for review from {old} through {now}.',
    }
    for condition, extra in distractors.items():
        name = f'{rule}_{condition}'
        derived = deepcopy(profile)
        scope_id = derived['scope_claims']['source']
        derived['evidence'][scope_id] += extra
        public['profiles'][name] = derived
        reference['profiles'][name] = deepcopy(base[1]['profiles'][rule])
        for original in base[0]['cases']:
            if original['profile'] != rule:
                continue
            case = deepcopy(original)
            case['profile'] = name
            case['id'] = original['id'].replace(rule + '-', name + '-', 1)
            public['cases'].append(case)
            reference['cases'][case['id']] = deepcopy(base[1]['cases'][original['id']])

for name, payload in (('public', public), ('reference', reference)):
    prior.pilot.write(HERE / f'{name}.json', payload)

locations, picks = prior.gold_picks(public, reference)
rows = prior.frozen.judge(public, reference, locations, picks)
assert len(rows) == 48 and all(row['checks']['strict'] for row in rows.values())
assert sum(len(row['expected']['branches']) for row in rows.values()) == 64
print('Eight rule/condition profiles, 48 cases and 64 reference branches verified.')
