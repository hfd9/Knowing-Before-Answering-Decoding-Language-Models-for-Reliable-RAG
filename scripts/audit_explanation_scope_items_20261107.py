"""Read-only, template-aware structural cross-check; stdout CSV, not an independent review."""
import csv
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/review/2026-11-06-explanation-scope-materials-v2'
EXPECTED_MATERIAL_SHA = 'd70c9e72b89e023fae19bf94d91e9bb438bc5e4726fab27786e5db7869bc877e'
EXPECTED_AUTHOR_SHA = '3cd48f094ca6d91365117e3ade11c0b856874c4e548abbd899a9a1593dfe3933'
QUESTION = re.compile(r'According only to the provided fictional archive records, what is the (alpha|omega) code assigned to Unit (XU-\d+)\?')
FACT = re.compile(r'A record assigns Unit (XU-\d+) the (alpha|omega) code (VX-\d+)\.(?: The archive lists (alpha|omega) as a field\.)?')
RULE = ('All records refer to the same snapshot. Each unit has exactly one value for each code field. '
        'Alpha code and omega code are independent fields. Different units may share values. '
        'Records may disagree; no record has priority.')
FILLER = 'The fictional archive stores its records on numbered pages.'
LABELS = {'S': 'one_target_record', 'I0': 'target_unassigned_no_conflicting_record',
          'IU': 'target_unassigned_other_entity_record_conflict', 'CT': 'conflicting_target_records'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    raw = (BASE / 'materials.json').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == EXPECTED_MATERIAL_SHA, 'material fingerprint changed')
    materials = json.loads(raw)['items']
    author_raw = (BASE / 'author-interpretation.json').read_bytes()
    require(hashlib.sha256(author_raw).hexdigest() == EXPECTED_AUTHOR_SHA, 'author interpretation fingerprint changed')
    authors = json.loads(author_raw)
    require(authors['materials_sha256'] == EXPECTED_MATERIAL_SHA, 'author source binding changed')
    a_by_id = {item['id']: item for item in authors['items']}
    require(len(materials) == len(a_by_id) == 48, 'expected 48 materials and interpretations')
    by_scene = defaultdict(dict)
    results = []
    for item in materials:
        item_id = item['id']
        scene = item['scene_id']
        condition = item['condition']
        require(item_id == f'{scene}_{condition}' and condition in LABELS, 'invalid ID/condition')
        require(condition not in by_scene[scene], 'duplicate scene/condition')
        q = QUESTION.fullmatch(item['question'])
        require(q is not None and len(item['documents']) == 5, f'{item_id}: question or slots')
        field, target = q.groups()
        facts, rule_slots, filler_slots = [], [], []
        for slot, text in enumerate(item['documents'], 1):
            if text == RULE:
                rule_slots.append(slot)
            elif text == FILLER:
                filler_slots.append(slot)
            else:
                m = FACT.fullmatch(text)
                require(m is not None, f'{item_id}: unexpected sentence or extra assertion in slot {slot}')
                entity, attribute, value, redundant_field = m.groups()
                facts.append({'slot': slot, 'entity': entity, 'field': attribute, 'value': value,
                              'quote': m.group(0).split(' The archive lists ')[0],
                              'redundant_field': redundant_field})
        require(len(facts) == 3 and len(rule_slots) == len(filler_slots) == 1, f'{item_id}: slot inventory')
        groups = defaultdict(set)
        for fact in facts:
            groups[(fact['entity'], fact['field'])].add(fact['value'])
        target_facts = [x for x in facts if (x['entity'], x['field']) == (target, field)]
        conflicts = [(key, values) for key, values in groups.items() if len(values) > 1]
        actual = (len({x['value'] for x in target_facts}), len(conflicts))
        require(actual == {'S': (1, 0), 'I0': (0, 0), 'IU': (0, 1), 'CT': (2, 1)}[condition],
                f'{item_id}: target/conflict shape')
        if condition == 'IU':
            require(conflicts[0][0][0] != target and conflicts[0][0][1] == field, f'{item_id}: IU conflict scope')
        if condition == 'CT':
            require(conflicts[0][0] == (target, field), f'{item_id}: CT conflict scope')
        author = a_by_id[item_id]
        require(author['construction_interpretation'] == LABELS[condition], f'{item_id}: interpretation mismatch')
        for kind in ('target_record_citations', 'other_same_field_record_citations'):
            for c in author[kind]:
                require(type(c['document_index']) is int and 1 <= c['document_index'] <= 5,
                        f'{item_id}: citation slot out of range')
                require(c['quote'] in item['documents'][c['document_index'] - 1], f'{item_id}: citation mismatch')
                require(any((c['document_index'], c['entity'], c['field'], c['value']) ==
                            (x['slot'], x['entity'], x['field'], x['value']) for x in facts),
                        f'{item_id}: citation attributes mismatch')
        expected_target = {(x['slot'], x['entity'], x['field'], x['value']) for x in target_facts}
        author_target = {(x['document_index'], x['entity'], x['field'], x['value'])
                         for x in author['target_record_citations']}
        require(expected_target == author_target, f'{item_id}: author target citation coverage')
        expected_other = {(x['slot'], x['entity'], x['field'], x['value']) for x in facts
                          if x['entity'] != target and x['field'] == field}
        author_other = {(x['document_index'], x['entity'], x['field'], x['value'])
                        for x in author['other_same_field_record_citations']}
        require(expected_other == author_other, f'{item_id}: author other citation coverage')
        by_scene[scene][condition] = item
        results.append({'item_id': item_id, 'target': target, 'field': field, 'condition': condition,
                        'target_values': '|'.join(sorted({x['value'] for x in target_facts})),
                        'conflict_scope': '|'.join(f'{k[0]}.{k[1]}' for k, _ in conflicts) or 'none',
                        'rule_slot': rule_slots[0], 'filler_slot': filler_slots[0],
                        'record_evidence': ' | '.join(f"D{x['slot']}:{x['entity']}.{x['field']}={x['value']}" for x in facts),
                        'judgment_scope': 'template_structure_only_not_independent_semantic_approval'})
    require(len(by_scene) == 12 and set(a_by_id) == {x['id'] for x in materials}, 'scene or author inventory')
    for scene, items in by_scene.items():
        require(set(items) == set(LABELS), f'{scene}: four conditions required')
        base, variant = items['I0'], items['IU']
        require(base['question'] == variant['question'], f'{scene}: paired question changed')
        require(sum(a != b for a, b in zip(base['documents'], variant['documents'])) == 1,
                f'{scene}: paired slot difference')
    require(Counter(x['condition'] for x in results) == Counter({x: 12 for x in LABELS}), 'condition totals')
    writer = csv.DictWriter(sys.stdout, fieldnames=list(results[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(results)


if __name__ == '__main__':
    main()
