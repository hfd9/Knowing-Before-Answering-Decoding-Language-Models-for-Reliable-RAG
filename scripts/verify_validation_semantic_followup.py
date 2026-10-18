"""Read-only verification of explicit same-assistant followup ratings; no inference."""

import argparse
from collections import Counter
import csv
import json
from pathlib import Path

import validation_semantic_diagnosis as d

DEFAULT = d.ROOT / 'runs/qwen2.5-3b-validation-semantic-followup-2026-10-16-v1'


def verify(base):
    protocol = d.read(base / 'protocol.json')
    seal = d.read(base / 'review_seal.json')
    source = d.ROOT / protocol['source_export_dir']
    d.require(d.digest(source / 'manifest.json') == protocol['source_export_manifest_sha256'],
              'Source export manifest changed')
    d.require(d.digest(d.MANIFEST) == protocol['source_pilot_manifest_sha256'], 'Pilot manifest changed')
    export_manifest = d.read(source / 'manifest.json')
    d.verify_hashes(source, export_manifest['artifact_sha256'])
    d.verify_hashes(d.ROOT, export_manifest['implementation_sha256'])
    d.verify_hashes(d.ROOT, protocol['original_sources_sha256'])
    d.require(d.digest(base / 'protocol.json') == seal['protocol_sha256'], 'Followup protocol changed')
    d.require(d.digest(base / 'ratings.json') == seal['ratings_sha256'], 'Followup ratings changed')
    d.require(d.digest(base / 'ratings.csv') == seal['ratings_csv_sha256'], 'Followup CSV changed')
    d.require(d.digest(source / 'reviewer/inputs.json') == protocol['source_packet_sha256'],
              'Review packet changed')
    old_manifest, _, old_ratings, outputs, _, _, _, _ = d.load_verified()
    d.require(protocol['old_input_ratings_sha256'] ==
              old_manifest['run_artifact_sha256']['input_ratings.json'], 'Old rating binding differs')
    mapping = d.read(source / 'coordinator/review_mapping.json')
    packet = d.indexed(d.read(source / 'reviewer/inputs.json')['records'], 'review_id')
    ratings = d.read(base / 'ratings.json')
    new = d.indexed(ratings, 'review_id')
    with (base / 'ratings.csv').open(encoding='utf-8', newline='') as file:
        csv_rows = d.indexed(list(csv.DictReader(file)), 'review_id')
    d.require(len(new) == 30 and set(new) == set(packet) == set(csv_rows), 'Require exactly all30 ratings')
    quote_offsets = []
    for key, row in new.items():
        d.require(row['pilot_id'] == mapping[key], f'ID mapping differs: {key}')
        d.require(row['packet_sha256'] == protocol['source_packet_sha256'], f'Wrong batch: {key}')
        d.require(row['reviewer'] == protocol['reviewer'] and row['prior_exposure'] == protocol['provenance'],
                  f'Provenance differs: {key}')
        d.require(row['all_five_documents_read'] is True, f'Full reading not attested: {key}')
        d.require(row['semantic_mode'] in d.MODES + ['unknown'], f'Invalid mode: {key}')
        d.require(row['confidence'] in ['high', 'moderate', 'ambiguous'], f'Invalid confidence: {key}')
        for field in ['question_interpretation', 'reason', 'uncertainty_notes']:
            d.require(isinstance(row[field], str) and row[field].strip(), f'Missing {field}: {key}')
        d.require(isinstance(row['required_facts'], list) and bool(row['required_facts']),
                  f'Missing premises: {key}')
        for citation in row['citations']:
            slot = citation['doc_id']
            d.require(type(slot) is int and 1 <= slot <= 5, f'Invalid document slot: {key}')
            text = packet[key]['documents'][slot - 1]
            quote = citation['quote']
            d.require(isinstance(quote, str) and quote.strip() and quote in text, f'Quote absent: {key}')
            starts = []; cursor = 0
            while True:
                start = text.find(quote, cursor)
                if start < 0:
                    break
                starts.append(dict(start=start, end=start + len(quote))); cursor = start + 1
            quote_offsets.append(dict(review_id=key, pilot_id=row['pilot_id'], **citation, occurrences=starts))
        if row['semantic_mode'] == 'answer':
            d.require(bool(row['citations']) and bool(row['answer_if_supported']), f'Answer lacks support: {key}')
        if row['semantic_mode'] == 'refuse':
            d.require(bool(row['missing_facts']), f'Refuse lacks missing premise: {key}')
        if row['semantic_mode'] == 'conflict':
            d.require(len(row['conflicting_claims']) >= 2 and len(row['citations']) >= 2,
                      f'Conflict lacks both claims: {key}')
        for field, value in csv_rows[key].items():
            if field in ['required_facts', 'missing_facts', 'conflicting_claims']:
                expected = row[field]; actual = json.loads(value)
            elif field == 'citations_json':
                expected = row['citations']; actual = json.loads(value)
            elif field == 'all_five_documents_read':
                expected = 'yes'; actual = value
            else:
                expected = row[field]; actual = value
            d.require(actual == expected, f'CSV differs from explicit rating: {key}/{field}')
    comparisons = []
    changes = []
    for key, row in new.items():
        old_key = row['pilot_id']; out = outputs[old_key]; draft = out['v4']['draft']
        judgment = ('not_scored_input_unknown' if row['semantic_mode'] == 'unknown' else
                    'technical_invalid' if draft['status'] != 'valid_structure' else
                    'agreement' if draft['semantic_mode'] == row['semantic_mode'] else 'mismatch')
        entry = dict(review_id=key, pilot_id=old_key, id=out['id'], question=packet[key]['question'],
                     published_mode=out['published_mode'],
                     input_semantic_mode=row['semantic_mode'], input_confidence=row['confidence'],
                     old_input_mode=old_ratings[old_key]['semantic_mode'],
                     v4_report_mode=draft['semantic_mode'], v4_status=draft['status'],
                     classification_judgment=judgment)
        entry.update({name: out['previous'][name]['pred_mode'] or 'invalid' for name in d.METHODS[:-1]})
        comparisons.append(entry)
        if entry['old_input_mode'] != entry['input_semantic_mode']:
            changes.append(dict(review_id=key, pilot_id=old_key, id=out['id'],
                                old_mode=entry['old_input_mode'], new_mode=entry['input_semantic_mode'],
                                explanation=row['reason'], limitation=row['uncertainty_notes']))
    comparisons.sort(key=lambda r: r['review_id'])
    changes.sort(key=lambda r: r['pilot_id'])
    summary = dict(status='same_assistant_followup_complete_not_independent_gold',
                   source_packet_sha256=protocol['source_packet_sha256'], reviewer=protocol['reviewer'],
                   provenance=protocol['provenance'], independent_new_ratings=0,
                   same_assistant_additional_ratings=30, base_questions=10, document_slots_read=150,
                   unique_documents_read=len({text for row in packet.values() for text in row['documents']}),
                   input_mode_counts=dict(Counter(r['semantic_mode'] for r in ratings)),
                   confidence_counts=dict(Counter(r['confidence'] for r in ratings)),
                   exact_quotes_checked=len(quote_offsets), mode_changes=changes,
                   known_input_publication_disagreements=[dict(
                       review_id=r['review_id'], pilot_id=r['pilot_id'], id=r['id'],
                       published_mode=r['published_mode'], input_semantic_mode=r['input_semantic_mode'])
                       for r in comparisons if r['input_semantic_mode'] != 'unknown'
                       and r['published_mode'] != r['input_semantic_mode']],
                   unknown_ids=[dict(review_id=r['review_id'], pilot_id=r['pilot_id'])
                                for r in ratings if r['semantic_mode'] == 'unknown'],
                   v4_classification_judgments=dict(Counter(r['classification_judgment'] for r in comparisons)),
                   method_agreement_tables=d.agreement_table(comparisons),
                   ratings_sha256=d.digest(base / 'ratings.json'),
                   ratings_csv_sha256=d.digest(base / 'ratings.csv'),
                   limitation='Same previously exposed assistant and same30 pilot; refinements in question interpretation, '
                   'not new independent evidence or a qualified baseline. Old judgments remain frozen. '
                   'No automatic label import, GPU, confirmation set or causal claim.')
    if (base / 'manifest.json').exists():
        manifest = d.read(base / 'manifest.json')
        d.verify_hashes(base, manifest['artifact_sha256'])
        d.verify_hashes(d.ROOT, manifest['implementation_sha256'])
        d.require(d.read(base / 'summary.json') == summary, 'Saved summary differs from replay')
    return summary, comparisons, quote_offsets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run_dir', type=Path, default=DEFAULT)
    args = parser.parse_args()
    summary, _, _ = verify(args.run_dir.resolve())
    print(d.json_text(summary))


if __name__ == '__main__':
    main()
