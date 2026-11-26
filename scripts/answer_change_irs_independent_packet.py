"""Prepare input-only review packet for the two exposed IRS triads.

The coordinator mapping must not be given to the reviewer before input review.
This tool neither sends the packet nor claims independent review occurred.
"""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/review/2026-11-26-two-rule-7b-first-results-v1/raw.zip'
PACK = ROOT / 'docs/review/2026-11-26-irs-input-review-packet-v1'
RULE = 'eitc_investment'
EXPECTED_ARCHIVE = '62c6f10621994b60bffd5dd4775874ece3736bdcd0c5db180658dd8b98b474d5'
EXPECTED_SEAL = 'ee889482d8be85d3d8f45f4cf254364176cd264de03cba817b011e1106239fac'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def build(plan, records, source_sha, source_seal_sha):
    selected = [t for t in plan if t['route'] == 'direct' and t['case'].startswith(RULE + '/')]
    expected = {f'{RULE}/{group}/{state}/direct' for group in ('same', 'different')
                for state in ('missing', 'old', 'new')}
    require(len(selected) == 6 and {t['id'] for t in selected} == expected, 'unexpected selection')
    public, coordination = [], []
    for task in selected:
        record = records[task['id']]
        require(record['status'] == 'complete', 'first-turn output incomplete')
        identity = 'R' + sha(('irs_input_review_v1/' + task['id']).encode())[:12].upper()
        public.append({'review_id': identity, 'messages': task['messages']})
        coordination.append({'review_id': identity, 'original_task_id': task['id'],
            'messages_sha256': sha(encode(task['messages'])),
            'output_sha256': sha(record['output'].encode('utf-8'))})
    public.sort(key=lambda x: x['review_id'])
    coordination.sort(key=lambda x: x['review_id'])
    require(len({r['review_id'] for r in public}) == 6, 'review ID collision')
    packet = {'version': 1, 'purpose': 'input_only_task_interpretation_not_legal_gold',
              'cases': public}
    mapping = {'version': 1, 'status': 'prepared_not_reviewed', 'source_archive_sha256': source_sha,
               'source_run_seal_sha256': source_seal_sha, 'entries': coordination}
    form = {'version': 1, 'reviewer': None, 'previous_exposure': None, 'reviewed_without_model_outputs': None,
            'cases': [{'review_id': row['review_id'], 'actual_date_provided': None,
                       'possible_date_1': None, 'possible_date_2': None,
                       'branch_1_conclusion': None, 'branch_1_support_quote': None,
                       'branch_2_conclusion': None, 'branch_2_support_quote': None,
                       'unique_conclusion_for_case': None, 'material_sufficiency': None,
                       'author_metadata_dependency': None, 'uncertainty_or_disagreement': None}
                      for row in public]}
    return packet, mapping, form


def from_archive():
    source_sha = sha(SOURCE.read_bytes())
    require(source_sha == EXPECTED_ARCHIVE, 'source archive digest differs')
    with ZipFile(SOURCE) as z:
        seal_raw = z.read('run/seal.json')
        require(sha(seal_raw) == EXPECTED_SEAL, 'source seal digest differs')
        seal = json.loads(seal_raw)
        require(all(sha(z.read('run/' + name)) == h for name, h in seal.items()), 'source seal mismatch')
        plan = json.loads(z.read('prepared/plan.json'))
        records = {}
        for index, task in enumerate(plan):
            attempt = json.loads(z.read(f'run/{index:02d}.attempt.json'))
            record = json.loads(z.read(f'run/{index:02d}.record.json'))
            require(attempt['task'] == task and record['id'] == task['id'], 'source task mismatch')
            records[task['id']] = record
        return build(plan, records, source_sha, sha(seal_raw))


def main(verify):
    packet, mapping, form = from_archive()
    files = {'public/input-packet.json': packet, 'public/review-form.json': form,
             'coordination/mapping.json': mapping}
    for name, obj in files.items():
        path = PACK / name
        if verify:
            require(path.read_bytes() == encode(obj), f'{name} differs')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as out:
                out.write(encode(obj))
    print('Input packet replayed.' if verify else 'Input packet prepared.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    main(parser.parse_args().verify)
