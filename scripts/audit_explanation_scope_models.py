"""Offline finite-model audit of candidate material; no semantic or independence certification."""
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/review/2026-11-06-explanation-scope-materials-v2'
TECH = ROOT / 'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1'
plan = json.loads((TECH / 'execution-draft.json').read_text())
for path, expected_hash in plan['source_sha256'].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected_hash, path
items = json.loads((BASE / 'materials.json').read_text())['items']
scenes = {s['scene_id']: s for s in json.loads((BASE / 'design-lock.json').read_text())['scenes']}
ids = [r['id'] for r in items]
smoke = [f'exs01_{c}' for c in ('S', 'I0', 'IU', 'CT')]
ordered = smoke + sorted((x for x in ids if x not in smoke),
                         key=lambda x: hashlib.sha256(('explanation-scope-order-v1|' + x).encode()).hexdigest())
assert plan['ordered_ids'] == ordered and plan['smoke_ids'] == smoke and len(set(ordered)) == 48
assert plan['guards'] == {'semantic_independent_approvals': 0, 'formal_gate': False,
                          'gpu_launch_ready': False, 'collection_allowed': False,
                          'held_out_380_accessed': False, 'fit_budget': 0}
fact_pattern = re.compile(r'A record assigns Unit (XU-\d{3}) the (alpha|omega) code (VX-\d{5})\.')
question_pattern = re.compile(r'According only to the provided fictional archive records, what is the (alpha|omega) code assigned to Unit (XU-\d{3})\?')
results = []
for row in items:
    scene = scenes[row['scene_id']]
    match = question_pattern.fullmatch(row['question'])
    assert match
    query_field, target = match.groups()
    assert (target, query_field) == (scene['target'], scene['f'])
    facts = [(i, *m.groups()) for i, doc in enumerate(row['documents'], 1)
             if (m := fact_pattern.match(doc))]
    assert len(facts) == 3
    by_key = defaultdict(set)
    for _, entity, field, value in facts:
        by_key[(entity, field)].add(value)
    conflicts = {key for key, values in by_key.items() if len(values) > 1}
    domain = [scene['a'], scene['b'], scene['c'], scene['alternative_target_values'][0]]
    assert len(set(domain)) == 4
    keys = [(entity, field) for entity in (scene['target'], scene['other']) for field in ('alpha', 'omega')]
    worlds = [dict(zip(keys, values)) for values in itertools.product(domain, repeat=4)]

    def satisfying(kept):
        return [world for world in worlds if all(world[(entity, field)] == value for _, entity, field, value in kept)]

    all_trusted = satisfying(facts)
    repairs = []
    if conflicts:
        assert len(conflicts) == 1
        conflict_key = next(iter(conflicts))
        conflicting = [fact for fact in facts if (fact[1], fact[2]) == conflict_key]
        assert len(conflicting) == 2
        for removed in conflicting:
            retained = [fact for fact in facts if fact != removed]
            valid = satisfying(retained)
            repairs.append({'dropped_document': removed[0], 'world_count': len(valid),
                            'target_values': sorted({w[(target, query_field)] for w in valid})})
    condition = row['condition']
    values = sorted({w[(target, query_field)] for w in all_trusted})
    if condition == 'S':
        assert not conflicts and len(all_trusted) == 4 and values == [scene['a']]
    elif condition == 'I0':
        assert not conflicts and len(all_trusted) == 4 and set(values) == set(domain)
    elif condition == 'IU':
        assert conflicts == {(scene['other'], query_field)} and not all_trusted
        assert len(repairs) == 2 and all(len(x['target_values']) == 4 and x['world_count'] == 16 for x in repairs)
    elif condition == 'CT':
        assert conflicts == {(target, query_field)} and not all_trusted
        assert len(repairs) == 2 and all(len(x['target_values']) == 1 and x['world_count'] == 16 for x in repairs)
        assert {x['target_values'][0] for x in repairs} == {scene['a'], scene['b']}
    else:
        raise AssertionError('unexpected condition')
    results.append({'id': row['id'], 'condition': condition,
                    'finite_all_records_trusted_world_count': len(all_trusted),
                    'finite_all_records_trusted_target_values': values,
                    'minimal_one_record_repair_cases': repairs,
                    'if_all_reports_may_be_wrong_target_values': sorted(domain)})
assert Counter(r['condition'] for r in results) == {c: 12 for c in ('S', 'I0', 'IU', 'CT')}
print(json.dumps({'status': 'finite_model_audit_not_independent_semantic_approval',
                  'execution_draft_sha256': hashlib.sha256((TECH / 'execution-draft.json').read_bytes()).hexdigest(),
                  'domain_size': 4, 'worlds_per_item_before_report_constraints': 256,
                  'assumptions': ['Each retained report is imposed as true only for the given repair.',
                                  'The alternative interpretation permits every report to be false.',
                                  'Finite-domain witnesses do not exhaust unrestricted natural-language models.'],
                  'interpretation_note': 'S has one reported target value, but if all reports may be false its true target is not determined.',
                  'items': results, 'formal_gate': False, 'independent_approval': False,
                  'model_inference': False}, ensure_ascii=False, indent=2))
