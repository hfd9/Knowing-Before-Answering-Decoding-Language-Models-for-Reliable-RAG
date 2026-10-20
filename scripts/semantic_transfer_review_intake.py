"""CPU-only validation of two semantic reviews; never approves labels or starts GPU work."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATERIALS = ROOT / 'runs/qwen2.5-3b-semantic-transfer-materials-v3'
DEFAULT_OUTPUT = ROOT / 'runs/qwen2.5-3b-semantic-transfer-review-intake-v1'
DESIGN = ROOT / 'prompts/semantic_transfer_validation_v1.json'
MODES = {'answer', 'refuse', 'conflict', 'unknown'}


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def serialize(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_materials(base):
    protocol = read(base / 'protocol.json')
    require(protocol['design_sha256'] == digest(DESIGN), 'Frozen design mismatch')
    inputs = read(base / 'materials/inputs.json')
    unavailable = read(base / 'materials/unavailable_cells.json')
    require(digest(base / 'materials/inputs.json') == protocol['inputs_sha256'], 'Input batch mismatch')
    mapping = read(base / 'coordinator/review_mapping.json')
    packets = {side: read(base / f'review_{side}/packet.json') for side in ['a', 'b']}
    design = read(DESIGN)
    partitions = {oid: part for part, ids in design['partitions'].items() for oid in ids}
    planned_ids = {f'stv{number:02d}_{expression}_{condition}'
        for number in range(1, 31) for expression in ['A', 'B'] for condition in ['S', 'K', 'I', 'C']}
    ids = [row['id'] for row in inputs + unavailable]
    require(len(ids) == len(set(ids)) == 240 and set(ids) == planned_ids, 'Planned240 denominator mismatch')
    base_order = list(partitions)
    for row in inputs + unavailable:
        number = int(row['id'][3:5])
        require(row['original_id'] == base_order[number - 1], 'Base identity mismatch')
        require(row['partition'] == partitions[row['original_id']], 'Base partition mismatch')
        require(row['semantic_label'] is None, 'Author labels must remain null')
        require(row['id'] == f"stv{number:02d}_{row['expression']}_{row['condition']}", 'Condition identity mismatch')
    for row in inputs:
        require(isinstance(row.get('docs'), list) and len(row['docs']) == 5
            and all(isinstance(text, str) and text.strip() for text in row['docs']), 'Five complete documents required')
    require(set(mapping) == {row['id'] for row in inputs}, 'Coordinator mapping mismatch')
    for side, packet in packets.items():
        require(digest(base / f'review_{side}/packet.json') == protocol['packet_sha256'][side], 'Review packet hash mismatch')
        items = {item['item_id']: item for item in packet['items']}
        require(len(items) == len(packet['items']) == len(inputs), 'Review packet duplicate/missing IDs')
        require({value[side] for value in mapping.values()} == set(items), 'Review mapping must be bijective')
        for row in inputs:
            item = items[mapping[row['id']][side]]
            require(set(item) == {'item_id', 'question', 'documents'}, 'Non-blind packet fields')
            require(item['question'] == row['question'] and item['documents'] == row['docs'], 'Mapped packet content mismatch')
    return inputs, unavailable, mapping, packets, design


def validate_review(review, packet, expected_sha256):
    require(isinstance(review, dict), 'Review must be an object')
    require(isinstance(review.get('reviewer'), str) and review['reviewer'].strip(), 'Reviewer identity required')
    require(review.get('history_exposed') is False, 'History-exposed or undeclared review cannot satisfy intake')
    require(isinstance(review.get('exposure_description'), str) and review['exposure_description'].strip(), 'Explicit exposure description required')
    require(review.get('packet_sha256') == expected_sha256, 'Wrong review batch')
    items = {item['item_id']: item for item in packet['items']}
    ratings = review.get('ratings')
    require(isinstance(ratings, list), 'Ratings must be a list')
    require(all(isinstance(row, dict) for row in ratings), 'Rating must be an object')
    ids = [row.get('item_id') for row in ratings]
    require(len(ids) == len(set(ids)) == len(items) and set(ids) == set(items), 'Review must cover each supplied item exactly once')
    normalized = {}
    for rating in ratings:
        require(rating.get('status') != 'unreviewed', 'Unreviewed template is not a completed judgment')
        mode = rating.get('semantic_mode')
        require(mode in MODES, 'Invalid semantic mode')
        require(rating.get('confidence') in {'high', 'moderate', 'ambiguous'}, 'Confidence required')
        require(isinstance(rating.get('rationale'), str) and rating['rationale'].strip(), 'Rationale required')
        require(isinstance(rating.get('resolution_basis'), str), 'Resolution explanation required')
        for field in ['required_facts', 'support_chain', 'missing_facts', 'conflicting_claims']:
            require(isinstance(rating.get(field), list) and all(isinstance(t, str) and t.strip() for t in rating[field]), f'Invalid {field}')
        require(bool(rating['required_facts']), 'Required facts must be explicit')
        if mode == 'answer':
            require(bool(rating['support_chain']), 'Answer judgment requires a support chain')
        if mode == 'refuse':
            require(bool(rating['missing_facts']), 'Refuse judgment requires a missing premise')
        if mode == 'conflict':
            require(len(rating['conflicting_claims']) >= 2, 'Conflict judgment requires two claims')
        citations = rating.get('citations')
        require(isinstance(citations, list) and citations, 'Exact evidence citations required')
        verified = []
        documents = items[rating['item_id']]['documents']
        for citation in citations:
            require(isinstance(citation, dict), 'Citation must be an object')
            slot = citation.get('doc_slot')
            quote = citation.get('quote')
            require(type(slot) is int and 1 <= slot <= 5, 'Invalid document slot')
            require(isinstance(quote, str) and quote.strip(), 'Empty citation')
            text = documents[slot - 1]
            start = citation.get('start', text.find(quote))
            require(type(start) is int and start >= 0 and text[start:start + len(quote)] == quote, 'Citation does not match full document')
            if 'end' in citation:
                require(citation['end'] == start + len(quote), 'Citation end offset mismatch')
            verified.append(dict(doc_slot=slot, quote=quote, start=start, end=start + len(quote),
                document_sha256=hashlib.sha256(text.encode()).hexdigest()))
        normalized[rating['item_id']] = {**rating, 'citations': verified}
    return normalized


def summarize(inputs, unavailable, mapping, reviews, design):
    paired = len(reviews) == 2
    if paired:
        require(reviews['a']['metadata']['reviewer'].strip().casefold() != reviews['b']['metadata']['reviewer'].strip().casefold(), 'Two distinct reviewer identities required')
    candidates = []
    disagreements = []
    for row in inputs:
        a = reviews['a']['ratings'][mapping[row['id']]['a']]['semantic_mode'] if paired else None
        b = reviews['b']['ratings'][mapping[row['id']]['b']]['semantic_mode'] if paired else None
        candidate = a if paired and a == b and a != 'unknown' else None
        candidates.append(dict(id=row['id'], original_id=row['original_id'], partition=row['partition'],
            expression=row['expression'], condition=row['condition'], review_a=a, review_b=b,
            consensus_candidate=candidate, semantic_label=None,
            status='agreement_pending_context_audit' if candidate else ('disagreement_or_unknown' if paired else 'reviews_missing')))
        if paired and a != b:
            disagreements.append(row['id'])
    # The immutable design states the 0.90 requirement in its trigger text.
    # Candidate agreement does not approve labels, even when this number is met.
    minimum = 0.90
    per_partition = {}
    for part, bases in design['partitions'].items():
        own = [row for row in candidates if row['partition'] == part]
        agreed = sum(row['consensus_candidate'] is not None for row in own)
        planned = len(bases) * 8
        per_partition[part] = dict(planned_cells=planned, constructed_cells=len(own),
            unavailable_cells=sum(row['partition'] == part for row in unavailable),
            agreement_candidates=agreed, agreement_coverage=agreed / planned,
            candidate_coverage_requirement_met=agreed / planned >= minimum)
    agreed = sum(row['consensus_candidate'] is not None for row in candidates)
    classes = Counter(row['consensus_candidate'] for row in candidates if row['partition'] == 'semantic_train'
        and row['expression'] == 'A' and row['consensus_candidate'] is not None)
    report = dict(status='reviews_validated_context_audit_pending' if paired else 'pending_no_review_files',
        planned_cells=240, constructed_cells=len(inputs), unavailable_cells=len(unavailable),
        construction_coverage=len(inputs) / 240, validated_review_files=len(reviews),
        independently_verified_review_contexts=0, approved_semantic_labels=0,
        agreement_candidates=agreed, agreement_coverage=agreed / 240,
        disagreements=disagreements, partitions=per_partition, training_A_candidate_class_counts=dict(classes),
        candidate_coverage_requirement_met=agreed / 240 >= minimum and all(
            part['candidate_coverage_requirement_met'] for part in per_partition.values()),
        training_A_has_three_candidate_classes=set(classes) == {'answer', 'refuse', 'conflict'},
        context_independence_note='Self-reported history_exposed=false is validated, not independently proved. Distinct names do not establish independent contexts or model sources. Audit actual received context before approving labels.',
        no_automatic_adjudication=True, approved_for_training=False, gpu_launch_ready=False,
        new_gpu_forwards=0, generated_answers=0, trained_probes=0)
    return report, candidates


def process(materials, output, review_a=None, review_b=None, write=True):
    require((review_a is None) == (review_b is None), 'Supply both reviews together or neither')
    inputs, unavailable, mapping, packets, design = load_materials(materials)
    source_files = [materials / 'protocol.json', materials / 'materials/inputs.json',
        materials / 'materials/unavailable_cells.json', materials / 'coordinator/review_mapping.json']
    reviews = {}
    for side, path in [('a', review_a), ('b', review_b)]:
        source_files.append(materials / f'review_{side}/packet.json')
        if path is not None:
            value = read(path)
            ratings = validate_review(value, packets[side], digest(materials / f'review_{side}/packet.json'))
            reviews[side] = dict(metadata={key: value[key] for key in ['reviewer', 'history_exposed', 'exposure_description', 'packet_sha256']}, ratings=ratings)
            source_files.append(path)
    report, candidates = summarize(inputs, unavailable, mapping, reviews, design)
    protocol = dict(task='semantic_review_intake_CPU_only', implementation_sha256=digest(Path(__file__)),
        design_sha256=digest(DESIGN), sources={str(p.resolve()): digest(p) for p in source_files},
        outputs_are_candidates_only=True, run_has_no_inference_or_fit=True)
    for name, value in {'protocol.json': protocol, 'review_validation.json': report,
            'consensus_candidates.json': candidates, 'validated_reviews.json': reviews}.items():
        path = output / name
        expected = serialize(value)
        if path.exists():
            require(path.read_text() == expected, f'Existing intake differs; use a new run directory: {path}')
        elif write:
            output.mkdir(parents=True, exist_ok=True)
            path.write_text(expected)
        else:
            raise ValueError(f'Missing intake artifact: {path}')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'verify'], default='prepare')
    parser.add_argument('--materials-dir', type=Path, default=DEFAULT_MATERIALS)
    parser.add_argument('--run-dir', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--review-a', type=Path)
    parser.add_argument('--review-b', type=Path)
    args = parser.parse_args()
    materials, output = args.materials_dir.resolve(), args.run_dir.resolve()
    require(materials.is_relative_to(ROOT / 'runs'), 'Materials must be in runs')
    require(output.is_relative_to(ROOT / 'runs'), 'Output must be in runs')
    require(output != materials and not output.is_relative_to(materials), 'Use a separate intake run')
    print(serialize(process(materials, output, args.review_a, args.review_b, args.stage == 'prepare')))


if __name__ == '__main__':
    main()
