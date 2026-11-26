"""Recompute mechanical diagnostics from sealed outputs and informed ratings."""
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REFERENCE = ROOT / 'docs/review/2026-11-26-new-rule-materials-v1/reference.json'
PREPARED = ROOT / 'docs/review/2026-11-26-two-rule-7b-first-v1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run():
    refs = json.loads(REFERENCE.read_text())['cases']
    ratings = list(csv.DictReader((HERE / 'ratings.csv').open()))
    assert len(ratings) == 24
    archive_path = HERE / 'raw.zip'
    with ZipFile(archive_path) as z:
        seal = json.loads(z.read('run/seal.json'))
        assert all(sha(z.read('run/' + n)) == h for n, h in seal.items())
        assert z.read('prepared/plan.json') == (PREPARED / 'plan.json').read_bytes()
        assert z.read('prepared/manifest.json') == (PREPARED / 'manifest.json').read_bytes()
        plan = json.loads(z.read('prepared/plan.json'))
        assert len(plan) == 24
        records = {}
        for i, task in enumerate(plan):
            attempt = json.loads(z.read(f'run/{i:02d}.attempt.json'))
            row = json.loads(z.read(f'run/{i:02d}.record.json'))
            assert attempt['task'] == task and row['id'] == task['id']
            assert row['status'] == 'complete' and row['eos_token_ids'] == [151645, 151643]
            assert row['generated_token_ids'][-1] in row['eos_token_ids']
            assert task['id'] not in records
            records[task['id']] = row
    expected_ids = set(records)
    assert {r['case'] + '/' + r['route'] for r in ratings} == expected_ids
    groups = collections.Counter()
    for row in ratings:
        case, route = row['case'], row['route']
        output = records[case + '/' + route]['output']
        ids = set(re.findall(r'\b(?:E\d+|F\d+)\b', output))
        assert ids == set(row['citation_ids'].split('|'))
        branch = refs[case]['branches']
        expected = '|'.join('Y' if value else 'N' for value in branch.values())
        assert expected == row['reference']
        groups[(route, case.split('/')[-1], row['content_status'])] += 1
        if case.endswith('/missing'):
            assert row['asks_date'] == 'no' and '?' not in output
        else:
            assert row['asks_date'] == 'na' and row['unique_status'] == 'na'
    pairs = {}
    for route in ('direct', 'by_version'):
        for rule in ('adviser_aum', 'eitc_investment'):
            matched = [r for r in ratings if r['route'] == route and r['case'] in
                       (f'{rule}/same/missing', f'{rule}/different/missing')]
            assert len(matched) == 2
            pairs[route + '/' + rule] = {
                'unique_pair_correct': all(x['unique_status'] == 'correct' for x in matched),
                'content_pair_correct': all(x['content_status'] == 'correct' for x in matched)}
    return {'archive_sha256': sha(archive_path.read_bytes()), 'ratings_sha256': sha((HERE / 'ratings.csv').read_bytes()),
            'reference_sha256': sha(REFERENCE.read_bytes()), 'records': len(records),
            'manually_assessed_direct_date_requests': 0,
            'status_counts': {'/'.join(k): v for k, v in sorted(groups.items())}, 'pairs': pairs,
            'semantic_judgments_automatically_verified': False}


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False, indent=2))
