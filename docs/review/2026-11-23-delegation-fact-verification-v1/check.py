"""Replay the sealed extraction cohort with a frozen F1 direction check."""
import argparse
from collections import Counter
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import query_determinacy_delegation_collect_v2 as live
from query_determinacy_delegation import structured_from_parser


LIVE = HERE.parent / '2026-11-23-rule-applicability-live-v1'
ARCHIVE = LIVE / 'heldout-raw.zip'
SCORES = LIVE / 'heldout-results.json'
contract = live.contract


def check_direction(records, model_grant):
    # The grant component of the frozen parser reads only F1.
    source_grant = structured_from_parser(records)['grant']
    if source_grant is None:
        return 'f1_unrecognized', source_grant
    if model_grant is None:
        return 'model_grant_missing', source_grant
    if model_grant == source_grant:
        return 'confirmed', source_grant
    reversed_grant = {'grantor': source_grant['recipient'], 'recipient': source_grant['grantor']}
    return ('roles_reversed' if model_grant == reversed_grant else 'different_roles'), source_grant


def replay():
    with TemporaryDirectory() as temp, ZipFile(ARCHIVE) as bundle:
        # Extract only the flat files used by the frozen archive verifier.
        names = bundle.namelist()
        contract.require(len(names) == len(set(names)) and all(Path(n).name == n for n in names),
                         'expected flat archive with unique file names')
        bundle.extractall(temp)
        original = live.score(Path(temp))
    contract.require(original == contract.read(SCORES), 'original sealed scores differ')
    contract.require(original['split'] == 'heldout', 'expected the held-out run')
    policy, _, _, _, inputs, references, groups = contract.load_packet()
    previous = original['rows']['extract']
    contract.require(not original['summary']['extract']['invalid'] and previous.keys() == inputs.keys(),
                     'expected all original extraction outputs to be scoreable')
    details = {}
    verified = {}
    for case_id, before in previous.items():
        records, ref = inputs[case_id], references[case_id]
        extracted = before['structure']
        status, from_f1 = check_direction(records, extracted['grant'])
        guarded = extracted if status == 'confirmed' else dict(extracted, grant=None)
        after = contract.judge(records, ref, 'extract', live.local.encode(guarded).decode())
        contract.require((after == before if status == 'confirmed' else after['final'] == 'X'),
                         'the check changed a confirmed result or failed to stop an unconfirmed one')
        verified[case_id] = after
        details[case_id] = {
            'root': ref['root'], 'wording': ref['wording'], 'f1': records['F1'],
            'check': status, 'f1_grant': from_f1, 'model_grant': extracted['grant'],
            'reference_final': ref['result']['final'],
            'before': {k: before[k] for k in ('final', 'correct_grounded', 'unfounded_unique')},
            'after': {k: after[k] for k in ('final', 'correct_grounded', 'unfounded_unique')},
        }

    old = original['summary']['extract']
    new = contract.summarize(verified, groups, references)
    stopped = sorted(set(old['unfounded_unique']) - set(new['unfounded_unique']))
    retain = [i for i in details if previous[i]['correct_grounded'] and verified[i]['correct_grounded']]
    lost = [i for i in details if previous[i]['correct_grounded'] and not verified[i]['correct_grounded']]
    return {
        'sources': {'archive_sha256': live.first.digest(ARCHIVE), 'original_scores_sha256': live.first.digest(SCORES),
                    'heldout_seal_sha256': original['seal_sha256']},
        'versions': len(details), 'roots': len(groups),
        'direction_check_counts': dict(Counter(row['check'] for row in details.values())),
        'before': old, 'after': new,
        'stopped_unfounded_unique_by_check': dict(Counter(details[i]['check'] for i in stopped)),
        'retained_correct_grounded': sorted(retain), 'lost_correct_grounded': sorted(lost),
        'new_unresolved': sorted(set(new['unresolved']) - set(old['unresolved'])),
        'compared_to_frozen_parser': contract.compare(new, original['summary']['parser'], policy),
        'rows': details,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result = replay()
    if args.verify:
        contract.require(result == contract.read(HERE / 'results.json'), 'saved direction-check result differs')
        print(f"Verified {result['versions']} sealed extraction outputs and their offline results.")
    else:
        print(live.local.encode(result).decode(), end='')


if __name__ == '__main__':
    main()
