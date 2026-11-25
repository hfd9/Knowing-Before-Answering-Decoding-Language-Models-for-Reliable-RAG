"""Prepare two new rules with overlapping and nonoverlapping scope distractors."""
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'scripts'))
import query_determinacy_date_multi_pilot as study

study.PACK = HERE
public, reference = study.materials()
rules = {r['id']: r for r in study.pilot.read(HERE / 'rules.json')}
base_public = deepcopy(public)
base_reference = deepcopy(reference)
for name, profile in base_public['profiles'].items():
    effective = date.fromisoformat(rules[name]['effective'])
    before = effective - timedelta(days=1)
    distractors = {
        'overlap': f' An unrelated fee is $17. The separate review runs from {before} through {effective}.',
        'separate': ' An unrelated fee is $17. The separate review runs from 2020-01-01 through 2020-01-01.',
    }
    for variant, addition in distractors.items():
        new_name = f'{name}_{variant}'
        item = deepcopy(profile)
        item['evidence'][item['scope_claims']['source']] += addition
        public['profiles'][new_name] = item
        reference['profiles'][new_name] = deepcopy(base_reference['profiles'][name])
        for row in base_public['cases']:
            if row['profile'] != name:
                continue
            case = deepcopy(row)
            case['id'] = row['id'].replace(name+'-', new_name+'-', 1)
            case['profile'] = new_name
            public['cases'].append(case)
            reference['cases'][case['id']] = deepcopy(base_reference['cases'][row['id']])
for name, data in (('public', public), ('reference', reference)):
    study.pilot.write(HERE / f'{name}.json', data)
locations, picks = study.gold_picks(public, reference)
results = study.frozen.judge(public, reference, locations, picks)
assert len(results) == 36 and all(row['checks']['strict'] for row in results.values())
assert sum(len(row['expected']['branches']) for row in results.values()) == 48
for name, profile in public['profiles'].items():
    if '_' in name:
        source = profile['evidence'][profile['scope_claims']['source']]
        assert study.frozen.amount(source) == 17 and len(study.frozen.parse_days(source)) == 2
print('36 reference cases, 48 branches and four real version-shaped distractors verified.')
