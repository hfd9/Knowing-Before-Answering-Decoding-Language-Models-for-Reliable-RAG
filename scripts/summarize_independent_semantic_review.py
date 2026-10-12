"""Validate independent context ratings, compare with v3; no formal-label import.

Reviewers saw project-wide injected background, but no per-item source labels.
Differences are exported for adjudication, not automatically turned into gold.
"""

from collections import Counter
import argparse
from datetime import datetime, timezone
import csv
import json
from pathlib import Path

import prepare_independent_semantic_review as p
import free_answer_review as behavior


def counts(rows, field):
    return dict(Counter(r[field] for r in rows))


def agreement(old, new):
    categories = ['yes', 'no', 'unknown']
    n = len(old)
    observed = sum(a == b for a, b in zip(old, new)) / n
    a, b = Counter(old), Counter(new)
    chance = sum(a[k]*b[k] for k in categories)/n**2
    known = [(a,b) for a,b in zip(old,new) if a != 'unknown' and b != 'unknown']
    return dict(n=n, equal_including_unknown=sum(a == b for a,b in zip(old,new)),
                agreement_including_unknown=observed,
                kappa_treating_unknown_as_category=(observed-chance)/(1-chance) if chance < 1 else None,
                both_known=len(known), both_known_equal=sum(a == b for a,b in known),
                both_known_agreement=sum(a == b for a,b in known)/len(known) if known else None,
                old_unknown_new_known=sum(a == 'unknown' and b != 'unknown' for a,b in zip(old,new)),
                known_disagreements=sum(a != b for a,b in known))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--supplement', type=Path)
    parser.add_argument('--output-version', default='comparison-v1')
    parser.add_argument('--source-snapshot', type=Path)
    args = parser.parse_args()
    if Path(args.output_version).name != args.output_version or args.output_version in {'.', '..'}:
        parser.error('Output version must be one directory name')
    mapping = json.loads((p.OUT/'coordinator/mapping.json').read_text())
    p.verify_sources(mapping, args.source_snapshot)
    evidence, ratings, files = [], [], {}
    assigned_behavior, missing_behavior = set(), set()
    second_review_count = 0
    for name in ['a','b','c']:
        assignment=json.loads((p.OUT/f'public/assignments/{name}.json').read_text())
        for task, destination, id_field in [('evidence',evidence,'evidence_id'),('behavior',ratings,'review_id')]:
            path=p.OUT/f'reviewers/{name}/{task}.csv'
            p.validate(path, args.source_snapshot)
            rows=list(csv.DictReader(path.open()))
            expected = set(assignment[task+'_ids'])
            found = {r[id_field] for r in rows}
            if not found <= expected or (task == 'evidence' and found != expected):
                raise ValueError(f'Incomplete or wrong assignment: {name}/{task}')
            if task == 'behavior':
                assigned_behavior.update(expected)
                missing_behavior.update(expected - found)
                second_review_count += len(rows)
            if not all(r['reviewer'].strip() for r in rows):
                raise ValueError(f'Unreviewed rows: {name}/{task}')
            destination.extend(rows)
            files[str(path.relative_to(p.ROOT))]=p.sha(path.read_bytes())
    supplement_count = 0
    if args.supplement is not None:
        path = args.supplement.resolve()
        p.validate(path, args.source_snapshot)
        rows = list(csv.DictReader(path.open()))
        if {r['review_id'] for r in rows} != missing_behavior:
            raise ValueError('Supplement must cover exactly missing assigned behavior IDs')
        if not all(r['reviewer'].startswith('Codex-coordinator-supplement-') for r in rows):
            raise ValueError('Coordinator supplement must disclose a separate reviewer identity')
        ratings.extend(rows)
        supplement_count = len(rows)
        files[str(path.relative_to(p.ROOT))] = p.sha(path.read_bytes())
    elif missing_behavior:
        raise ValueError(f'Incomplete behavior assignments: {sorted(missing_behavior)}')
    assert len(evidence)==len({r['evidence_id'] for r in evidence})==300
    assert len(ratings)==len({r['review_id'] for r in ratings})==234
    e_map={r['evidence_id']:r for r in mapping['evidence_mapping']}
    b_map={r['review_id']:r for r in mapping['behavioral_mapping']}
    e_lookup={r['evidence_id']:r for r in evidence}
    r_lookup={r['review_id']:r for r in ratings}
    out=p.OUT/args.output_version
    p.freeze(out/'independent_evidence.csv',p.csv_bytes(sorted(evidence,key=lambda r:r['evidence_id']),list(evidence[0])))
    p.freeze(out/'independent_behavior.csv',p.csv_bytes(sorted(ratings,key=lambda r:r['review_id']),list(ratings[0])))
    changes=[]
    for r in ratings:
        prior=b_map[r['review_id']]
        for field in p.FIELDS:
            if r[field] != prior['previous'][field]:
                changes.append(dict(review_id=r['review_id'],source_item_id=prior['source_item_id'],
                                    evidence_id=r['evidence_id'] if 'evidence_id' in r else prior['evidence_id'],
                                    field=field,old=prior['previous'][field],independent=r[field],
                                    disposition='pending_adjudication',reason=r['notes']))
    p.freeze(out/'disagreements.csv',p.csv_bytes(changes,
             ['review_id','source_item_id','evidence_id','field','old','independent','disposition','reason']))
    core=[]
    for r in ratings:
        prior=b_map[r['review_id']]
        if prior['core']:
            er=e_lookup[prior['evidence_id']]
            core.append(dict(source_item_id=prior['source_item_id'],review_id=r['review_id'],
                             evidence_id=prior['evidence_id'],format=prior['format'],
                             independent_semantic_class=er['semantic_class'],
                             **{f:r[f] for f in p.FIELDS},
                             evidence_reason=er['reason'],behavior_reason=r['notes']))
    assert len(core)==20
    p.freeze(out/'core_cases.csv',p.csv_bytes(core,list(core[0])))
    source_data={r['id']:r for r in map(json.loads,(p.ROOT/'runs/qwen2.5-3b-small/data/instances_test.jsonl').read_text().splitlines())}
    original_quality=list(csv.DictReader((p.ROOT/'docs/records/2026-10-11-free-answer-followup-audit-conflict-quality.csv').open()))
    old_quality={r['id']:r['quality'] for r in original_quality}
    quality_comparison=[]
    for r in evidence:
        source=e_map[r['evidence_id']]
        if source['id'] in old_quality:
            quality_comparison.append(dict(evidence_id=r['evidence_id'],id=source['id'],
                previous_quality=old_quality[source['id']],independent_semantic_class=r['semantic_class'],
                reason=r['reason']))
    assert len(quality_comparison)==100
    p.freeze(out/'conflict_quality_comparison.csv',p.csv_bytes(quality_comparison,list(quality_comparison[0])))
    annotation_path=p.RUN/'annotations.csv'
    if args.source_snapshot is not None:
        annotation_path=args.source_snapshot/annotation_path.relative_to(p.ROOT)
    original_annotations={r['item_id']:r for r in csv.DictReader(annotation_path.open())}
    outputs={}
    for fmt in ['plain','chat']:
        outputs.update({(fmt,r['id']):r for r in json.loads((p.RUN/f'{fmt}/test/predictions.json').read_text())['records']})
    joined_v3=[]
    joined_independent=[]
    for r in mapping['behavioral_mapping']:
        src=source_data[r['id']]
        raw=outputs[(r['format'],r['id'])]
        er=e_lookup[r['evidence_id']]
        base=dict(format=r['format'],id=r['id'],true_mode=src['true_mode'],probe_pred=raw['probe_pred'],
                  semantic_class=er['semantic_class'],review_id=r['review_id'],evidence_id=r['evidence_id'])
        conversion={'yes':True,'no':False,'unknown':None}
        joined_v3.append(dict(base,behavior={f:conversion[original_annotations[r['source_item_id']][f]] for f in p.FIELDS}))
        annotation=r_lookup.get(r['review_id'],{})
        joined_independent.append(dict(base,behavior={f:conversion[annotation.get(f,'unknown')] for f in p.FIELDS}))
    rates={}
    for fmt in ['plain','chat']:
        subset=[r for r in joined_v3 if r['format']==fmt]
        independent_subset=[r for r in joined_independent if r['format']==fmt]
        rates[fmt]=dict(
            v3_behavior_in_semantically_insufficient_input=behavior.rate_bounds(subset,lambda r:r['semantic_class']=='insufficient','has_substantive_answer'),
            v3_behavior_after_probe_refuse_in_semantically_insufficient_input=behavior.rate_bounds(subset,lambda r:r['semantic_class']=='insufficient' and r['probe_pred']=='refuse','has_substantive_answer'),
            independent_behavior_after_probe_refuse_in_semantically_insufficient_input=behavior.rate_bounds(independent_subset,lambda r:r['semantic_class']=='insufficient' and r['probe_pred']=='refuse','has_substantive_answer'),
            v3_selection_in_semantically_conflicting_input=behavior.rate_bounds(subset,lambda r:r['semantic_class']=='conflicting','selects_single_answer'),
            independent_selection_in_semantically_conflicting_input=behavior.rate_bounds(independent_subset,lambda r:r['semantic_class']=='conflicting','selects_single_answer'))
    result=dict(status='review_verified_with_coordinator_supplement' if supplement_count else 'independent_review_verified',recorded_at=datetime.now(timezone.utc).isoformat(),
                evidence_items=300,behavior_items=234,packet_sha256=mapping['packet_sha256'],ratings_sha256=files,
                second_review_behavior_items=second_review_count,
                coordinator_supplement_behavior_items=supplement_count,
                background_exposure_disclosed=True,
                reviewer_independence=f'Three fresh-context same-model shards saved {second_review_count} behavior scores and 300 input scores. Their declarations report project AGENTS background exposure without prior per-item labels or coordinator mapping. {supplement_count} missing behavior scores are current-coordinator supplements with historical context exposure, not independent second ratings. Not fully background-blind or independent human gold.',
                formal_annotations='v3 unchanged; no automatic adjudication/import',
                evidence_counts=counts(evidence,'semantic_class'),
                evidence_by_published_class={mode:dict(Counter(r['semantic_class'] for r in evidence if e_map[r['evidence_id']]['published_class']==mode)) for mode in ['answer','refuse','conflict']},
                field_agreement={f:agreement([b_map[r['review_id']]['previous'][f] for r in ratings],[r[f] for r in ratings]) for f in p.FIELDS},
                controls_field_agreement={f:agreement([b_map[r['review_id']]['previous'][f] for r in ratings if b_map[r['review_id']]['control']],[r[f] for r in ratings if b_map[r['review_id']]['control']]) for f in p.FIELDS},
                changed_fields=len(changes),changed_rows=len({r['review_id'] for r in changes}),
                core_case_confirmation={fmt:dict(n=sum(r['format']==fmt for r in core),
                    substantive_yes=sum(r['format']==fmt and r['has_substantive_answer']=='yes' for r in core),
                    semantically_insufficient_and_substantive_yes=sum(r['format']==fmt and r['has_substantive_answer']=='yes' and r['independent_semantic_class']=='insufficient' for r in core),
                    semantic_counts=dict(Counter(r['independent_semantic_class'] for r in core if r['format']==fmt))) for fmt in ['plain','chat']},
                quality_stratified_rates=rates,
                rate_notes='v3 rates combine second-review input quality with first-review behavior. Legacy keys named independent include second-context scores plus any explicitly disclosed coordinator supplements; all other outputs remain unknown. Membership is restricted to known semantic classes; unknown input classes are excluded and separately counted. These are post-hoc diagnostic bounds, not confidence intervals or confirmation results.',
                agreement_note='234 outputs are an enriched difficult-case queue; do not extrapolate agreement to the full 600. Unknown is its own category; both-known agreement has a different denominator. 30 random controls are descriptive and small.')
    p.freeze(out/'summary.json',p.encoded(result))
    p.verify_sources(mapping, args.source_snapshot)
    p.freeze(p.OUT/'coordinator/readiness.json',p.encoded(result))
    print(json.dumps({k:v for k,v in result.items() if k not in ['ratings_sha256','field_agreement','controls_field_agreement','quality_stratified_rates']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
