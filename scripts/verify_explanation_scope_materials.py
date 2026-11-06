"""Read-only independent surface, repair-witness and tokenizer checks for draft inputs."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'code'))
import evidence_experiment as renderer  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument('--version', choices=('v1', 'v2'), default='v1')
args = parser.parse_args()
BASE = ROOT / f'docs/review/2026-11-06-explanation-scope-materials-{args.version}'
plan = json.loads((BASE / 'design-lock.json').read_text())
materials = json.loads((BASE / 'materials.json').read_text())
packet = json.loads((BASE / 'input-packet.json').read_text())
coord = json.loads((BASE / 'coordinator.json').read_text())
rows = {r['id']: r for r in materials['items']}
scenes = {s['scene_id']: s for s in plan['scenes']}
assert len(rows) == len(packet['items']) == len(coord['mapping']) == 48
assert materials['design_lock_sha256'] == hashlib.sha256((BASE / 'design-lock.json').read_bytes()).hexdigest()
assert Counter(r['condition'] for r in rows.values()) == {c: 12 for c in ('S', 'I0', 'IU', 'CT')}
assert len(scenes) == 12 and len(coord['witnesses']) == 48
assert len(set(coord['mapping'].values())) == 48 and set(coord['mapping'].values()) == set(rows)
for item in packet['items']:
    r = rows[coord['mapping'][item['item_id']]]
    assert item['question'] == r['question'] and item['documents'] == r['documents']

fact = re.compile(r'A record assigns Unit (XU-\d{3}) the (alpha|omega) code (VX-\d{5})\.')
question = re.compile(r'According only to the provided fictional archive records, what is the (alpha|omega) code assigned to Unit (XU-\d{3})\?')
actual_assignments = {}
world_count = Counter()
for item_id, row in rows.items():
    match = question.fullmatch(row['question'])
    assert match and len(row['documents']) == 5
    f, target = match.groups()
    scene = scenes[row['scene_id']]
    assert f == scene['f'] and target == scene['target']
    facts = [fact.match(doc).groups() for doc in row['documents'] if fact.match(doc)]
    assert len(facts) == 3
    observed = Counter(facts)
    stated = [tuple(x) for x in coord['witnesses'][item_id]['displayed_assignments']]
    assert observed == Counter(stated)
    target_facts = [value for entity, field, value in facts if (entity, field) == (target, f)]
    other = scene['other']
    other_facts = [value for entity, field, value in facts if (entity, field) == (other, f)]
    c = row['condition']
    t, o, g = target, other, scene['g']
    a, b, value_c = scene['a'], scene['b'], scene['c']
    expected = {
        'S': [(t, f, a), (o, f, b), (t, g, value_c)],
        'I0': [(o, f, a), (o, g, b), (t, g, value_c)],
        'IU': [(o, f, a), (o, f, b), (t, g, value_c)],
        'CT': [(t, f, a), (t, f, b), (t, g, value_c)],
    }
    assert observed == Counter(expected[c])
    if c == 'S':
        assert target_facts == [scene['a']] and len(other_facts) == 1
    elif c == 'I0':
        assert not target_facts and len(other_facts) == 1
    elif c == 'IU':
        assert not target_facts and set(other_facts) == {scene['a'], scene['b']}
    else:
        assert set(target_facts) == {scene['a'], scene['b']}
    assert scene['a'] != scene['b']
    visible = row['question'] + '\n' + '\n'.join(row['documents'])
    assert all(v not in visible for v in scene['alternative_target_values'])
    repairs = coord['witnesses'][item_id]['local_repair_witnesses']
    assert coord['witnesses'][item_id]['not_exhaustive'] is True
    assert len(repairs) == {'S': 1, 'I0': 2, 'IU': 4, 'CT': 2}[c]
    worlds_by_repair = {}
    for repair in repairs:
        world = {(a['entity'], a['field']): a['value'] for a in repair['world']}
        assert len(world) == 4 and set(world) == {(e, field) for e in (target, other) for field in ('alpha', 'omega')}
        dropped = repair['dropped_record_index']
        retained = [a for i, a in enumerate(stated) if i != dropped]
        assert all(world[(e, field)] == v for e, field, v in retained)
        if dropped is not None:
            dropped_entity, dropped_field, dropped_value = stated[dropped]
            assert world[(dropped_entity, dropped_field)] != dropped_value
        worlds_by_repair.setdefault(dropped, set()).add(world[(target, f)])
        world_count[c] += 1
    if c == 'I0':
        assert worlds_by_repair == {None: set(scene['alternative_target_values'])}
    if c == 'IU':
        assert worlds_by_repair == {0: set(scene['alternative_target_values']), 1: set(scene['alternative_target_values'])}
    if c == 'CT':
        assert worlds_by_repair == {0: {scene['b']}, 1: {scene['a']}}
    actual_assignments[item_id] = observed

old = [ROOT / 'docs/review/2026-10-23-semantic-claims-v1/public/input_packet.json',
       ROOT / 'prompts/behavior_relation_attachment_materials_v1.json',
       ROOT / 'prompts/behavior_binding_materials_v1.json']
old_text = '\n'.join(p.read_text() for p in old)
new_identifiers = {s[k] for s in scenes.values() for k in ('target', 'other', 'a', 'b', 'c')}
assert not any(identifier in old_text for identifier in new_identifiers)
old_entity_suffixes = set(re.findall(r'U-(\d{3})', old_text))
old_code_suffixes = set(re.findall(r'K-(\d{5})', old_text))
entity_suffix_overlap = sorted({s[k].split('-')[1] for s in scenes.values() for k in ('target', 'other')} & old_entity_suffixes)
code_suffix_overlap = sorted({s[k].split('-')[1] for s in scenes.values() for k in ('a', 'b', 'c')} & old_code_suffixes)
target_lower = sum(s['target'] < s['other'] for s in scenes.values())
if args.version == 'v2':
    assert not entity_suffix_overlap and not code_suffix_overlap and target_lower == 6

reference = json.loads((ROOT / 'runs/qwen2.5-3b-relation-attachment-v1/protocol.json').read_text())
model_path = Path(reference['model'])
for name in ('config.json', 'tokenizer.json', 'tokenizer_config.json'):
    assert hashlib.sha256((model_path / name).read_bytes()).hexdigest() == reference['model_files_sha256'][name]
tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
assert renderer.FREE_INSTRUCTION == reference['instruction']
lengths, tokenids = {}, {}
for item_id, row in rows.items():
    text = renderer.render_input({'question': row['question'], 'docs': row['documents']}, 'free_answer', 'chat', tokenizer)
    ids = renderer.encode(tokenizer, text, 'chat')['input_ids']
    assert len(ids) + 128 <= reference['context_tokens']
    assert all(marker not in text for marker in (item_id, 'local_repair_witnesses', 'alternative_target_values'))
    lengths[item_id] = len(ids)
    tokenids[item_id] = ids

token_differences = []
for scene_id in sorted(scenes):
    a, b = (rows[f'{scene_id}_{c}'] for c in ('I0', 'IU'))
    assert a['question'] == b['question']
    assert sum(x != y for x, y in zip(a['documents'], b['documents'])) == 1
    words = lambda r: Counter(re.findall(r'[A-Za-z]+|\d+', '\n'.join(r['documents'])))
    assert words(a) == words(b) and sum(map(len, a['documents'])) == sum(map(len, b['documents']))
    ids_a, ids_b = tokenids[a['id']], tokenids[b['id']]
    token_differences.append({'scene_id': scene_id, 'I0_tokens': len(ids_a), 'IU_tokens': len(ids_b),
                              'equal_token_length': len(ids_a) == len(ids_b),
                              'equal_token_multiset': Counter(ids_a) == Counter(ids_b)})

print(json.dumps({'status': 'draft_surface_world_and_tokenizer_checked_not_semantic_independent_approval',
                  'version': args.version,
                  'items': len(rows), 'scenes': len(scenes), 'primary_pairs': len(token_differences),
                  'witnesses_by_condition': dict(world_count), 'input_tokens_min': min(lengths.values()),
                  'input_tokens_max': max(lengths.values()), 'input_tokens_total': sum(lengths.values()),
                  'token_pair_checks': token_differences, 'collision_scope_files': len(old),
                  'old_entity_number_suffix_overlap': entity_suffix_overlap,
                  'old_code_number_suffix_overlap': code_suffix_overlap,
                  'scenes_target_id_lexicographically_smaller': target_lower,
                  'model_weights_loaded': False, 'model_inference': False, 'independent_approval': False,
                  'formal_gate': False, 'gpu_launch_ready': False}, ensure_ascii=False, indent=2))
