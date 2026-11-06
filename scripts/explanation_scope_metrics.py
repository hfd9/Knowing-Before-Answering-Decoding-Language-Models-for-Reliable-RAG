"""CPU calculator for declared manual endpoints; no scoring, evidence approval or writes.

The 48 template rows are planning slots, not constructed experimental inputs.
Provenance metadata is not checked against source bytes or reviewer context.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'prompts/explanation_scope_scoring_contract_v1.json'
CONDITIONS = ('S', 'I0', 'IU', 'CT')
COMMON = ('gives_unretracted_target_value', 'provides_substantive_explanation',
          'whole_explanation_support', 'overbroad_missing_information_claim')
SPECIFIC = {
    'S': ('grounded_target_answer',),
    'I0': ('withholds_target_with_support', 'unsupported_target_conflict'),
    'IU': ('withholds_target_with_support', 'unsupported_target_conflict'),
    'CT': ('recognizes_target_conflict', 'unresolved_target_side_selection'),
}
FIELDS = COMMON + tuple(dict.fromkeys(k for values in SPECIFIC.values() for k in values))
YNU = ('yes', 'no', 'unknown')
SUPPORT = ('supported', 'unsupported', 'contradicted', 'ambiguous', 'not_applicable')
TECHNICAL = ('not_collected', 'complete', 'empty', 'truncated', 'unreadable', 'failed')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_contract():
    contract = json.loads(CONTRACT.read_text())
    require(contract['schema_version'] == 1, 'Unsupported contract schema')
    require(contract['draft_sha256'] == digest(ROOT / contract['draft_path']), 'Draft changed')
    draft = json.loads((ROOT / contract['draft_path']).read_text())
    require(draft['status'] == 'conditional_draft_pending_actual_independent_review'
            and draft['is_executable_protocol'] is False, 'Expected a conditional draft')
    require(contract['planned_scenes'] == 12 and contract['planned_slots'] == 48
            and tuple(contract['conditions']) == CONDITIONS, 'Expected the full12x4 grid')
    require(tuple(contract['common_fields']) == COMMON
            and {k: tuple(v) for k, v in contract['condition_fields'].items()} == SPECIFIC,
            'Contract endpoint definitions differ')
    require(tuple(contract['judgments']) == YNU
            and tuple(contract['technical_statuses']) == TECHNICAL
            and tuple(contract['whole_explanation_support_values']) == SUPPORT,
            'Contract states differ')
    require(contract['boundaries']['formal_gate'] is False
            and contract['boundaries']['gpu_launch_ready'] is False
            and contract['boundaries']['automatic_independent_approval'] is False,
            'Calculator cannot approve research')
    return contract


def blank_review():
    contract = load_contract()
    return {
        'schema_version': 1,
        'draft_sha256': contract['draft_sha256'],
        'contract_sha256': digest(CONTRACT),
        'provenance': {'reviewer_id': None, 'history_exposure': 'unknown', 'description': None},
        'rows': [dict(scene=scene, condition=condition, technical_status='not_collected',
                      review_status='unreviewed', source_item_id=None, input_sha256=None,
                      output_sha256=None, **{k: None for k in FIELDS})
                 for scene in range(1, 13) for condition in CONDITIONS],
    }


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def valid_sha(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in '0123456789abcdef' for c in value))


def validate(review):
    contract = load_contract()
    require(isinstance(review, dict) and type(review.get('schema_version')) is int
            and review['schema_version'] == 1, 'Invalid review schema')
    require(review.get('draft_sha256') == contract['draft_sha256']
            and review.get('contract_sha256') == digest(CONTRACT), 'Review binding mismatch')
    provenance = review.get('provenance')
    require(isinstance(provenance, dict)
            and provenance.get('history_exposure') in contract['provenance_exposure_values'],
            'Explicit provenance exposure declaration required')
    rows = review.get('rows')
    require(isinstance(rows, list) and len(rows) == 48, 'Retain all48 planning slots')
    indexed = {}
    for row in rows:
        require(isinstance(row, dict), 'Each row must be an object')
        scene, condition = row.get('scene'), row.get('condition')
        require(type(scene) is int and 1 <= scene <= 12 and condition in CONDITIONS,
                'Invalid scene or condition')
        key = (scene, condition)
        require(key not in indexed, 'Duplicate planning slot')
        indexed[key] = row
        require(row.get('technical_status') in TECHNICAL
                and row.get('review_status') in ('unreviewed', 'reviewed'), 'Invalid status')
        require(all(k in row for k in FIELDS), 'Endpoint fields must be explicit')
        for k in ('input_sha256', 'output_sha256'):
            require(row.get(k) is None or valid_sha(row[k]), 'Invalid declared source hash')
        require(row.get('source_item_id') is None or nonempty(row['source_item_id']),
                'Invalid declared source item')
        if row['review_status'] == 'unreviewed':
            require(all(row[k] is None for k in FIELDS), 'Unreviewed endpoints must be null')
            continue
        require(row['technical_status'] == 'complete', 'Only complete outputs may be reviewed')
        require(nonempty(provenance.get('reviewer_id')) and nonempty(provenance.get('description')),
                'Reviewed endpoints require reviewer provenance')
        require(nonempty(row.get('source_item_id')) and valid_sha(row.get('input_sha256'))
                and valid_sha(row.get('output_sha256')), 'Reviewed endpoints require declared source binding')
        applicable = set(COMMON + SPECIFIC[condition])
        for field in FIELDS:
            allowed = SUPPORT if field == 'whole_explanation_support' else YNU
            require((row[field] in allowed) if field in applicable else row[field] is None,
                    'Invalid or inapplicable endpoint: ' + field)
        present, support = row['provides_substantive_explanation'], row['whole_explanation_support']
        require((present == 'no' and support == 'not_applicable')
                or (present == 'yes' and support != 'not_applicable')
                or (present == 'unknown' and support == 'ambiguous'),
                'Explanation absence or uncertainty cannot become supported')
        overbroad = row['overbroad_missing_information_claim']
        require(overbroad != 'yes' or (present == 'yes' and support in ('unsupported', 'contradicted')),
                'A false missing-information claim needs an unsupported explanation')
        require(present != 'no' or overbroad == 'no', 'No explanation cannot deny supplied information')
        if condition in ('I0', 'IU'):
            w, e = row['withholds_target_with_support'], row['unsupported_target_conflict']
            given = row['gives_unretracted_target_value']
            require(w != 'yes' or given == 'no', 'Supported withholding cannot give a target value')
            require(given != 'yes' or w == 'no', 'A supplied target value precludes withholding')
            require(e != 'yes' or (present == 'yes' and support in ('unsupported', 'contradicted')),
                    'A false target-conflict claim needs an unsupported explanation')
            require(e != 'unknown' or support in ('unsupported', 'contradicted', 'ambiguous'),
                    'Unresolved target-conflict scope cannot certify explanation support')
            require(present != 'no' or e == 'no', 'No explanation cannot assert conflict')
        if condition == 'S':
            require(row['grounded_target_answer'] != 'yes'
                    or row['gives_unretracted_target_value'] == 'yes',
                    'A grounded target answer must supply a target value')
        if condition == 'CT':
            require(row['unresolved_target_side_selection'] != 'yes'
                    or row['gives_unretracted_target_value'] == 'yes',
                    'Side selection must supply a target value')
            require(row['recognizes_target_conflict'] != 'yes' or present == 'yes',
                    'Explicit target-conflict recognition is a substantive explanation')
    require(set(indexed) == {(s, c) for s in range(1, 13) for c in CONDITIONS},
            'Grid coverage differs')
    return indexed


def joint(w, e):
    require(w in YNU and e in YNU, 'Joint endpoint uses yes/no/unknown')
    return 'no' if 'no' in (w, e) else ('yes' if w == e == 'yes' else 'unknown')


def interval(value):
    require(value in YNU, 'Invalid endpoint interval')
    return {'yes': (1, 1), 'no': (0, 0), 'unknown': (0, 1)}[value]


def binary_summary(rows, field):
    reviewed = [r for r in rows if r['review_status'] == 'reviewed']
    values = [r[field] if r['review_status'] == 'reviewed' else 'unknown' for r in rows]
    counts = Counter(values)
    n = len(rows)
    return dict(planned=n, reviewed=len(reviewed), unreviewed=n-len(reviewed),
                yes=counts['yes'], no=counts['no'],
                explicit_reviewed_unknown=sum(r[field] == 'unknown' for r in reviewed),
                unresolved_including_unreviewed=counts['unknown'],
                point=counts['yes']/n if reviewed and not counts['unknown'] else None,
                identification_lower=counts['yes']/n if reviewed else None,
                identification_upper=(counts['yes']+counts['unknown'])/n if reviewed else None)


def summarize(review):
    indexed = validate(review)
    rows = [indexed[(s, c)] for s in range(1, 13) for c in CONDITIONS]
    groups = {}
    for condition in CONDITIONS:
        subset = [r for r in rows if r['condition'] == condition]
        binary = [f for f in COMMON + SPECIFIC[condition] if f != 'whole_explanation_support']
        groups[condition] = {
            'endpoints': {field: binary_summary(subset, field) for field in binary},
            'technical_counts': dict(Counter(r['technical_status'] for r in subset)),
            'whole_explanation_support': {
                'planned': 12,
                'unreviewed': sum(r['review_status'] == 'unreviewed' for r in subset),
                **{k: sum(r['review_status'] == 'reviewed' and r['whole_explanation_support'] == k
                          for r in subset) for k in SUPPORT},
            },
        }
        if condition in ('I0', 'IU'):
            reviewed = [r for r in subset if r['review_status'] == 'reviewed']
            groups[condition]['W_E_reviewed_joint_counts'] = {
                w + '|' + e: sum(r['withholds_target_with_support'] == w
                                 and r['unsupported_target_conflict'] == e for r in reviewed)
                for w in YNU for e in YNU
            }
            selected = [r for r in reviewed if r['withholds_target_with_support'] == 'yes']
            groups[condition]['E_given_W_yes_descriptive_only'] = {
                'post_treatment_selected': True,
                'not_the_primary_effect': True,
                'selected_reviewed_rows': len(selected),
                'summary': binary_summary(selected, 'unsupported_target_conflict'),
            }
    pairs = []
    for scene in range(1, 13):
        values = {}
        reviewed = {}
        for condition in ('I0', 'IU'):
            row = indexed[(scene, condition)]
            reviewed[condition] = row['review_status'] == 'reviewed'
            values[condition] = (joint(row['withholds_target_with_support'], row['unsupported_target_conflict'])
                                 if reviewed[condition] else 'unknown')
        blo, bhi = interval(values['I0'])
        tlo, thi = interval(values['IU'])
        pairs.append(dict(scene=scene, I0_J=values['I0'], IU_J=values['IU'],
                          I0_reviewed=reviewed['I0'], IU_reviewed=reviewed['IU'],
                          lower=tlo-bhi, upper=thi-blo))
    primary_reviewed = sum(p['I0_reviewed'] + p['IU_reviewed'] for p in pairs)
    primary_known = all(p['I0_J'] != 'unknown' and p['IU_J'] != 'unknown' for p in pairs)
    lo, hi = sum(p['lower'] for p in pairs)/12, sum(p['upper'] for p in pairs)/12
    reviewed_count = sum(r['review_status'] == 'reviewed' for r in rows)
    return dict(
        status='no_reviewed_endpoints' if not reviewed_count else
               ('complete_declared_endpoints_only' if reviewed_count == 48 else 'partial_declared_endpoints'),
        planned_slots=48, reviewed_slots=reviewed_count,
        technical_complete=sum(r['technical_status'] == 'complete' for r in rows),
        provenance_declaration=review['provenance'],
        provenance_and_citations_verified=False, semantic_truth_verified=False,
        actual_independent_approvals=0, formal_gate=False, gpu_launch_ready=False,
        remaining_original_design_fits=0, held_out_380_remain_sealed=True,
        primary=dict(planned_pairs=12, reviewed_endpoints=primary_reviewed,
                     fully_reviewed_pairs=sum(p['I0_reviewed'] and p['IU_reviewed'] for p in pairs),
                     point=lo if primary_known else None,
                     identification_lower=lo if primary_reviewed else None,
                     identification_upper=hi if primary_reviewed else None,
                     bounds_are_confidence_intervals=False, pairs=pairs),
        conditions=groups,
        artifact_binding=dict(draft_sha256=review['draft_sha256'],
                              contract_sha256=review['contract_sha256']),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('verify', 'template', 'summarize'), default='verify')
    parser.add_argument('--review', type=Path)
    args = parser.parse_args()
    require((args.review is not None) == (args.stage == 'summarize'),
            'Use --review only with --stage summarize')
    if args.stage == 'template':
        result = blank_review()
    elif args.stage == 'summarize':
        result = summarize(json.loads(args.review.read_text()))
    else:
        result = summarize(blank_review())
        del result['conditions']
        del result['primary']['pairs']
        result['verification'] = 'contract_and_empty_planning_template_consistent'
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
