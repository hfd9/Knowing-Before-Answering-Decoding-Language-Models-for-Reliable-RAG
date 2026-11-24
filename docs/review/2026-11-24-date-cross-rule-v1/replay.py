"""Compare the threshold solver on the old inputs and an audited second rule."""

import argparse
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import sys

PACK = Path(__file__).resolve().parent
ROOT = PACK.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import query_determinacy_date_diagnostic as diagnostic  # noqa: E402
from query_determinacy_threshold_versions import ThresholdRule, ThresholdVersion, evaluate  # noqa: E402


def old_regression(inputs):
    # Map the unmodified public packet's parsed rule into the structured interface.
    packet_branches = diagnostic.solve_public(inputs['R03'])['branches']
    rule = ThresholdRule(packet_branches[0]['comparator'], 'consummation', 'E1', tuple(
        ThresholdVersion(date.fromisoformat(branch['valid_from']), date.fromisoformat(branch['valid_through']),
                         branch['threshold'], branch['evidence'][1]) for branch in packet_branches))
    decisions = {}
    for case, packet in inputs.items():
        stated, allowed = diagnostic.pilot.present_dates(packet)
        first, last = map(date.fromisoformat, allowed)
        parsed = diagnostic.solve_public(packet)
        amount = parsed['branches'][0]['amount']
        actual = evaluate(rule, amount, first, last, scope_established=True,
                          event_date=date.fromisoformat(stated) if stated else None)
        diagnostic.require(diagnostic.grounded(actual, parsed), f'changed original decision on {case}')
        decisions[case] = {key: actual[key] for key in ('action', 'answer', 'evidence')}
    return decisions


def cross_rule(profile):
    rule = ThresholdRule(profile['comparison'], profile['operative_event'], profile['evidence_id'], tuple(
        ThresholdVersion(date.fromisoformat(version['valid_from']), date.fromisoformat(version['valid_through']),
                         version['threshold'], version['evidence_id']) for version in profile['versions']))
    first, last = map(date.fromisoformat, profile['allowed_range'])
    # Hand-checked branch labels from the two cited thresholds, including both equality edges.
    expected = {32400: (True, True), 32401: (False, True), 33500: (False, True), 33501: (False, False)}
    outcomes = []
    for amount, answers in expected.items():
        branches = [evaluate(rule, amount, first, last, scope_established=True, event_date=day) for day in (first, last)]
        merged = evaluate(rule, amount, first, last, scope_established=True)
        negative = evaluate(replace(rule, comparison='>'), amount, first, last, scope_established=True)
        diagnostic.require(tuple(branch['answer'] for branch in branches) == answers, 'dated branch differs')
        diagnostic.require(tuple(branch['evidence'] for branch in branches) == (['A1', 'A24'], ['A1', 'A25']),
                           'evidence does not cover the actual dates')
        diagnostic.require(tuple(branch['answer'] for branch in merged['branches']) == answers, 'merged branch differs')
        diagnostic.require(tuple(branch['evidence'] for branch in merged['branches']) == (['A1', 'A24'], ['A1', 'A25'])
                           and merged['evidence'] == ['A1', 'A24', 'A25'], 'merged evidence differs')
        expected_action = 'answer' if answers[0] == answers[1] else 'ask_date'
        diagnostic.require(merged['action'] == expected_action and
                           merged['answer'] is (answers[0] if expected_action == 'answer' else None), 'merged action differs')
        if expected_action == 'ask_date':
            diagnostic.require(merged.get('ask_event') == 'consummation', 'wrong clarification target')
        outcomes.append({'amount': amount, 'dated': branches, 'merged': merged, 'wrong_comparator': negative})
    return outcomes


def build():
    source = diagnostic.pilot.MATERIAL / 'inputs.json'
    original = {row['id']: row['input'] for row in diagnostic.pilot.read(source)}
    retained = old_regression(original)
    hpml = PACK / 'hpml-rule.json'
    rows = cross_rule(diagnostic.pilot.read(hpml))
    # The old author reference is only used after decisions are produced.
    reference_source = diagnostic.pilot.MATERIAL / 'reference.json'
    reference = diagnostic.pilot.read(reference_source)['cases']
    diagnostic.require(all(diagnostic.grounded(result, reference[case]) for case, result in retained.items()),
                       'original author reference disagrees')
    sources = (source, reference_source, hpml, Path(diagnostic.__file__), Path(__file__),
               ROOT / 'scripts/query_determinacy_threshold_versions.py')
    summary = {'original_strict': len(retained), 'dated_strict': sum(len(row['dated']) for row in rows),
               'merged_strict': len(rows),
               'wrong_comparator_action_matches': sum(row['merged']['action'] == row['wrong_comparator']['action'] for row in rows),
               'wrong_comparator_branch_matches': sum(right['answer'] == wrong['answer'] for row in rows
                   for right, wrong in zip(row['merged']['branches'], row['wrong_comparator']['branches'], strict=True))}
    return {'sha256': {str(path.resolve().relative_to(ROOT)): diagnostic.pilot.local.hash_file(path) for path in sources},
            'old_regression': retained, 'cross_rule': rows, 'summary': summary}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result = diagnostic.pilot.local.encode(build())
    if args.verify:
        diagnostic.require(result == (PACK / 'results.json').read_bytes(), 'cross-rule replay differs')
        print('Date cross-rule replay passed.')
    else:
        print(result.decode(), end='')
