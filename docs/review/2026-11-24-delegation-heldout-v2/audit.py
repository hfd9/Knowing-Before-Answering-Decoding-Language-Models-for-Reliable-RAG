"""Recount the saved tables independently of the runner's aggregation."""
import argparse
from collections import defaultdict
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REFS = HERE.parent / '2026-11-24-delegation-heldout-v1' / 'author-reference.json'
ROUTES = ('program', 'direct', 'full', 'repair', 'full_checked')


def read(path):
    return json.loads(path.read_text())


def independent_flags(observed, ref):
    expected = ref['result']
    answers = observed['result']
    if answers is not None:
        # The archive standardizes evidence IDs as a set for scoring, independently of order.
        normalize = lambda result: {
            slot: (v['applies'], v['rule'], v['answer'], frozenset(v['evidence']))
            for slot, v in result['worlds'].items()
        }
        strict = (observed['structure'] == ref['structure'] and answers['final'] == expected['final']
                  and normalize(answers) == normalize(expected))
    else:
        strict = False
    valid = observed['invalid'] is None
    final = observed['final']
    return {
        'strict': strict,
        'invalid': not valid,
        'false_unique': final in {'Y', 'N'} and expected['final'] in {'U', 'X'},
        'clear_unresolved': valid and final == 'X' and expected['final'] in {'U', 'Y', 'N'},
        'correct_x': valid and final == expected['final'] == 'X',
    }


def verify(report, refs, run):
    assert report['rows'].keys() == refs.keys()
    actual_calls = {}
    for path in sorted(run.glob('*.record.json')):
        for item in read(path)['records']:
            key = (item['case'], item['arm'])
            assert key not in actual_calls
            actual_calls[key] = (len(item['input_token_ids']), len(item['generated_token_ids']))
    assert len(actual_calls) == report['physical_calls']

    groups = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    roots = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    families = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    transitions = {}
    verified_coverage = 0
    observed_reversal = []
    for case, ref in refs.items():
        row = report['rows'][case]
        assert row['expected'] == ref['result']['final']
        assert (row['root'], row['group'], row['family']) == (ref['root'], ref['group'], ref['family'])
        for route in ROUTES:
            obs = row['arms'][route]
            flags = independent_flags(obs, ref)
            assert all(flags[k] == obs[k] for k in flags if k != 'invalid')
            if route == 'program' or (route == 'repair' and not row['missing']):
                expected_cost = None
            else:
                physical_arm = ('direct' if route == 'direct' else
                                'repair' if route == 'repair' and len(row['missing']) == 1 else 'extract')
                expected_cost = actual_calls[case, physical_arm]
            assert (obs['calls'], obs['input_tokens'], obs['output_tokens']) == (
                (1, *expected_cost) if expected_cost is not None else (0, 0, 0))
            counts = flags | {key: obs[key] for key in ('calls', 'input_tokens', 'output_tokens')} | {'n': 1}
            for table in (groups['all'], groups[ref['group']], roots[ref['root']], families[ref['family']]):
                for key, value in counts.items():
                    table[route][key] += value
        full, checked = (row['arms'][route] for route in ('full', 'full_checked'))
        grant = full['structure']['grant'] if full['structure'] is not None else None
        gold = ref['structure']['grant']
        reversed_order = (grant is not None and gold is not None and grant != gold
                          and grant['grantor'] == gold['recipient'] and gold['grantor'] == grant['recipient'])
        assert reversed_order == row['actual_f1_reversed']
        if reversed_order and full['false_unique']:
            observed_reversal.append(case)
        assert (full['calls'], full['input_tokens'], full['output_tokens']) == (
            checked['calls'], checked['input_tokens'], checked['output_tokens'])
        if row['f1_verification'] in {'confirmed', 'roles_reversed', 'different_roles', 'model_grant_missing'}:
            verified_coverage += 1
        if checked['final'] != full['final'] or checked['strict'] != full['strict']:
            transitions[case] = (full['final'], checked['final'],
                                 full['false_unique'] and not checked['false_unique'],
                                 full['strict'] and not checked['strict'],
                                 checked['strict'] and not full['strict'])
    summary = report['summary']
    assert dict(groups) == summary['groups'] and dict(families) == summary['families']
    assert all(dict(values) == {k: entry[k] for k in ROUTES} for root, values in roots.items()
               for entry in (summary['roots'][root],))
    assert transitions == {
        r['case']: tuple(r[k] for k in ('before', 'after', 'blocked_false_unique', 'lost_strict', 'recovered_strict'))
        for r in summary['verification_transitions']
    }
    return {'verified_rows': len(refs), 'physical_calls': len(actual_calls), 'f1_verifier_covered_valid': verified_coverage,
            'false_unique_with_reference_reversal': observed_reversal, 'ablation_transitions': transitions}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('run', type=Path)
    cli.add_argument('--report', type=Path, default=HERE / 'heldout-results.json')
    args = cli.parse_args()
    print(json.dumps(verify(read(args.report), read(REFS), args.run), ensure_ascii=False, sort_keys=True))
