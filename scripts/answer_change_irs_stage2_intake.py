"""Prepare and preserve second-stage review; validates structure, not truth or independence."""
import argparse
from datetime import datetime
import json
from pathlib import Path

import answer_change_irs_independent_packet as packet
import answer_change_irs_review_intake as first

FIELDS = ('claims_actual_date', 'unconditional_conclusion', 'conditional_branches',
          'asks_event_date', 'internal_contradiction')
LABELS = {'yes', 'no', 'unknown', 'not_applicable'}


def checked_context():
    """Recheck first seal, source archive and output hashes before using stage 2."""
    root = first.RUN
    seal_raw = (root / 'seal.json').read_bytes()
    first_seal = json.loads(seal_raw)
    review_raw = (root / 'review.json').read_bytes()
    input_raw = (first.PUBLIC / 'input-packet.json').read_bytes()
    template_raw = (first.PUBLIC / 'review-form.json').read_bytes()
    packet.require(packet.sha(input_raw) == first.EXPECTED_PACKET and
                   packet.sha(template_raw) == first.EXPECTED_TEMPLATE, 'public input changed')
    packet.require(first_seal['review_sha256'] == packet.sha(review_raw) and
                   first_seal['input_packet_sha256'] == packet.sha(input_raw) and
                   first_seal['template_sha256'] == packet.sha(template_raw) and
                   first_seal['independence_certified'] is False and
                   first_seal['reviewed_without_model_outputs_self_reported'] ==
                   json.loads(review_raw)['reviewed_without_model_outputs'], 'first-stage seal mismatch')
    first.validate(json.loads(review_raw), json.loads(input_raw), json.loads(template_raw))
    _, expected_mapping, _ = packet.from_archive()
    mapping = json.loads(first.COORDINATOR.read_bytes())
    packet.require(mapping == expected_mapping, 'coordination mapping mismatch')
    raw = (root / 'stage2.json').read_bytes()
    stage = json.loads(raw)
    packet.require(set(stage) == {'version', 'input_review_seal_sha256', 'source_archive_sha256',
                                  'cases', 'review_form'} and stage['version'] == 1 and
                   stage['input_review_seal_sha256'] == packet.sha(seal_raw) and
                   stage['source_archive_sha256'] == packet.EXPECTED_ARCHIVE, 'stage 2 binding mismatch')
    outputs = stage['cases']
    entries = mapping['entries']
    packet.require(isinstance(outputs, list) and len(outputs) == len(entries) == 6, 'stage 2 cases mismatch')
    packet.require([x['review_id'] for x in outputs] == [x['review_id'] for x in entries], 'stage 2 IDs mismatch')
    for output, entry in zip(outputs, entries):
        packet.require(set(output) == {'review_id', 'model_output'} and
                       isinstance(output['model_output'], str) and
                       packet.sha(output['model_output'].encode()) == entry['output_sha256'],
                       'stage 2 output mismatch')
    expected_form = [dict(review_id=x['review_id'], **{k: None for k in FIELDS},
                          supporting_output_quotes=None, uncertainty_or_notes=None) for x in outputs]
    packet.require(stage['review_form'] == expected_form, 'stage 2 blank form changed')
    return stage, seal_raw, raw


def make_template(stage):
    return {'version': 1, 'reviewer': None, 'reviewed_at': None, 'exposure_and_role': None,
            'cases': stage['review_form']}


def validate(review, stage):
    packet.require(isinstance(review, dict) and set(review) ==
                   {'version', 'reviewer', 'reviewed_at', 'exposure_and_role', 'cases'} and
                   review['version'] == 1, 'review fields differ')
    for field in ('reviewer', 'exposure_and_role'):
        packet.require(isinstance(review[field], str) and review[field].strip(), f'{field} missing')
    try:
        when = datetime.fromisoformat(review['reviewed_at'])
    except (ValueError, TypeError) as exc:
        raise ValueError('reviewed_at must be an ISO timestamp with timezone') from exc
    packet.require(when.tzinfo is not None and when.utcoffset() is not None, 'reviewed_at requires timezone')
    rows, outputs = review['cases'], stage['cases']
    packet.require(isinstance(rows, list) and len(rows) == len(outputs), 'review case count differs')
    ids = [row['review_id'] for row in rows]
    packet.require(len(set(ids)) == len(ids) and set(ids) == {x['review_id'] for x in outputs},
                   'review IDs differ')
    by_id = {x['review_id']: x['model_output'] for x in outputs}
    for row in rows:
        packet.require(set(row) == {'review_id', *FIELDS, 'supporting_output_quotes', 'uncertainty_or_notes'},
                       'case fields differ')
        packet.require(all(row[field] in LABELS for field in FIELDS), 'invalid observation label')
        quotes = row['supporting_output_quotes']
        packet.require(isinstance(quotes, list) and all(isinstance(q, str) and q.strip() and
                       q in by_id[row['review_id']] for q in quotes), 'output quote not in output')
        packet.require(not any(row[field] == 'yes' for field in FIELDS) or quotes,
                       'positive observation needs output quote')
        packet.require(isinstance(row['uncertainty_or_notes'], str) and row['uncertainty_or_notes'].strip(),
                       'notes required')
    return True


def prepare():
    stage, _, _ = checked_context()
    first.write_raw(first.RUN / 'stage2-review-template.json', packet.encode(make_template(stage)))
    print('Blank stage 2 review template prepared; no review occurred.')


def seal(review_path):
    stage, first_seal, stage_raw = checked_context()
    raw = review_path.read_bytes()
    review = json.loads(raw)
    validate(review, stage)
    target = first.RUN / 'stage2-review'
    packet.require(not target.exists(), 'stage 2 review exists; preserve it')
    target.mkdir(mode=0o700)
    first.write_raw(target / 'review.json', raw)
    seal_doc = {'version': 1, 'stage1_seal_sha256': packet.sha(first_seal),
                'stage2_sha256': packet.sha(stage_raw), 'stage2_review_sha256': packet.sha(raw),
                'source_archive_sha256': packet.EXPECTED_ARCHIVE, 'independence_certified': False}
    first.write_raw(target / 'seal.json', packet.encode(seal_doc))
    print('Stage 2 review sealed; judgments and independence remain unverified.')


def verify():
    stage, first_seal, stage_raw = checked_context()
    target = first.RUN / 'stage2-review'
    raw = (target / 'review.json').read_bytes()
    seal_doc = json.loads((target / 'seal.json').read_bytes())
    expected = {'version': 1, 'stage1_seal_sha256': packet.sha(first_seal),
                'stage2_sha256': packet.sha(stage_raw), 'stage2_review_sha256': packet.sha(raw),
                'source_archive_sha256': packet.EXPECTED_ARCHIVE, 'independence_certified': False}
    packet.require(seal_doc == expected, 'stage 2 review seal mismatch')
    validate(json.loads(raw), stage)
    print('Stage 2 review replayed; judgments and independence remain unverified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    sub.add_parser('verify')
    command = sub.add_parser('seal')
    command.add_argument('review', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    elif args.action == 'seal':
        seal(args.review)
    else:
        verify()
