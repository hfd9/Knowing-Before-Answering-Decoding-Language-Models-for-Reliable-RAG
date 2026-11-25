"""Replay reference-field substitutions on the six sealed date-extraction outputs."""

import argparse
from collections import Counter
from copy import deepcopy
from itertools import combinations
import json
from pathlib import Path
import sys
import tempfile
from zipfile import ZipFile


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'scripts'))

import query_determinacy_date_source_recovery as recovery


STUDY = recovery.study
PACK = recovery.PACK
ARCHIVE = PACK / 'recovery-raw.zip'
YEARS = ('2024', '2025')
FIELDS = {key: (key,) for key in ('scope', 'comparison', 'event', 'amount', 'first', 'last', 'date',
                                   'rule_id', 'scope_ids', 'fact_id')}
FIELDS.update({f'{label}_{year}': ('versions', index, key)
               for index, year in enumerate(YEARS)
               for label, key in (('valid_from', 'from'), ('valid_through', 'through'),
                                  ('threshold', 'threshold'), ('version_id', 'id'))})
EVIDENCE = ('rule_id', 'scope_ids', 'fact_id', 'version_id_2024', 'version_id_2025')
AMOUNT_RULE = ('comparison', 'amount')
CASE_RANGE = ('first', 'last')
SCENARIOS = {
    'original': (),
    'scope_only': ('scope',),
    'all_evidence_only': EVIDENCE,
    'scope_and_evidence': ('scope', *EVIDENCE),
    'scope_evidence_comparison': ('scope', *EVIDENCE, 'comparison'),
    'scope_evidence_amount': ('scope', *EVIDENCE, 'amount'),
    'scope_evidence_range': ('scope', *EVIDENCE, *CASE_RANGE),
    'scope_evidence_comparison_amount': ('scope', *EVIDENCE, *AMOUNT_RULE),
    'all_fields': tuple(FIELDS),
}


def raw_reference(case, reference):
    expected = STUDY.reference_fields(case, reference)
    comparator, event, rule_id = expected['rule']
    first, last = expected['range']
    return {'scope': expected['scope'], 'comparison': comparator, 'event': event, 'amount': expected['amount'],
            'first': first, 'last': last, 'date': expected['date'], 'rule_id': rule_id,
            'scope_ids': expected['scope_evidence'], 'fact_id': expected['fact_evidence'],
            'versions': [dict(zip(('from', 'through', 'threshold', 'id'), version, strict=True))
                         for version in expected['versions']]}


def field_parent(data, field):
    path = FIELDS[field]
    for key in path[:-1]:
        data = data[key]
    return data, path[-1]


def field_value(data, field):
    parent, key = field_parent(data, field)
    return parent.get(key)


def compare(raw, target, field):
    parent, key = field_parent(raw, field)
    observed, expected = parent.get(key), field_value(target, field)
    if type(observed) is type(expected) and observed == expected and key in parent:
        status = 'correct'
    elif observed in (None, '', []):
        status = 'missing'
    else:
        status = 'wrong'
    return {'status': status, 'present': key in parent, 'observed': observed, 'reference': expected}


def evaluate(raw, target, correct, expected):
    candidate = deepcopy(raw)
    for field in correct:
        parent, key = field_parent(candidate, field)
        parent[key] = field_value(target, field)

    outcome, error, stage = {'tag': None}, None, 'parse'
    try:
        parsed = recovery.parse(json.dumps(candidate))
        stage = 'solve'
        outcome = STUDY.solve(parsed)
    except (ValueError, TypeError) as exc:
        error = str(exc)
    if error is None:
        stage = 'unresolved' if outcome['tag'] == 'UNRESOLVED' else 'decision'

    observed = {row[0]: row[1:] for row in outcome.get('branches', [])}
    per_day = {day: {'conclusion': day in observed and observed[day][0] == answer,
                     'evidence': day in observed and observed[day][1] == evidence}
               for day, answer, evidence in expected['branches']}
    grade = STUDY.grade(outcome, expected)
    return {'stage': stage, 'error': error, 'outcome': outcome, 'grade': grade, 'by_date': per_day,
            'action_type_correct': action_type(outcome['tag']) == action_type(expected['tag']),
            'role_bindings_correct': all(compare(candidate, target, field)['status'] == 'correct' for field in EVIDENCE)}


def action_type(tag):
    return 'ANSWER' if tag in ('ANSWER_Y', 'ANSWER_N') else tag


def case_results(case, output, reference, archived):
    raw = json.loads(output)
    target = raw_reference(case, reference)
    expected = STUDY.reference_answer(case, reference)
    assert len(raw['versions']) == len(YEARS)
    assert [row['from'][:4] for row in raw['versions']] == list(YEARS)
    fields = {field: compare(raw, target, field) for field in FIELDS}
    def run(corrected):
        return evaluate(raw, target, corrected, expected)

    scenarios = {name: run(corrected) for name, corrected in SCENARIOS.items()}
    original = scenarios['original']
    assert (original['outcome'], original['error'], original['grade']) == (
        archived['outcome'], archived['issue'], archived['checks'])
    assert scenarios['all_fields']['grade']['strict'] and scenarios['all_fields']['role_bindings_correct']
    errors = tuple(field for field, evaluation in fields.items() if evaluation['status'] != 'correct')
    single = {field: run((field,)) for field in errors}
    recovered = []
    for size in range(len(errors) + 1):
        for corrected in combinations(errors, size):
            if run(corrected)['grade']['strict']:
                recovered.append(corrected)
    minimal = [corrected for corrected in recovered
               if not any(set(other) < set(corrected) for other in recovered)]
    assert minimal and not any(result['grade']['strict'] for result in single.values())
    return {'profile': case['profile'], 'output_sha256': recovery.local.sha(output.encode()),
            'expected': expected, 'fields': fields, 'scenarios': scenarios, 'single_field': single,
            'subsets_tested': 2 ** len(errors), 'strict_subsets': len(recovered), 'minimal_strict_subsets': minimal}


def summarize(outcomes):
    dates = [day for result in outcomes for day in result['by_date'].values()]
    return {'strict': sum(row['grade']['strict'] for row in outcomes),
            'action_type_correct': sum(row['action_type_correct'] for row in outcomes),
            'action_exact': sum(row['grade']['action_exact'] for row in outcomes),
            'wrong_unique': sum(row['grade']['wrong_unique_on_varying'] for row in outcomes),
            'conclusions_correct': sum(day['conclusion'] for day in dates),
            'evidence_correct': sum(day['evidence'] for day in dates), 'reference_branches': len(dates),
            'role_bindings_correct': sum(row['role_bindings_correct'] for row in outcomes),
            'stages': dict(Counter(row['stage'] for row in outcomes))}


def replay():
    public, reference = (recovery.pilot.read(PACK / f'{name}.json') for name in ('public', 'reference'))
    archived = recovery.pilot.read(PACK / 'recovery-results.json')['rows']['extract']
    with tempfile.TemporaryDirectory(prefix='kba-date-fields-') as directory:
        with ZipFile(ARCHIVE) as archive:
            archive.extractall(directory)
        saved, _ = recovery.archived(Path(directory), recovery.plan(public))
    outputs = {row['case']: row['output'] for row in saved if row['method'] == 'extract' and row['status'] == 'complete'}
    assert set(outputs) == set(archived) == {case['id'] for case in public['cases']}
    cases = {case['id']: case_results(case, outputs[case['id']], reference, archived[case['id']])
             for case in public['cases']}
    return {'source_archive_sha256': recovery.local.hash_file(ARCHIVE),
            'money_unit': 'whole USD, fixed by the archived extraction interface',
            'scenario_fields': SCENARIOS, 'scenarios': {
                name: summarize([row['scenarios'][name] for row in cases.values()]) for name in SCENARIOS},
            'single_field': {field: summarize([row['single_field'].get(field, row['scenarios']['original'])
                                              for row in cases.values()]) for field in FIELDS},
            'cases': cases}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='compare replay to the saved results')
    args = parser.parse_args()
    result = json.dumps(replay(), ensure_ascii=False, indent=2) + '\n'
    if args.verify:
        assert result == (HERE / 'results.json').read_text(encoding='utf-8'), 'field replay differs'
        print('Six date cases and all field substitutions replayed exactly.')
    else:
        print(result, end='')
