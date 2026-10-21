"""CPU-only replay of sealed, history-exposed manual behavior judgments.

This module validates evidence and summarizes existing judgments. It never scores
language with keywords, approves semantic labels, loads a model, or changes a run.
"""

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

from semantic_transfer_metrics import BEHAVIOR_FIELDS, behavior_summary

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'docs/records/2026-10-21-semantic-transfer-exploratory-behavior'
RUN = 'runs/qwen2.5-3b-semantic-transfer-exploratory-v5-v1'
AUTHOR = 'docs/records/2026-10-21-semantic-transfer-v5-acceptance-ratings.json'
MATERIALS = 'runs/qwen2.5-3b-semantic-transfer-materials-v5/materials/inputs.json'
VALUES = {'yes', 'no', 'unknown'}
BASE_METADATA = dict(history_exposed=True, independent_gold=False,
    approved_for_training=False, formal_semantic_labels_added=0,
    new_gpu_calls=0, new_probe_fits=0)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(root, path):
    return json.loads((root / path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_metadata(value):
    for key, expected in BASE_METADATA.items():
        require(type(value.get(key)) is type(expected) and value[key] == expected,
            'Review exposure/authorization metadata mismatch: ' + key)


def verify_files(root, files):
    for name, expected in files.items():
        require(digest((root / name).read_bytes()) == expected, 'Hash mismatch: ' + name)


def check_citation(citation, text, hash_key):
    a, b = citation.get('start'), citation.get('end')
    require(type(a) is int and type(b) is int and 0 <= a < b <= len(text),
        'Citation offsets must be nonempty character offsets')
    require(citation.get('quote') == text[a:b], 'Citation text mismatch')
    require(citation.get(hash_key) == digest(text.encode()), 'Citation source hash mismatch')


def validate_ratings(packet, review):
    check_metadata(review)
    items = {r['item_id']: r for r in packet['items']}
    require(len(items) == len(packet['items']) == 240, 'Packet must contain 240 unique items')
    ratings = review['ratings']
    require(len(ratings) == 240 and {r['item_id'] for r in ratings} == set(items),
        'Ratings must be a 240-item bijection')
    for r in ratings:
        item = items[r['item_id']]
        require(r.get('status') == 'reviewed' and bool(r.get('rationale')), 'Unreviewed row')
        require(all(r.get(f) in VALUES for f in BEHAVIOR_FIELDS), 'Invalid behavior value')
        require(r.get('read_document_slots') == [dict(document_index=i + 1,
            sha256=digest(d.encode())) for i, d in enumerate(item['documents'])],
            'Five document reading references mismatch')
        require(len(item['documents']) == 5 and bool(r['input_citations']), 'Missing input evidence')
        for c in r['input_citations']:
            slot = c.get('document_index')
            require(type(slot) is int and 1 <= slot <= 5, 'Invalid document index')
            check_citation(c, item['documents'][slot - 1], 'document_sha256')
        require(bool(r['output_citations']), 'Missing output evidence')
        for c in r['output_citations']:
            check_citation(c, item['answer'], 'answer_sha256')
        require(any(c['start'] == 0 and c['end'] == len(item['answer'])
            for c in r['output_citations']), 'Complete answer citation required')
        if r['selection_without_resolution'] == 'yes':
            require(r['selects_single_answer'] == r['has_substantive_answer'] == 'yes'
                and r['has_supplied_resolution'] == 'no', 'Contradictory unresolved selection')
        if r['answer_grounded_correct'] == 'yes':
            require(r['has_substantive_answer'] == 'yes', 'Grounded answer without answer')
    return {r['item_id']: r for r in ratings}


def load_sealed(root):
    seal = read(root, PREFIX + '-seal.json')
    check_metadata(seal)
    require(seal['stage'] == 'behavior_scoring_sealed_before_rowwise_join'
        and seal['rowwise_join_started'] is False, 'Wrong seal stage')
    verify_files(root, seal['artifacts'])
    packet_path = RUN + '/behavior_review/packet.json'
    packet = read(root, packet_path)
    review = read(root, PREFIX + '-ratings.json')
    require(review['packet_sha256'] == digest((root / packet_path).read_bytes()),
        'Wrong packet binding')
    require(review['rubric_sha256'] == digest((root / (PREFIX + '-rubric.json')).read_bytes()),
        'Wrong rubric binding')
    manual_bytes = (root / (PREFIX + '-manual.txt')).read_bytes()
    require(review['manual_sha256'] == digest(manual_bytes), 'Wrong manual binding')
    ratings = validate_ratings(packet, review)
    lines = manual_bytes.decode().splitlines()
    require(len(lines) == 240 and len({line.split('|')[0] for line in lines}) == 240,
        'Manual rows are not unique and complete')
    for line in lines:
        key, code, slots, reason = line.split('|')
        r = ratings[key]
        require(dict(zip(BEHAVIOR_FIELDS, [{'y': 'yes', 'n': 'no', '?': 'unknown'}[c]
            for c in code])) == {f: r[f] for f in BEHAVIOR_FIELDS}, 'Manual code mismatch')
        require(reason == r['rationale'] and list(map(int, slots.split(','))) ==
            [c['document_index'] for c in r['input_citations']], 'Manual evidence mismatch')
    inventory = read(root, PREFIX + '-reading-inventory.json')
    require(inventory['document_slots'] == 1200 and inventory['unique_documents'] == 435,
        'Wrong reading inventory counts')
    catalog = {d['document_id']: d['sha256'] for d in inventory['document_catalog']}
    items = {r['item_id']: r for r in packet['items']}
    require(len(inventory['items']) == 240 and {r['item_id'] for r in inventory['items']} == set(items),
        'Wrong reading inventory membership')
    for r in inventory['items']:
        require([catalog[k] for k in r['document_refs']] ==
            [digest(d.encode()) for d in items[r['item_id']]['documents']], 'Reading references mismatch')
    preserved = read(root, PREFIX + '-preserved.json')
    require(len(preserved) == 869, 'Wrong preservation inventory')
    verify_files(root, preserved)
    return packet, ratings, seal


def rate(rows, field):
    counts = Counter(r[field] for r in rows)
    require(not set(counts) - VALUES, 'Invalid rate values')
    n, yes, unknown = len(rows), counts['yes'], counts['unknown']
    return dict(eligible=n, yes=yes, no=counts['no'], unknown=unknown,
        point=yes / n if n and not unknown else None,
        lower=yes / n if n else None, upper=(yes + unknown) / n if n else None)


def conjunctive_rate(rows, *fields):
    values = []
    for r in rows:
        v = [r[f] for f in fields]
        values.append(dict(combined='no' if 'no' in v else 'unknown' if 'unknown' in v else 'yes'))
    return rate(values, 'combined')


def join_rows(root, packet, ratings):
    mapping = read(root, RUN + '/coordinator/behavior_mapping.json')
    predictions = read(root, RUN + '/predictions.json')['records']
    materials = read(root, MATERIALS)
    author = read(root, AUTHOR)
    require(author['history_exposed'] is True and author['independent_gold'] is False
        and author['approved_for_training'] is False, 'Author input reference is not approved gold')
    authors = {r['id']: r for r in author['ratings']}
    require(len(mapping) == len(predictions) == len(materials) == len(authors) == 240,
        'Join source length mismatch')
    require(len(set(mapping.values())) == 240 and set(mapping.values()) == set(ratings),
        'Anonymous mapping is not bijective')
    preds = {r['id']: r for r in predictions}
    require(len(preds) == 240 and set(mapping) == set(preds) == set(authors), 'Join source IDs mismatch')
    require(all(v is None for v in read(root, RUN + '/approved_labels.json').values()),
        'Formal semantic labels changed')
    items = {r['item_id']: r for r in packet['items']}
    result = []
    for m in materials:
        key = m['id']
        p, a, item_id = preds[key], authors[key], mapping[key]
        item = items[item_id]
        require(m['question'] == item['question'] and m['docs'] == item['documents']
            and p['raw_output'] == item['answer'], 'Join input/output mismatch: ' + key)
        for field in ['original_id', 'partition', 'expression', 'condition']:
            require(m[field] == p[field] == a[field], 'Join metadata mismatch')
        require(p['probe_pred'] in {'answer', 'refuse', 'conflict'}
            and p['probe_decision_pre_first_token'] is True
            and p['probe_layer_zero_based'] == 28, 'Wrong frozen probe/timepoint')
        result.append(dict(id=key, item_id=item_id, original_id=m['original_id'],
            partition=m['partition'], expression=m['expression'], condition=m['condition'],
            exposed_author_input_mode=a['semantic_mode'], probe_pred=p['probe_pred'],
            probe_probabilities=p['probe_probabilities'], question=item['question'],
            raw_output=item['answer'], **{f: ratings[item_id][f] for f in BEHAVIOR_FIELDS},
            rationale=ratings[item_id]['rationale']))
    require(Counter(r['exposed_author_input_mode'] for r in result) ==
        Counter(answer=116, refuse=60, conflict=60, unknown=4), 'Author grouping changed')
    return result


def summarize(rows):
    labels = {r['id']: r['exposed_author_input_mode'] for r in rows}
    ratings = {r['id']: r for r in rows}
    insufficient = [r for r in rows if r['exposed_author_input_mode'] == 'refuse']
    conflict = [r for r in rows if r['exposed_author_input_mode'] == 'conflict']
    sufficient = [r for r in rows if r['exposed_author_input_mode'] == 'answer']
    probe_refuse = [r for r in insufficient if r['probe_pred'] == 'refuse']
    false_conflict = [r for r in sufficient if r['probe_pred'] == 'conflict']
    return dict(rows=len(rows), author_input_counts=dict(Counter(r['exposed_author_input_mode'] for r in rows)),
        field_rates={f: rate(rows, f) for f in BEHAVIOR_FIELDS},
        primary=behavior_summary(rows, labels, ratings),
        insufficient_acknowledgment=rate(insufficient, 'acknowledges_insufficiency'),
        insufficient_answer_after_acknowledgment=conjunctive_rate(insufficient,
            'has_substantive_answer', 'acknowledges_insufficiency'),
        conflict_acknowledgment=rate(conflict, 'acknowledges_conflict'),
        conflict_acknowledgment_and_unresolved_selection=conjunctive_rate(conflict,
            'acknowledges_conflict', 'selection_without_resolution'),
        conflict_supplied_resolution=rate(conflict, 'has_supplied_resolution'),
        sufficient_grounded_correct=rate(sufficient, 'answer_grounded_correct'),
        secondary=dict(insufficient_probe_refuse_substantive=rate(probe_refuse, 'has_substantive_answer'),
            sufficient_probe_conflict_cells=len(false_conflict),
            sufficient_probe_conflict_grounded_correct=rate(false_conflict, 'answer_grounded_correct')))


def make_report(root):
    packet, ratings, seal = load_sealed(root)
    rows = join_rows(root, packet, ratings)
    unknowns = [dict(item_id=r['item_id'], id=r['id'],
        fields=[f for f in BEHAVIOR_FIELDS if r[f] == 'unknown'], rationale=r['rationale'])
        for r in rows if any(r[f] == 'unknown' for f in BEHAVIOR_FIELDS)]
    sources = [RUN + '/coordinator/behavior_mapping.json', RUN + '/predictions.json',
        RUN + '/approved_labels.json', MATERIALS, AUTHOR,
        PREFIX + '-seal.json', 'scripts/semantic_transfer_metrics.py',
        'scripts/semantic_transfer_exploratory_behavior_review.py']
    report = dict(schema_version=1, status='exploratory_behavior_review_complete', **BASE_METADATA,
        interpretation='Post-generation, history-exposed assistant review. Author input grouping is '
        'an exposed diagnostic reference, not independent gold. No semantic accuracy or causal inference. '
        'Unknown intervals are identification bounds in full eligible denominators, not confidence intervals. '
        'Source train/dev/eval partitions are not prospective tests. Thirty bases with repeated variants.',
        anonymous_rows=240, behavior_fields=1680,
        determinate_fields=1680 - sum(len(r['fields']) for r in unknowns),
        unknown_fields=sum(len(r['fields']) for r in unknowns), unknown_rows=unknowns,
        preserved_paths=869, input_citations=sum(len(r['input_citations']) for r in ratings.values()),
        output_citations=sum(len(r['output_citations']) for r in ratings.values()),
        full_read_slots=1200, full_read_unique_documents=435,
        source_hashes={p: digest((root / p).read_bytes()) for p in sources},
        all=summarize(rows),
        by_source_partition={v: summarize([r for r in rows if r['partition'] == v])
            for v in sorted({r['partition'] for r in rows})},
        by_expression={v: summarize([r for r in rows if r['expression'] == v]) for v in ['A', 'B']},
        by_constructed_condition={v: summarize([r for r in rows if r['condition'] == v])
            for v in ['S', 'K', 'I', 'C']})
    pairs = []
    for oid in sorted({r['original_id'] for r in rows}):
        group = {(r['expression'], r['condition']): r for r in rows if r['original_id'] == oid}
        for condition in ['S', 'K', 'I', 'C']:
            a, b = group['A', condition], group['B', condition]
            pairs.append(dict(original_id=oid, condition=condition, left=a['id'], right=b['id'],
                field_agreement={f: 'unknown' if 'unknown' in [a[f], b[f]] else
                    'yes' if a[f] == b[f] else 'no' for f in BEHAVIOR_FIELDS}))
    report['AB_behavior_agreement'] = {f: rate([p['field_agreement'] for p in pairs], f)
        for f in BEHAVIOR_FIELDS}
    return report, rows, pairs


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def csv_bytes(rows):
    output = io.StringIO(newline='')
    columns = list(rows[0])
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    for r in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, dict)
            else v for k, v in r.items()})
    return output.getvalue().encode()


def artifacts(root):
    report, rows, pairs = make_report(root)
    return {PREFIX + '.json': json_bytes(report), PREFIX + '-cells.csv': csv_bytes(rows),
        PREFIX + '-pairs.json': json_bytes(pairs)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['analyze', 'verify'], required=True)
    args = parser.parse_args()
    outputs = artifacts(ROOT)
    for name, data in outputs.items():
        path = ROOT / name
        if path.exists():
            require(path.read_bytes() == data, 'Existing artifact differs; refuse overwrite: ' + name)
        else:
            require(args.stage == 'analyze', 'Missing artifact: ' + name)
            path.write_bytes(data)
    print(json.dumps(dict(stage=args.stage, rows=240, artifacts=len(outputs),
        preserved_paths=869, no_gpu=True, independent_gold=False), sort_keys=True))


if __name__ == '__main__':
    main()
