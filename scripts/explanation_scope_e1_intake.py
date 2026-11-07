"""Seal E1 manual claim reviews before connecting mappings; no inference or semantic scoring."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

import explanation_scope_e1 as e1
import explanation_scope_metrics as metrics
import explanation_scope_runtime as scope
import explanation_scope_transaction_prototype as tx

EXPOSURES = {'unknown', 'declared_exposed', 'declared_unexposed'}
JUDGMENTS = {'supported', 'unsupported', 'contradicted', 'ambiguous', 'not_applicable'}
STATUSES = {'complete', 'empty', 'truncated', 'failed', 'not_collected'}
CLAIM_ID = re.compile(r'[A-Za-z0-9_-]{1,64}\Z')
MAX_BYTES = 16 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def exact(value, keys, label):
    require(isinstance(value, dict) and set(value) == set(keys), 'Invalid fields: ' + label)


def unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON key')
        value[key] = item
    return value


def read_json(path):
    fd = os.open(Path(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_BYTES, 'Bounded regular file required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(MAX_BYTES + 1)
        require(len(raw) <= MAX_BYTES, 'File too large')
    finally:
        os.close(fd)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON constant')))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Invalid UTF-8 JSON') from error
    return raw, value


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_raw_exclusive(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        raise  # Preserve partial artifacts.
    tx._fsync_dir(path.parent)


def empty_directory(path):
    target = Path(path)
    require(not target.is_symlink() and target.is_dir(), 'Existing non-symlink output directory required')
    target = target.resolve(strict=True)
    require(not any(target.iterdir()), 'Output directory must be empty; preserve prior files')
    require(stat.S_IMODE(target.stat().st_mode) & 0o077 == 0, 'Output directory must be private')
    return target


def forbid_overlap(output, paths):
    for path in paths:
        source = Path(path).resolve(strict=True)
        require(source != output and not source.is_relative_to(output), 'Input cannot be in output directory')


def validate_packet(packet):
    exact(packet, ('format', 'items', 'note'), 'packet')
    require(packet['format'] == 'e1-review-packet-v1' and nonempty(packet['note']), 'Wrong E1 packet')
    rows = packet['items']
    require(isinstance(rows, list) and len(rows) == 48, 'Packet must retain 48 slots')
    items = {}
    for row in rows:
        require(isinstance(row, dict), 'Invalid packet row')
        status = row.get('technical_status')
        exact(row, ('item_id', 'question', 'documents', 'technical_status', 'answer') if status == 'complete'
              else ('item_id', 'question', 'documents', 'technical_status'), 'packet row')
        iid = row['item_id']
        require(isinstance(iid, str) and iid not in items and status in STATUSES, 'Invalid packet identity or status')
        require(nonempty(row['question']) and isinstance(row['documents'], list) and len(row['documents']) == 5
                and all(nonempty(text) for text in row['documents']), 'Invalid packet input')
        if status == 'complete':
            require(nonempty(row['answer']), 'Complete output must be nonempty')
        items[iid] = row
    require(set(items) == {f'R{i:03d}' for i in range(1, 49)}, 'Packet pseudonym grid differs')
    return items


def citation(value, text, document=False):
    exact(value, ('document_index', 'start', 'end', 'quote') if document else ('start', 'end', 'quote'), 'citation')
    start, end = value['start'], value['end']
    require(type(start) is int and type(end) is int and 0 <= start < end <= len(text), 'Citation offset invalid')
    require(nonempty(value['quote']) and text[start:end] == value['quote'], 'Citation quote mismatch')


def doc_refs(refs, documents):
    require(isinstance(refs, list), 'Document references must be a list')
    for ref in refs:
        require(isinstance(ref, dict), 'Invalid document reference')
        slot = ref.get('document_index')
        require(type(slot) is int and 1 <= slot <= 5, 'Document slot must be 1–5')
        citation(ref, documents[slot - 1], document=True)


def validate_review(review, items):
    exact(review, ('reviewer_id', 'history_exposure', 'exposure_description', 'items'), 'review')
    require(nonempty(review['reviewer_id']) and review['history_exposure'] in EXPOSURES
            and nonempty(review['exposure_description']), 'Reviewer and exposure declaration required')
    rows = review['items']
    require(isinstance(rows, list) and len(rows) == 48, 'Review must retain 48 rows')
    by_id = {}
    for row in rows:
        exact(row, ('item_id', 'review_status', 'full_answer_reviewed', 'claims'), 'review row')
        iid = row['item_id']
        require(isinstance(iid, str) and iid in items and iid not in by_id, 'Unknown or duplicate review ID')
        require(type(row['full_answer_reviewed']) is bool and isinstance(row['claims'], list), 'Invalid review declaration')
        if row['review_status'] == 'unreviewed':
            require(row['full_answer_reviewed'] is False and not row['claims'], 'Unreviewed row contains claims')
        else:
            require(row['review_status'] == 'reviewed' and items[iid]['technical_status'] == 'complete'
                    and row['full_answer_reviewed'] is True and row['claims'], 'Only complete outputs can be reviewed')
            seen = set()
            for claim in row['claims']:
                exact(claim, ('claim_id', 'claim', 'role', 'judgment', 'reason', 'output_citation',
                              'document_support', 'counterevidence'), 'claim')
                cid = claim['claim_id']
                require(isinstance(cid, str) and CLAIM_ID.fullmatch(cid) is not None and cid not in seen,
                        'Invalid or duplicate claim ID')
                seen.add(cid)
                require(nonempty(claim['claim']) and nonempty(claim['reason'])
                        and claim['role'] in {'target', 'explanation', 'other'}
                        and claim['judgment'] in JUDGMENTS, 'Invalid claim judgment')
                citation(claim['output_citation'], items[iid]['answer'])
                doc_refs(claim['document_support'], items[iid]['documents'])
                doc_refs(claim['counterevidence'], items[iid]['documents'])
                require(claim['judgment'] != 'supported' or claim['document_support'], 'Supported claim needs evidence')
                require(claim['judgment'] != 'contradicted' or claim['counterevidence'], 'Contradicted claim needs counterevidence')
        by_id[iid] = row
    require(set(by_id) == set(items), 'Review grid differs')
    return by_id


def seal_review(packet_path, review_path, output_dir):
    """Only public packet and reviewer form are read; no coordinator or condition mapping."""
    packet_raw, packet = read_json(packet_path)
    review_raw, review = read_json(review_path)
    items = validate_packet(packet)
    rows = validate_review(review, items)
    output = empty_directory(output_dir)
    forbid_overlap(output, (packet_path, review_path))
    receipt = {'format': 'e1-claim-review-seal-v1', 'e1_protocol_sha256': e1.PROTOCOL_SHA256,
        'packet_bytes_sha256': sha(packet_raw), 'packet_canonical_sha256': scope.json_sha(packet),
        'review_bytes_sha256': sha(review_raw), 'intake_code_sha256': sha(Path(__file__).read_bytes()),
        'sealed_at_utc': datetime.now(timezone.utc).isoformat(),
        'reviewed_items': sum(row['review_status'] == 'reviewed' for row in rows.values()),
        'reviewer_id': review['reviewer_id'], 'history_exposure': review['history_exposure'],
        'independent_approval': False}
    write_raw_exclusive(output / 'review.json', review_raw)
    tx._exclusive(output / 'receipt.json', receipt)
    return receipt


def check_lock():
    e1.check_protocol()
    _, lock = read_json(e1.IMPLEMENTATION_LOCK)
    expected_names = set(e1.IMPLEMENTATION)
    exact(lock, ('e1_protocol_sha256', 'source_plan_sha256', 'implementation_sha256',
                 'formal_gate', 'gpu_launch_ready'), 'E1 implementation lock')
    require(lock.get('e1_protocol_sha256') == e1.PROTOCOL_SHA256
            and lock.get('formal_gate') is False and lock.get('gpu_launch_ready') is False,
            'E1 lock status differs')
    require(isinstance(lock.get('implementation_sha256'), dict)
            and set(lock['implementation_sha256']) == expected_names, 'E1 implementation inventory differs')
    for name, expected in lock['implementation_sha256'].items():
        require(sha((e1.ROOT / name).read_bytes()) == expected, 'E1 implementation differs: ' + name)
    require(sha(e1.ledger.PLAN_PATH.read_bytes()) == lock.get('source_plan_sha256'), 'E1 source plan differs')


def verify_sealed_review(packet_raw, packet, sealed_dir):
    directory = Path(sealed_dir)
    require(not directory.is_symlink() and directory.is_dir()
            and {p.name for p in directory.iterdir()} == {'review.json', 'receipt.json'}, 'Incomplete review seal')
    review_raw, review = read_json(directory / 'review.json')
    receipt_raw, receipt = read_json(directory / 'receipt.json')
    keys = ('format', 'e1_protocol_sha256', 'packet_bytes_sha256', 'packet_canonical_sha256',
            'review_bytes_sha256', 'intake_code_sha256', 'sealed_at_utc', 'reviewed_items',
            'reviewer_id', 'history_exposure', 'independent_approval')
    exact(receipt, keys, 'review receipt')
    require(receipt['format'] == 'e1-claim-review-seal-v1' and receipt['e1_protocol_sha256'] == e1.PROTOCOL_SHA256
            and receipt['packet_bytes_sha256'] == sha(packet_raw) and receipt['packet_canonical_sha256'] == scope.json_sha(packet)
            and receipt['review_bytes_sha256'] == sha(review_raw)
            and receipt['intake_code_sha256'] == sha(Path(__file__).read_bytes())
            and receipt['independent_approval'] is False, 'Review seal binding differs')
    try:
        sealed_at = datetime.fromisoformat(receipt['sealed_at_utc'])
    except (ValueError, TypeError) as error:
        raise ValueError('Invalid seal timestamp') from error
    require(sealed_at.utcoffset() is not None, 'Seal timestamp lacks timezone')
    rows = validate_review(review, validate_packet(packet))
    require(type(receipt['reviewed_items']) is int
            and receipt['reviewed_items'] == sum(row['review_status'] == 'reviewed' for row in rows.values())
            and receipt['reviewer_id'] == review['reviewer_id'] and receipt['history_exposure'] == review['history_exposure'],
            'Review receipt differs')
    return review_raw, review, receipt_raw, receipt, rows


def validate_coordinator(packet, coordinator, export_seal):
    items = validate_packet(packet)
    require(isinstance(coordinator, dict) and coordinator.get('format') == 'e1-review-coordinator-v1'
            and coordinator.get('protocol_sha256') == e1.PROTOCOL_SHA256
            and type(coordinator.get('synthetic_fixture')) is bool
            and coordinator.get('public_packet_sha256') == scope.json_sha(packet), 'Coordinator binding differs')
    require(export_seal == {'packet_sha256': scope.json_sha(packet),
                            'coordinator_sha256': scope.json_sha(coordinator)}, 'Export seal differs')
    sources = coordinator.get('mapping_and_sources')
    require(isinstance(sources, dict) and set(sources) == set(items), 'Coordinator map differs')
    template = coordinator.get('endpoint_template')
    require(isinstance(template, dict) and template.get('e1_protocol_sha256') == e1.PROTOCOL_SHA256,
            'Template protocol differs')
    indexed = metrics.validate(template)
    seen_source = set()
    for (scene, condition), row in indexed.items():
        iid = row.get('source_item_id')
        require(iid in sources and iid not in seen_source and row['review_status'] == 'unreviewed',
                'Template identity differs')
        seen_source.add(iid)
        source, item = sources[iid], items[iid]
        require(isinstance(source, dict) and source.get('source_item_id') == f'exs{scene:02d}_{condition}'
                and source.get('technical_status') == item['technical_status'] == row['technical_status']
                and source.get('input_sha256') == scope.input_payload_sha(item) == row['input_sha256']
                and source.get('output_sha256') == row['output_sha256'], 'Source binding differs')
        if item['technical_status'] == 'complete':
            require(source['output_sha256'] == scope.text_sha(item['answer']), 'Output hash differs')
    require(seen_source == set(items), 'Source map not bijective')
    return template


def connect(packet_path, sealed_dir, coordinator_path, export_seal_path, conversion_path, output_dir):
    """Verify the sealed public stage before reading condition-bearing coordinator files."""
    packet_raw, packet = read_json(packet_path)
    review_raw, review, receipt_raw, receipt, reviewed = verify_sealed_review(packet_raw, packet, sealed_dir)
    check_lock()
    coordinator_raw, coordinator = read_json(coordinator_path)
    export_raw, export_seal = read_json(export_seal_path)
    template = validate_coordinator(packet, coordinator, export_seal)
    conversion_raw, conversion = read_json(conversion_path)
    exact(conversion, ('converter_id', 'history_exposure', 'exposure_description', 'sealed_review_sha256', 'items'), 'conversion')
    require(nonempty(conversion['converter_id']) and conversion['history_exposure'] in EXPOSURES
            and nonempty(conversion['exposure_description'])
            and conversion['sealed_review_sha256'] == receipt['review_bytes_sha256'], 'Conversion provenance differs')
    require(isinstance(conversion['items'], list), 'Conversion items must be a list')
    rows = {row['source_item_id']: row for row in template['rows']}
    seen = set()
    for conversion_row in conversion['items']:
        exact(conversion_row, ('item_id', 'claim_ids', 'rationale', 'fields'), 'conversion row')
        iid = conversion_row['item_id']
        require(isinstance(iid, str) and iid in rows and iid not in seen, 'Unknown or duplicate conversion ID')
        seen.add(iid)
        require(reviewed[iid]['review_status'] == 'reviewed' and nonempty(conversion_row['rationale']),
                'Conversion requires a sealed reviewed row and rationale')
        ids = conversion_row['claim_ids']
        claim_ids = {claim['claim_id'] for claim in reviewed[iid]['claims']}
        require(isinstance(ids, list) and ids and all(isinstance(x, str) for x in ids)
                and len(ids) == len(set(ids)) and set(ids) <= claim_ids, 'Conversion claim references differ')
        fields = conversion_row['fields']
        exact(fields, metrics.FIELDS, 'endpoint fields')
        rows[iid].update(fields)
        rows[iid]['review_status'] = 'reviewed'
    template['provenance'] = {'reviewer_id': conversion['converter_id'],
                              'history_exposure': conversion['history_exposure'],
                              'description': conversion['exposure_description']}
    metrics.validate(template)
    summary = metrics.summarize(template)
    output = empty_directory(output_dir)
    forbid_overlap(output, (packet_path, coordinator_path, export_seal_path, conversion_path,
                            Path(sealed_dir) / 'review.json', Path(sealed_dir) / 'receipt.json'))
    result_receipt = {'format': 'e1-claim-conversion-receipt-v1', 'e1_protocol_sha256': e1.PROTOCOL_SHA256,
        'packet_bytes_sha256': sha(packet_raw), 'review_bytes_sha256': sha(review_raw),
        'review_receipt_bytes_sha256': sha(receipt_raw), 'coordinator_bytes_sha256': sha(coordinator_raw),
        'export_seal_bytes_sha256': sha(export_raw), 'conversion_bytes_sha256': sha(conversion_raw),
        'endpoint_canonical_sha256': scope.json_sha(template), 'summary_canonical_sha256': scope.json_sha(summary),
        'intake_code_sha256': sha(Path(__file__).read_bytes()),
        'implementation_lock_sha256': sha(e1.IMPLEMENTATION_LOCK.read_bytes()),
        'reviewer_id': review['reviewer_id'], 'reviewer_exposure': review['history_exposure'],
        'converter_id': conversion['converter_id'], 'converter_exposure': conversion['history_exposure'],
        'converted_items': len(seen), 'converted_at_utc': datetime.now(timezone.utc).isoformat(),
        'independent_approval': False, 'formal_gate': False, 'gpu_launch_ready': False,
        'semantic_truth_verified': False, 'raw_cache_bytes_verified_by_intake': False}
    write_raw_exclusive(output / 'conversion.json', conversion_raw)
    tx._exclusive(output / 'endpoints.json', template)
    tx._exclusive(output / 'summary.json', summary)
    tx._exclusive(output / 'receipt.json', result_receipt)
    return result_receipt, summary


def verify_result(packet_path, sealed_dir, coordinator_path, export_seal_path, result_dir):
    """Replay into a temporary private directory; existing inputs and results remain unchanged."""
    directory = Path(result_dir)
    require(not directory.is_symlink() and directory.is_dir()
            and {p.name for p in directory.iterdir()} == {'conversion.json', 'endpoints.json', 'summary.json', 'receipt.json'},
            'Incomplete conversion result')
    _, endpoints = read_json(directory / 'endpoints.json')
    _, summary = read_json(directory / 'summary.json')
    _, receipt = read_json(directory / 'receipt.json')
    require(isinstance(receipt, dict) and nonempty(receipt.get('converted_at_utc')), 'Invalid conversion receipt')
    try:
        recorded_time = datetime.fromisoformat(receipt['converted_at_utc'])
    except ValueError as error:
        raise ValueError('Invalid conversion time') from error
    require(recorded_time.utcoffset() is not None, 'Conversion time lacks timezone')
    with tempfile.TemporaryDirectory(prefix='e1-intake-replay-') as temporary:
        replay_receipt, replay_summary = connect(packet_path, sealed_dir, coordinator_path, export_seal_path,
                                                 directory / 'conversion.json', temporary)
        _, replay_endpoints = read_json(Path(temporary) / 'endpoints.json')
    require(endpoints == replay_endpoints and summary == replay_summary, 'Endpoint or summary replay differs')
    without_time = lambda data: {key: value for key, value in data.items() if key != 'converted_at_utc'}
    require(without_time(receipt) == without_time(replay_receipt), 'Conversion receipt replay differs')
    return {'status': 'source_bindings_and_declared_endpoint_summary_replayed_not_semantic_certification',
            'reviewed_slots': summary['reviewed_slots'], 'planned_slots': summary['planned_slots'],
            'planned_pairs': summary['primary']['planned_pairs'], 'formal_gate': False,
            'gpu_launch_ready': False, 'independent_approval': False, 'semantic_truth_verified': False,
            'raw_cache_bytes_verified_by_intake': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='stage', required=True)
    seal = sub.add_parser('seal')
    seal.add_argument('--packet', required=True)
    seal.add_argument('--review', required=True)
    seal.add_argument('--output-dir', required=True)
    convert = sub.add_parser('connect')
    for name in ('packet', 'sealed-dir', 'coordinator', 'export-seal', 'conversion', 'output-dir'):
        convert.add_argument('--' + name, required=True)
    verify = sub.add_parser('verify')
    for name in ('packet', 'sealed-dir', 'coordinator', 'export-seal', 'result-dir'):
        verify.add_argument('--' + name, required=True)
    args = parser.parse_args()
    if args.stage == 'seal':
        result = seal_review(args.packet, args.review, args.output_dir)
    elif args.stage == 'connect':
        result, _ = connect(args.packet, args.sealed_dir, args.coordinator, args.export_seal,
                            args.conversion, args.output_dir)
    else:
        result = verify_result(args.packet, args.sealed_dir, args.coordinator, args.export_seal, args.result_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
