"""Build a separate annotation version from explicit manual field decisions.

No voting, semantic inference, model loading or formal annotation import. Original
v3, second ratings and source outputs are verified and preserved. Each disputed
cell needs a recorded decision even when the final value remains unknown.
"""

import argparse
from collections import Counter
import csv
import json
from pathlib import Path

import prepare_independent_semantic_review as p
import free_answer_review as behavior


def apply_decisions(original, mapping, discrepancies, decisions):
    lookup = {r['review_id']: r for r in mapping['behavioral_mapping']}
    expected = {(r['review_id'], r['field']): r for r in discrepancies}
    if len(expected) != len(discrepancies):
        raise ValueError('Duplicate disputed cell')
    result = {r['item_id']: dict(r) for r in original}
    if len(result) != len(original):
        raise ValueError('Duplicate source item')
    seen, audit = set(), []
    for decision in decisions:
        bid = decision['review_id']
        if bid not in lookup or not decision['reason'].strip() or not decision['adjudicator'].strip():
            raise ValueError('Missing identity or manual judgment reason')
        item = lookup[bid]['source_item_id']
        for field, value in decision['final_fields'].items():
            cell = (bid, field)
            if cell not in expected or cell in seen or value not in {'yes', 'no', 'unknown'}:
                raise ValueError(f'Unexpected, duplicated or invalid decision: {cell}')
            seen.add(cell)
            prior = expected[cell]
            if result[item][field] != prior['old']:
                raise ValueError('Adjudication does not match frozen original score')
            audit.append(dict(review_id=bid, item_id=item, field=field,
                              old=prior['old'], second_or_supplement=prior['independent'],
                              final=value, changed_from_v3=value != prior['old'],
                              adjudicator=decision['adjudicator'], reason=decision['reason']))
            result[item][field] = value
        if any(a['item_id'] == item and a['changed_from_v3'] for a in audit):
            result[item]['reviewer'] = decision['adjudicator']
            result[item]['notes'] += ' | 2026-10-12 field adjudication: ' + decision['reason']
    if seen != set(expected):
        raise ValueError(f'Missing manual decisions: {sorted(set(expected) - seen)}')
    for row in result.values():
        if row['has_substantive_answer'] == 'no' and any(row[f] == 'yes' for f in
                ['selects_single_answer', 'answer_correct']):
            raise ValueError('Final no-answer score conflicts with selection/correctness')
    return [result[r['item_id']] for r in original], audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison', type=Path, required=True)
    parser.add_argument('--decisions', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-snapshot', type=Path)
    args = parser.parse_args()
    mapping = json.loads((p.OUT/'coordinator/mapping.json').read_text())
    p.verify_sources(mapping, args.source_snapshot)
    comparison = json.loads((args.comparison/'summary.json').read_text())
    for filename, digest in comparison['ratings_sha256'].items():
        if p.sha((p.ROOT/filename).read_bytes()) != digest:
            raise ValueError('Review ratings changed since comparison')
    original_path=p.RUN/'annotations.csv'
    if args.source_snapshot is not None:
        original_path=args.source_snapshot/original_path.relative_to(p.ROOT)
    original = list(csv.DictReader(original_path.open()))
    discrepancies = list(csv.DictReader((args.comparison/'disagreements.csv').open()))
    manual = json.loads(args.decisions.read_text())
    if not manual.get('rubric_unchanged'):
        raise ValueError('Manual decisions must disclose unchanged rubric')
    rows, audit = apply_decisions(original, mapping, discrepancies, manual['decisions'])
    p.freeze(args.out/'annotations_v4.csv', p.csv_bytes(rows, list(original[0])))
    manifest = json.loads((p.RUN/'review/manifest.json').read_text())
    manifest_hash = p.sha((p.RUN/'review/manifest.json').read_bytes())
    behavior.load_annotations(args.out/'annotations_v4.csv', manifest['items'], manifest_hash)
    p.freeze(args.out/'field_adjudications.csv', p.csv_bytes(audit, list(audit[0])))
    uncertain = [r for r in rows if any(r[f] == 'unknown' for f in p.FIELDS)]
    p.freeze(args.out/'uncertain_v4.csv', p.csv_bytes(uncertain, list(original[0])))
    annotations = {r['item_id']: r for r in rows}
    evidence = {r['evidence_id']: r for r in csv.DictReader(
        (args.comparison/'independent_evidence.csv').open())}
    outputs = {}
    for fmt in ['plain', 'chat']:
        outputs.update({(fmt,r['id']):r for r in json.loads(
            (p.RUN/f'{fmt}/test/predictions.json').read_text())['records']})
    published = {r['evidence_id']:r['published_class'] for r in mapping['evidence_mapping']}
    original_ids = {r['evidence_id']:r['original_id'] for r in mapping['evidence_mapping']}
    convert = {'yes': True, 'no': False, 'unknown': None}
    joined = []
    core = []
    for m in mapping['behavioral_mapping']:
        a = annotations[m['source_item_id']]
        row = dict(format=m['format'], id=m['id'], item_id=m['source_item_id'],
                   review_id=m['review_id'], evidence_id=m['evidence_id'],
                   original_id=original_ids[m['evidence_id']],
                   true_mode=published[m['evidence_id']],
                   semantic_class=evidence[m['evidence_id']]['semantic_class'],
                   probe_pred=outputs[(m['format'],m['id'])]['probe_pred'],
                   behavior={f:convert[a[f]] for f in p.FIELDS})
        joined.append(row)
        if m['core']:
            core.append(dict(item_id=m['source_item_id'], review_id=m['review_id'],
                             format=m['format'], semantic_class=row['semantic_class'],
                             **{f:a[f] for f in p.FIELDS}))
    rates = {}
    for fmt in ['plain','chat']:
        subset = [r for r in joined if r['format'] == fmt]
        rates[fmt] = dict(
            published=behavior.behavior_summary(subset),
            semantic_insufficient_answer=behavior.rate_bounds(subset, lambda r:r['semantic_class']=='insufficient', 'has_substantive_answer'),
            semantic_insufficient_after_probe_refuse=behavior.rate_bounds(subset, lambda r:r['semantic_class']=='insufficient' and r['probe_pred']=='refuse', 'has_substantive_answer'),
            semantic_conflict_selection=behavior.rate_bounds(subset, lambda r:r['semantic_class']=='conflicting', 'selects_single_answer'),
            semantic_sufficient_correct=behavior.rate_bounds(subset, lambda r:r['semantic_class']=='sufficient', 'grounded_correct_answer'))
    p.freeze(args.out/'core_adjudicated.csv', p.csv_bytes(core,list(core[0])))
    summary = dict(status='all_disputed_behavior_fields_adjudicated_version_prepared',
                   original_sha256=p.sha(original_path.read_bytes()),
                   v4_sha256=p.sha((args.out/'annotations_v4.csv').read_bytes()),
                   manual_decisions_sha256=p.sha(args.decisions.read_bytes()),
                   comparison_sha256=p.sha((args.comparison/'summary.json').read_bytes()),
                   annotations=600, second_review_behavior_items=232, coordinator_supplement_items=2,
                   adjudicated_rows=len(manual['decisions']), adjudicated_fields=len(audit),
                   changed_fields=sum(r['changed_from_v3'] for r in audit),
                   changed_rows=len({r['item_id'] for r in audit if r['changed_from_v3']}),
                   fully_known_rows=600-len(uncertain), any_unknown_rows=len(uncertain),
                   core_confirmation={fmt:dict(Counter(r['has_substantive_answer'] for r in core if r['format']==fmt)) for fmt in ['plain','chat']},
                   rates=rates,
                   limitations='Current coordinator adjudication, not independent human gold. Input quality is saved second-review rating, not new ground truth. Whole-output ambiguity and truncation remain unknown. Semantic subsets exclude 10 unknown input classes and are post-hoc diagnostics. Rate bounds are identification bounds, not confidence intervals. 234 reviewed outputs enrich difficult cases; agreement is not representative of 600.')
    p.freeze(args.out/'summary.json', p.encoded(summary))
    p.verify_sources(mapping, args.source_snapshot)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['rates']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
