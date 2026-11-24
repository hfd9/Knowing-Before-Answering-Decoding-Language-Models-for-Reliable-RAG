"""Replay the command-line entry point on the frozen first and second turns."""

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


PACK = Path(__file__).resolve().parent
ROOT = PACK.parents[2]
ENTRY = ROOT / 'scripts/query_determinacy_date_verified.py'
sys.path.insert(0, str(ENTRY.parent))

import query_determinacy_date_diagnostic as diagnostic  # noqa: E402


def archived_claim(row):
    answer, evidence = diagnostic.REPLY.fullmatch(row['output'].strip()).groups()
    return {'date': row['day'], 'answer': answer.upper() == 'YES', 'evidence': diagnostic.cited(evidence)}


def read_cli(packet, claim_file, *, event_date=None, claims=None):
    command = [sys.executable, str(ENTRY), '-']
    if event_date:
        command.extend(['--event-date', event_date])
    if claims is not None:
        claim_file.write_text(json.dumps(claims), encoding='utf-8')
        command.extend(['--branches', str(claim_file)])
    return json.loads(subprocess.run(command, input=packet + '\n', text=True, capture_output=True, check=True).stdout)


def run():
    inputs, rows = diagnostic.archived_rows()
    first = {case: [] for case in inputs}
    follow = {}
    for row in rows:
        if row['method'] != 'by_version':
            continue
        if row['turn'] == 1:
            first[row['case']].append(row)
        else:
            date = diagnostic.SUPPLIED.match(row['messages'][-1]['content'])[1]
            diagnostic.require(date == row['day'] and date not in follow, 'archived follow-up date mismatch')
            follow[date] = [row]

    def replay_group(packet, rows, claim_file, event_date=None):
        direct = read_cli(packet, claim_file, event_date=event_date)
        claims = [archived_claim(row) for row in rows]
        archive = read_cli(packet, claim_file, event_date=event_date, claims=claims)
        recomputed_claims = [{key: branch[key] for key in ('date', 'answer', 'evidence')}
                             for branch in direct['branches']]
        computed = read_cli(packet, claim_file, event_date=event_date, claims=recomputed_claims)
        diagnostic.require(computed == direct, 'verified program branches differ from direct evaluation')
        return {'original_claims': claims, 'verified_archive': archive, 'source_decision': direct,
                'verified_computed_branches': computed['action']}

    with TemporaryDirectory(prefix='kba-date-verified-') as work:
        claim_file = Path(work) / 'claims.json'
        initial = {case: replay_group(inputs[case], items, claim_file) for case, items in first.items()}
        continued = {date: replay_group(inputs['R06'], items, claim_file, date) for date, items in follow.items()}
        r06 = initial['R06']
        corrected_evidence = {branch['date']: branch['evidence'] for branch in r06['source_decision']['branches']}
        evidence_only = [dict(claim, evidence=corrected_evidence[claim['date']]) for claim in r06['original_claims']]
        evidence_only_replay = read_cli(inputs['R06'], claim_file, claims=evidence_only)

    # Score after the command finishes. The entry point never reads the author reference.
    reference_file = diagnostic.pilot.MATERIAL / 'reference.json'
    reference = diagnostic.pilot.read(reference_file)['cases']
    follow_reference = {item['event_date']: item for item in reference.values() if item['option'] == 'B' and item['event_date']}
    summaries = {}
    for split, groups, gold in (('first', initial, reference), ('follow', continued, follow_reference)):
        issues = Counter(issue['code'] for item in groups.values() for issue in item['verified_archive'].get('issues', []))
        summaries[split] = {'groups': len(groups), 'issues': dict(issues),
                            'archived_branches': sum(len(item['original_claims']) for item in groups.values()),
                            'source_strict': sum(diagnostic.grounded(item['source_decision'], gold[key])
                                                 for key, item in groups.items()),
                            'archive_strict': sum(diagnostic.grounded(item['verified_archive'], gold[key])
                                                  for key, item in groups.items())}
    fingerprints = {str(path.relative_to(ROOT)): diagnostic.pilot.local.hash_file(path) for path in
                    (diagnostic.ARCHIVE, diagnostic.pilot.MATERIAL / 'inputs.json', reference_file,
                     ENTRY, Path(diagnostic.__file__), Path(__file__).resolve())}
    return {'source_sha256': fingerprints, 'archived_calls': len(rows), 'first': initial, 'follow': continued,
            'evidence_only_r06': evidence_only_replay, 'summary': summaries}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    report = diagnostic.pilot.local.encode(run())
    if args.verify:
        diagnostic.require(report == (PACK / 'results.json').read_bytes(), 'CLI replay differs')
        print('Date entry point replay passed.')
    else:
        print(report.decode(), end='')


if __name__ == '__main__':
    main()
