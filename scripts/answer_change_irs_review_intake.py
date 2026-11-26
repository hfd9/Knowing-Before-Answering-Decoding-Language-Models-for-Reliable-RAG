"""Seal an input-only IRS review before releasing linked model outputs.

This checks document structure and literal spans, not reviewer independence or law.
No review is created, sent, or attributed by this tool.
"""
import argparse
from datetime import date
import json
import os
from pathlib import Path
from zipfile import ZipFile

import answer_change_irs_independent_packet as packet

PUBLIC = packet.PACK / 'public'
COORDINATOR = packet.PACK / 'coordination/mapping.json'
RUN = packet.ROOT / 'runs/answer-change-irs-review-intake-v1'
EXPECTED_PACKET = '82a898554515fd1aaa4c0865e9d684919ff33bee244b7d0160a2503e3404eb33'
EXPECTED_TEMPLATE = '45531c6988f72b915c76d70d0f801a3bc738905f3d22a30611bb270ba6efcda6'


def write_raw(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def validate(review, input_packet, template):
    packet.require(set(review) == set(template), 'review fields differ')
    packet.require(review['version'] == template['version'] == 1, 'review version differs')
    packet.require(isinstance(review['reviewer'], str) and review['reviewer'].strip(), 'reviewer missing')
    packet.require(isinstance(review['previous_exposure'], str) and review['previous_exposure'].strip(),
                   'exposure disclosure missing')
    packet.require(type(review['reviewed_without_model_outputs']) is bool, 'exposure flag required')
    source = {item['review_id']: item for item in input_packet['cases']}
    expected = {item['review_id']: item for item in template['cases']}
    rows = review['cases']
    packet.require(isinstance(rows, list) and len(rows) == len(source) == 6, 'case count differs')
    packet.require(len({item['review_id'] for item in rows}) == 6 and
                   {item['review_id'] for item in rows} == set(source) == set(expected), 'case IDs differ')
    for row in rows:
        rid = row['review_id']
        packet.require(set(row) == set(expected[rid]), 'case fields differ')
        texts = [turn['content'] for turn in source[rid]['messages']]
        for field in ('possible_date_1', 'possible_date_2'):
            value = row[field]
            packet.require(isinstance(value, str) and value and any(value in text for text in texts),
                           'possible date must occur in the input')
            try:
                parsed = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError('possible date must be ISO date') from exc
            packet.require(parsed.isoformat() == value, 'possible date must be ISO date')
        packet.require(row['possible_date_1'] != row['possible_date_2'], 'possible dates must differ')
        packet.require(row['actual_date_provided'] in
                       ('missing', 'unknown', row['possible_date_1'], row['possible_date_2']), 'invalid date status')
        for i in (1, 2):
            conclusion, quotes = row[f'branch_{i}_conclusion'], row[f'branch_{i}_support_quote']
            packet.require(conclusion in ('Y', 'N', 'unknown'), 'invalid branch conclusion')
            packet.require(isinstance(quotes, list) and all(isinstance(q, str) and q.strip() and
                           any(q in text for text in texts) for q in quotes), 'support quote not in input')
            packet.require(conclusion == 'unknown' or len(quotes) > 0, 'missing branch support')
        packet.require(row['unique_conclusion_for_case'] in ('Y', 'N', 'ambiguous', 'unknown'),
                       'invalid case conclusion')
        for field in ('material_sufficiency', 'author_metadata_dependency'):
            packet.require(row[field] in ('yes', 'no', 'unknown'), 'invalid material judgment')
        packet.require(isinstance(row['uncertainty_or_disagreement'], str), 'uncertainty disclosure required')
    return True


def seal(review_path):
    """Only public inputs and reviewer submission are read before the seal."""
    packet.require(not RUN.exists(), 'intake exists; preserve it for review')
    packet_raw = (PUBLIC / 'input-packet.json').read_bytes()
    template_raw = (PUBLIC / 'review-form.json').read_bytes()
    packet.require(packet.sha(packet_raw) == EXPECTED_PACKET and packet.sha(template_raw) == EXPECTED_TEMPLATE,
                   'public packet or template changed')
    review_raw = review_path.read_bytes()
    review = json.loads(review_raw)
    validate(review, json.loads(packet_raw), json.loads(template_raw))
    RUN.mkdir(parents=True, mode=0o700)
    write_raw(RUN / 'review.json', review_raw)
    seal_doc = {'input_packet_sha256': packet.sha(packet_raw), 'template_sha256': packet.sha(template_raw),
                'review_sha256': packet.sha(review_raw),
                'reviewed_without_model_outputs_self_reported': review['reviewed_without_model_outputs'],
                'independence_certified': False}
    write_raw(RUN / 'seal.json', packet.encode(seal_doc))
    print('Input review sealed. Reviewer independence remains unverified.')


def connect():
    """Verify the original seal before opening mapping and model responses."""
    seal_doc = json.loads((RUN / 'seal.json').read_bytes())
    review_raw = (RUN / 'review.json').read_bytes()
    packet_raw = (PUBLIC / 'input-packet.json').read_bytes()
    template_raw = (PUBLIC / 'review-form.json').read_bytes()
    packet.require(packet.sha(packet_raw) == EXPECTED_PACKET and packet.sha(template_raw) == EXPECTED_TEMPLATE,
                   'public packet or template changed')
    packet.require(seal_doc['review_sha256'] == packet.sha(review_raw) and
                   seal_doc['input_packet_sha256'] == packet.sha(packet_raw) and
                   seal_doc['template_sha256'] == packet.sha(template_raw), 'input review seal mismatch')
    validate(json.loads(review_raw), json.loads(packet_raw), json.loads(template_raw))
    packet.require(not (RUN / 'stage2.json').exists(), 'stage 2 exists; preserve it')
    _, expected_mapping, _ = packet.from_archive()
    mapping = json.loads(COORDINATOR.read_bytes())
    packet.require(mapping == expected_mapping, 'coordination mapping mismatch')
    with ZipFile(packet.SOURCE) as z:
        plan = json.loads(z.read('prepared/plan.json'))
        positions = {task['id']: index for index, task in enumerate(plan)}
        outputs = []
        for entry in mapping['entries']:
            record = json.loads(z.read(f'run/{positions[entry["original_task_id"]]:02d}.record.json'))
            packet.require(packet.sha(record['output'].encode('utf-8')) == entry['output_sha256'],
                           'model output hash mismatch')
            outputs.append({'review_id': entry['review_id'], 'model_output': record['output']})
    second = {'version': 1, 'input_review_seal_sha256': packet.sha((RUN / 'seal.json').read_bytes()),
              'source_archive_sha256': packet.EXPECTED_ARCHIVE, 'cases': outputs,
              'review_form': [{'review_id': item['review_id'], 'claims_actual_date': None,
                               'unconditional_conclusion': None, 'conditional_branches': None,
                               'asks_event_date': None, 'internal_contradiction': None,
                               'supporting_output_quotes': None, 'uncertainty_or_notes': None}
                              for item in outputs]}
    write_raw(RUN / 'stage2.json', packet.encode(second))
    print('Stage 2 prepared after input review seal; no scoring or independence claim.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='stage', required=True)
    one = sub.add_parser('seal')
    one.add_argument('review', type=Path)
    sub.add_parser('connect')
    opts = parser.parse_args()
    if opts.stage == 'seal':
        seal(opts.review)
    else:
        connect()
