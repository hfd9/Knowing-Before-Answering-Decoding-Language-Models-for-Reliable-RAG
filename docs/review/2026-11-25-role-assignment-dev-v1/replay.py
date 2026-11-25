"""Replay the exposed development records and synthetic role-assignment controls."""

from copy import deepcopy
import json
from pathlib import Path
import sys
from zipfile import ZipFile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_role_assign as candidate


base = candidate.base
pilot = base.pilot
frozen = base.frozen
local = base.local
PACKS = {'original': ROOT / 'docs/review/2026-11-25-typed-holdout-v1',
         'ambiguous': ROOT / 'docs/review/2026-11-25-typed-ambiguity-v1'}


def load_rows(path, prefix):
    with ZipFile(path / 'raw.zip') as z:
        return [row for name in sorted(z.namelist()) if name.startswith(prefix) and name.endswith('.record.json')
                for row in json.loads(z.read(name))['records']]


def run():
    original, ambiguous = (pilot.read(PACKS[name] / 'public.json') for name in PACKS)
    old_rows = load_rows(PACKS['original'], 'extract-')
    lookup = {row['id']: row for row in old_rows}
    results = {}
    for name, public in (('original', original), ('ambiguous', ambiguous)):
        records = load_rows(PACKS[name], 'locate-')
        locations, failures = candidate.assign(public, records)
        require = base.require
        require(not failures, 'candidate did not resolve exposed development set')
        tasks, groups = base.plan(public, locations)
        reused = []
        for task in tasks:
            row = lookup[task['id']]
            require(all(row[key] == value for key, value in task.items()), 'saved scope prompt changed')
            reused.append(row)
        picks, _ = frozen.extraction_picks(reused, groups)
        reference = pilot.read(PACKS[name] / 'reference.json')
        judged = frozen.judge(public, reference, locations, picks)
        require(all(row['checks']['strict'] for row in judged.values()), 'development result differs')
        results[name] = {'cases': len(judged), 'strict': sum(row['checks']['strict'] for row in judged.values()),
                         'locations': locations, 'saved_choices_reused': len(reused),
                         'rows': {key: {'checks': value['checks'], 'outcome': value['outcome'],
                                        'field_checks': value['field_checks']} for key, value in judged.items()}}

    name = 'estate_both'
    profile = deepcopy(ambiguous['profiles'][name])
    relevant = [row for row in load_rows(PACKS['ambiguous'], 'locate-') if row['id'].startswith(name + '/')]
    profile_map = {'profiles': {name: profile}}
    actual, errors = candidate.assign(profile_map, relevant)
    assert not errors and actual[name]['scope'] == 'E4'
    # Re-label source identities while preserving the score attached to each original source.
    mapping = {'E1': 'E3', 'E2': 'E4', 'E3': 'E1', 'E4': 'E2'}
    relabeled = deepcopy(profile_map)
    relabeled['profiles'][name]['evidence'] = {mapping[k]: v for k, v in profile['evidence'].items()}
    relabeled_rows = deepcopy(relevant)
    for row in relabeled_rows:
        row['choices'] = [mapping[tag] for tag in row['choices']]
    assert candidate.assign(relabeled, relabeled_rows)[0][name] == {role: mapping[tag] for role, tag in actual[name].items()}
    missing = deepcopy(profile_map)
    for tag in ('E1', 'E3'):
        missing['profiles'][name]['evidence'][tag] = 'No dated version is given.'
    assert candidate.assign(missing, relevant)[1][name] == 'no_nonoverlapping_version_pair'
    overlapping = deepcopy(profile_map)
    overlapping['profiles'][name]['evidence']['E3'] = overlapping['profiles'][name]['evidence']['E1']
    assert candidate.assign(overlapping, relevant)[1][name] == 'no_nonoverlapping_version_pair'
    tied = deepcopy(relevant)
    for row in tied:
        row['scores'] = [0.0] * len(row['scores'])
    assert candidate.assign(profile_map, tied)[1][name] == 'role_assignment_tie'
    # A nonoverlapping third candidate creates several possible pairs, which are resolved by saved role scores.
    third = deepcopy(profile_map)
    third['profiles'][name]['evidence']['E4'] = 'Historical review from 2020-01-01 through 2020-01-01. Fee $17.'
    third_result, third_failures = candidate.assign(third, relevant)
    assert not third_failures and name in third_result
    return {'source_sha256': {name: local.hash_file(path / 'raw.zip') for name, path in PACKS.items()},
            'candidate_sha256': local.hash_file(ROOT / 'scripts/query_determinacy_role_assign.py'),
            'results': results, 'controls': {'label_reassignment': 'passed', 'missing_versions': 'passed',
               'overlapping_versions': 'passed', 'score_tie': 'passed', 'three_disjoint_candidates': third_result[name]}}


if __name__ == '__main__':
    output = local.encode(run())
    if '--verify' in sys.argv:
        assert output == (HERE / 'results.json').read_bytes(), 'results differ from replay'
        print('Role assignment development replay and controls passed.')
    else:
        print(output.decode(), end='')
