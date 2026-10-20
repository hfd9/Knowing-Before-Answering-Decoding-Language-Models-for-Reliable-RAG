"""CPU replay of explicitly written, history-exposed semantic judgments; never approve labels."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

import semantic_transfer_review_intake as intake

ROOT = intake.ROOT
MATERIALS = ROOT / 'runs/qwen2.5-3b-semantic-transfer-materials-v4-r2'
DEFAULT = ROOT / 'runs/qwen2.5-3b-semantic-transfer-author-review-v1'
RATINGS = ROOT / 'docs/records/2026-10-20-semantic-transfer-author-input-review-ratings.json'
DEV_SEAL = ROOT / 'docs/records/2026-10-20-semantic-transfer-author-input-review-development48-sealed.json'
require, read, digest = intake.require, intake.read, intake.digest


def put(path, value, write):
    expected = value if isinstance(value, str) else intake.serialize(value)
    if path.exists():
        require(path.read_text() == expected, f'Frozen review artifact differs: {path}')
    elif write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected)
    else:
        raise ValueError(f'Missing review artifact: {path}')


def validate(rows, value, dev):
    require(value['history_exposed'] is True and value['independent_gold'] is False
        and value['approved_for_training'] is False and value['gpu_launch_ready'] is False,
        'Exposed author review must never become independent approval')
    ratings = value['ratings']
    require(len(ratings) == len({r['id'] for r in ratings}) == len(rows) == 240, 'All240 unique judgments required')
    by_id = {r['id']: r for r in ratings}
    require(set(by_id) == {r['id'] for r in rows}, 'Rating IDs mismatch')
    bases = value['base_decisions']
    require(set(bases) == {r['original_id'] for r in rows} and len(bases) == 30, 'All30 base audits required')
    documents = {}
    background_slots = []
    for row in rows:
        rating = by_id[row['id']]
        for key in ['id', 'original_id', 'partition', 'expression', 'condition']:
            require(rating[key] == row[key], 'Review identity/partition mismatch')
        require(rating['semantic_mode'] in {'answer', 'refuse', 'conflict', 'unknown'}, 'Invalid manual semantic judgment')
        require(rating['confidence'] in {'high', 'moderate', 'ambiguous'}, 'Confidence required')
        require(rating['rationale'].strip() and rating['required_facts'], 'Explicit semantic reasoning required')
        require(rating['independent_gold'] is False and rating['approved_for_training'] is False, 'Row cannot approve labels')
        if rating['semantic_mode'] == 'answer':
            require(bool(rating['support_chain']), 'Support chain required')
        if rating['semantic_mode'] == 'refuse':
            require(bool(rating['missing_facts']), 'Missing premise required')
        if rating['semantic_mode'] == 'conflict':
            require(len(rating['conflicting_claims']) >= 2, 'Two incompatible candidate claims required')
        require({c['doc_slot'] for c in rating['citations']} == set(row['target_slots']), 'Both target passages must be cited')
        for citation in rating['citations']:
            slot = citation['doc_slot']
            require(type(slot) is int and 1 <= slot <= 5, 'Invalid citation slot')
            document = row['docs'][slot - 1]
            start, end, quote = citation['start'], citation['end'], citation['quote']
            require(type(start) is int and type(end) is int and 0 <= start < end <= len(document), 'Invalid citation offsets')
            require(document[start:end] == quote and citation['document_sha256'] == hashlib.sha256(document.encode()).hexdigest(),
                'Citation or full-document hash mismatch')
        note = bases[row['original_id']]
        require(note['required'] and note['missing'].strip() and note['conflict'].strip()
            and note['s_i_change'].strip(), 'Base needs explicit support/missing/conflict/edit audit')
        order = [f'{e}_{c}' for e in ['A', 'B'] for c in ['S', 'K', 'I', 'C']]
        require(rating['semantic_mode'] == note['modes'][order.index(row['expression'] + '_' + row['condition'])],
            'Expanded judgment differs from explicit eight-cell manual decision')
        for slot, document in enumerate(row['docs'], 1):
            sha = hashlib.sha256(document.encode()).hexdigest()
            documents.setdefault(sha, dict(characters=len(document), occurrences=[]))['occurrences'].append(dict(id=row['id'], slot=slot))
            if slot not in row['target_slots'] and row['expression'] == 'A' and row['condition'] == 'S':
                background_slots.append(dict(original_id=row['original_id'], slot=slot, document_sha256=sha))
    for oid, note in bases.items():
        group = [r for r in rows if r['original_id'] == oid]
        require(len(group) == 8 and len({r['question'] for r in group}) == 1, 'Eight fixed-question variants required')
        require(len(note['backgrounds']) == 3, 'All three background roles must be assessed')
        expected_slots = set(range(1, 6)) - set(group[0]['target_slots'])
        require({int(t.split(':')[0]) for t in note['backgrounds']} == expected_slots, 'Background assessment slots mismatch')
        for row in group:
            require(row['target_slots'] == group[0]['target_slots'], 'Target slots changed')
            require(all(row['docs'][s-1] == group[0]['docs'][s-1] for s in expected_slots), 'Background/order changed')
    require(value['reviewed_slots'] == 1200 and value['reviewed_unique_full_documents'] == len(documents), 'Reading inventory mismatch')
    require(len(dev['ratings']) == 48 and dev['history_exposed'] is True, 'Original48 seal required')
    for rating in dev['ratings']:
        require(by_id[rating['id']] == rating, 'Development judgment changed after seal')
    return by_id, documents, background_slots


def derive(rows, value, authors, preflight):
    by_id = {r['id']: r for r in value['ratings']}
    author_by_id = {r['id']: r for r in authors}
    require(set(author_by_id) == set(by_id), 'Author comparison IDs mismatch')
    bases, pairs = value['base_decisions'], []
    for oid, note in bases.items():
        group = {(r['expression'], r['condition']): r for r in rows if r['original_id'] == oid}
        conditions = ['S', 'K', 'I', 'C']
        contrasts = [('AB_' + c, ('A', c), ('B', c)) for c in conditions]
        contrasts += [(e + '_S_to_' + c, (e, 'S'), (e, c)) for e in ['A', 'B'] for c in ['K', 'I', 'C']]
        for name, left, right in contrasts:
            a, b = group[left], group[right]
            la, lb = by_id[a['id']]['semantic_mode'], by_id[b['id']]['semantic_mode']
            known = la != 'unknown' and lb != 'unknown'
            caveat = note.get('expression_caveats', {}).get(left[1]) if name.startswith('AB_') else None
            if name.startswith('AB_'):
                reason = caveat or '本轮未识别出额外的表达命题差异；不是独立确认或形式等价证明。'
                structural_status = 'caveat_recorded' if caveat else 'no_specific_difference_identified'
                relation = 'same_reviewed_state' if known and la == lb else 'unknown_state_retained'
            elif right[1] == 'I':
                reason = note['s_i_change']
                structural_status = ('deletion_only_at_required_relation' if reason.startswith('DELETION_ONLY:')
                    else 'modality_recast' if reason.startswith('MODALITY_RECAST:') else 'other_facts_changed')
                relation = 'answer_to_refuse' if la == 'answer' and lb == 'refuse' else 'other_or_unknown'
            elif right[1] == 'C':
                reason = note['conflict']
                structural_status = 'modality_ambiguous' if not known else 'incompatible_claims_identified'
                relation = 'answer_to_conflict' if la == 'answer' and lb == 'conflict' else 'other_or_unknown'
            else:
                reason = 'K中新增/重排的支持属性与S结论相容；具体目标引文和逐条判断保留。'
                structural_status = 'compatible_support_reviewed'
                relation = 'answer_to_answer' if la == lb == 'answer' else 'other_or_unknown'
            pairs.append(dict(original_id=oid, partition=a['partition'], contrast=name,
                left_id=a['id'], right_id=b['id'], left_mode=la, right_mode=lb,
                determinate=known, relation_review=relation, structural_status=structural_status,
                rationale=reason, input_token_delta=preflight['input_tokens'][b['id']] - preflight['input_tokens'][a['id']],
                independent_gold=False, probe_prediction=None, probability_delta=None))
    counts = Counter(r['semantic_mode'] for r in value['ratings'])
    partitions = {part: dict(planned=sum(r['partition'] == part for r in rows),
        counts=dict(Counter(r['semantic_mode'] for r in value['ratings'] if r['partition'] == part)))
        for part in ['semantic_train', 'semantic_dev', 'semantic_eval']}
    ab = [p for p in pairs if p['contrast'].startswith('AB_')]
    si = [p for p in pairs if p['contrast'].endswith('S_to_I')]
    sc = [p for p in pairs if p['contrast'].endswith('S_to_C')]
    sk = [p for p in pairs if p['contrast'].endswith('S_to_K')]
    author_comparison = Counter('unknown_retained' if r['semantic_mode'] == 'unknown' else
        'same_proposed_class' if r['semantic_mode'] == author_by_id[r['id']]['author_proposed_mode'] else
        'different_determinate_class' for r in value['ratings'])
    summary = dict(status='exposed_author_input_review_complete_not_independent', reviewed_cells=240,
        reviewed_bases=30, reviewed_document_slots=1200, counts=dict(counts), partitions=partitions,
        provisional_determinate_cells=240 - counts['unknown'],
        provisional_determinate_coverage=(240 - counts['unknown']) / 240,
        independently_reviewed_cells=0, approved_semantic_labels=0, independent_semantic_coverage=0,
        gpu_launch_ready=False, approved_for_training=False,
        author_comparison=dict(author_comparison), author_agreement_is_not_accuracy=True,
        expression_pairs=dict(planned=len(ab), same_determinate_reviewed_state=sum(p['relation_review'] == 'same_reviewed_state' for p in ab),
            unknown_pairs=sum(not p['determinate'] for p in ab),
            caveats=sum(p['structural_status'] == 'caveat_recorded' for p in ab),
            no_specific_difference_identified=sum(p['structural_status'] == 'no_specific_difference_identified' for p in ab)),
        S_to_I_pairs=dict(planned=len(si), reviewed_answer_to_refuse=sum(p['relation_review'] == 'answer_to_refuse' for p in si),
            structural_counts=dict(Counter(p['structural_status'] for p in si))),
        S_to_C_pairs=dict(planned=len(sc), reviewed_answer_to_conflict=sum(p['relation_review'] == 'answer_to_conflict' for p in sc),
            unknown_pairs=sum(not p['determinate'] for p in sc)),
        S_to_K_pairs=dict(planned=len(sk), reviewed_answer_to_answer=sum(p['relation_review'] == 'answer_to_answer' for p in sk)),
        fixed_question_bases=30, fixed_background_and_slot_bases=30,
        unknown_ids=[r['id'] for r in value['ratings'] if r['semantic_mode'] == 'unknown'],
        no_probe_or_behavior_results_used=True, new_gpu_forwards=0, generated_answers=0, trained_probes=0)
    return summary, pairs


def csv_text(rows, columns):
    handle = io.StringIO(newline='')
    writer = csv.DictWriter(handle, fieldnames=columns, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})
    return handle.getvalue()


def process(materials=MATERIALS, ratings_path=RATINGS, seal_path=DEV_SEAL, run=DEFAULT, write=True):
    rows, _, _, _, _ = intake.load_materials(materials)
    value, seal = read(ratings_path), read(seal_path)
    require(value['source_protocol_sha256'] == digest(materials / 'protocol.json')
        and value['inputs_sha256'] == digest(materials / 'materials/inputs.json'), 'Frozen review source mismatch')
    require(value['development_seal_sha256'] == digest(seal_path), 'Development seal hash mismatch')
    by_id, documents, backgrounds = validate(rows, value, seal)
    preflight = read(materials / 'preflight.json')
    summary, pairs = derive(rows, value, read(materials / 'coordinator/author_judgments.json'), preflight)
    source_paths = [ratings_path, seal_path, materials / 'protocol.json', materials / 'materials/inputs.json',
        materials / 'coordinator/author_judgments.json', materials / 'preflight.json', Path(__file__)]
    protocol = dict(task='CPU_exposed_author_review_only', source_sha256={str(p.resolve()): digest(p) for p in source_paths},
        independent_gold=False, no_approval_or_inference_path=True)
    inventory = dict(reading_is_reviewer_declaration_not_proved_by_hash=True,
        unique_full_documents=len(documents), document_slots=1200, documents=documents,
        background_slots=backgrounds, unique_backgrounds=len({b['document_sha256'] for b in backgrounds}))
    comparison = [dict(id=r['id'], original_id=r['original_id'], partition=r['partition'], expression=r['expression'],
        condition=r['condition'], question=r['question'], semantic_mode=by_id[r['id']]['semantic_mode'],
        confidence=by_id[r['id']]['confidence'], rationale=by_id[r['id']]['rationale'],
        required_facts=by_id[r['id']]['required_facts'], citations=by_id[r['id']]['citations'],
        input_tokens=preflight['input_tokens'][r['id']],
        probe_prediction=None, probe_scores=None, generated_answer=None, independent_gold=False) for r in rows]
    outputs = {'protocol.json': protocol, 'summary.json': summary, 'pair_audits.json': pairs,
        'fulltext_inventory.json': inventory, 'joint_table.json': comparison,
        'joint_table.csv': csv_text(comparison, list(comparison[0])),
        'pair_audits.csv': csv_text(pairs, list(pairs[0]))}
    for name, content in outputs.items():
        put(run / name, content, write)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['analyze', 'verify'], default='verify')
    parser.add_argument('--run-dir', type=Path, default=DEFAULT)
    args = parser.parse_args()
    require(args.run_dir.resolve().is_relative_to(ROOT / 'runs'), 'Output must stay in project runs')
    require(not args.run_dir.resolve().is_relative_to(MATERIALS), 'Keep review separate from frozen materials')
    print(intake.serialize(process(run=args.run_dir.resolve(), write=args.stage == 'analyze')))


if __name__ == '__main__':
    main()
