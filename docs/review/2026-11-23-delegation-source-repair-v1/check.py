"""Replay observed extraction errors and the template-bounded source repair."""
import argparse
from collections import Counter
import json
from pathlib import Path
import runpy
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_delegation_paired as contract
from query_determinacy_delegation_source import solve_from_sources, source_structure, verify_fact


INITIAL = HERE.parent / '2026-11-23-rule-applicability-live-v1' / 'heldout-results.json'
PREVIOUS = HERE.parent / '2026-11-23-delegation-fact-verification-v1'


def metrics(row):
    return {key: row[key] for key in ('final', 'correct_grounded', 'unfounded_unique')}


def replay():
    # This re-decodes and checks the originally sealed model outputs before using their scores.
    previous = runpy.run_path(str(PREVIOUS / 'check.py'))['replay']()
    contract.require(previous == contract.read(PREVIOUS / 'results.json'), 'previous sealed replay differs')
    live = contract.read(INITIAL)
    _, _, dev, dev_ref, cases, refs, groups = contract.load_packet()
    before = live['rows']['extract']
    routes = {key: {} for key in ('f1_verified', 'f1_from_source', 'both_from_source')}
    details = {}
    for i, records in cases.items():
        model = before[i]['structure']
        status, fact, checked = verify_fact(records, model)
        source = source_structure(records)
        structures = {'f1_verified': checked, 'f1_from_source': dict(model, grant=fact), 'both_from_source': source}
        for route, structure in structures.items():
            routes[route][i] = contract.judge(records, refs[i], 'extract', json.dumps(structure))
        contract.require(routes['both_from_source'][i]['result'] == solve_from_sources(records),
                         'source entry point and scoring replay disagree')
        details[i] = {'root': refs[i]['root'], 'wording': refs[i]['wording'],
                      'original_check': previous['rows'][i]['check'], 'expanded_check': status,
                      'model_structure': model, 'source_structure': source,
                      'reference_final': refs[i]['result']['final'], 'original': metrics(before[i]),
                      **{route: metrics(rows[i]) for route, rows in routes.items()}}

    return {
        'original_seal_sha256': previous['sources']['heldout_seal_sha256'],
        'check_counts': dict(Counter(item['expanded_check'] for item in details.values())),
        'directions_correct': sum(source_structure(row)['grant'] == refs[i]['structure']['grant']
                                  for i, row in cases.items()),
        'rules_correct': sum(source_structure(row)['exception'] == refs[i]['structure']['exception']
                             for i, row in cases.items()),
        'development_correct_grounded': sum(
            contract.judge(row, dev_ref[i], 'extract', json.dumps(source_structure(row)))['correct_grounded']
            for i, row in dev.items()),
        'summary': {'original_extraction': live['summary']['extract'], 'original_f1_gate': previous['after'],
                    **{route: contract.summarize(rows, groups, refs) for route, rows in routes.items()}},
        'rows': details,
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--verify', action='store_true')
    args = cli.parse_args()
    result = replay()
    if args.verify:
        contract.require(result == contract.read(HERE / 'results.json'), 'saved source-repair replay differs')
        print(f"Verified {len(result['rows'])} observed versions and {result['development_correct_grounded']} development passes.")
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
