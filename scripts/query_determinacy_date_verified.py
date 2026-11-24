"""Run or verify the bounded date-rule decision from a public packet."""

import argparse
import json
from pathlib import Path
import sys

from query_determinacy_date_diagnostic import solve_public, unresolved


def evaluate(packet, event_date=None):
    """Allow a terminal newline on a packet saved as a plain-text file."""
    packet = packet.replace('\r\n', '\n').removesuffix('\n')
    return solve_public(packet, event_date)


def index_claims(claims):
    by_date = {}
    issues = []
    if not isinstance(claims, list):
        return by_date, [{'code': 'invalid_branch_list'}]

    for index, claim in enumerate(claims):
        if (not isinstance(claim, dict) or set(claim) != {'date', 'answer', 'evidence'}
                or not isinstance(claim['date'], str) or type(claim['answer']) is not bool
                or not isinstance(claim['evidence'], list)
                or not all(isinstance(label, str) for label in claim['evidence'])
                or len(set(claim['evidence'])) != len(claim['evidence'])):
            issues.append({'code': 'invalid_branch', 'index': index})
            continue
        day = claim['date']
        if day in by_date:
            issues.append({'code': 'duplicate_branch', 'date': day})
        else:
            by_date[day] = claim
    return by_date, issues


def verify_branches(packet, claims, event_date=None):
    """Release the computed action only if every claimed branch agrees with the packet."""
    decision = evaluate(packet, event_date)
    if decision['action'] == 'unresolved':
        return decision

    by_date, issues = index_claims(claims)
    expected = {branch['date']: branch for branch in decision['branches']}
    for day in sorted(by_date.keys() - expected.keys()):
        issues.append({'code': 'unexpected_branch', 'date': day})
    for day, branch in expected.items():
        if day not in by_date:
            issues.append({'code': 'missing_branch', 'date': day})
            continue
        claim = by_date[day]
        if set(claim['evidence']) != set(branch['evidence']):
            issues.append({'code': 'evidence_does_not_match_date', 'date': day})
        if claim['answer'] is not branch['answer']:
            issues.append({'code': 'conclusion_does_not_match_rule', 'date': day})
    return dict(unresolved('unverified_branches'), issues=issues) if issues else decision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet', help='plain-text packet path; use - to read stdin')
    parser.add_argument('--event-date', help='supplied consummation date in YYYY-MM-DD format')
    parser.add_argument('--branches', type=Path, help='optional JSON file of branch claims to verify')
    args = parser.parse_args()

    try:
        packet = sys.stdin.read() if args.packet == '-' else Path(args.packet).read_text(encoding='utf-8')
        if args.branches is None:
            decision = evaluate(packet, args.event_date)
        else:
            claims = json.loads(args.branches.read_text(encoding='utf-8'))
            decision = verify_branches(packet, claims, args.event_date)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        parser.exit(2, f'{parser.prog}: {error}\n')
    print(json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
