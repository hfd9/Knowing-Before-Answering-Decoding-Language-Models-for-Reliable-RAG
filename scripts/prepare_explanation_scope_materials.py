"""Offline author-exposed draft materials only; no collection or model inference."""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/review'


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def generate(out):
    plan_bytes = (out / 'design-lock.json').read_bytes()
    plan = json.loads(plan_bytes)
    scenes = plan['scenes']
    assert len(scenes) == 12
    assert Counter(tuple(s['role_permutation']) for s in scenes) == Counter({p: 2 for p in itertools.permutations(range(3))})
    assert Counter(s['f'] for s in scenes) == {'alpha': 6, 'omega': 6}
    assert len({s[k] for s in scenes for k in ('target', 'other')}) == 24
    assert len({s[k] for s in scenes for k in ('a', 'b', 'c')}) == 36
    rows, witnesses = [], {}
    for s in scenes:
        for condition in plan['condition_order']:
            role = plan['condition_assignments'][condition]
            first_owner, second_owner = s[role['first_owner']], s[role['second_owner']]
            args = dict(s, owner=first_owner)
            first = plan['first_record_template'].format(**args)
            args.update(owner=second_owner, field=s[role['second_field']], mention=s[role['second_mention']])
            second = plan['second_record_template'].format(**args)
            blocks = [plan['rule_document'], first, second,
                      plan['third_record_template'].format(**s), plan['filler_document']]
            rot = s['slot_rotation']
            docs = blocks[rot:] + blocks[:rot]
            item_id = f"{s['scene_id']}_{condition}"
            assignments = [[first_owner, s['f'], s['a']], [second_owner, s[role['second_field']], s['b']],
                           [s['target'], s['g'], s['c']]]
            row = {'id': item_id, 'scene_id': s['scene_id'], 'condition': condition,
                   'question': plan['question_template'].format(**s), 'documents': docs}
            rows.append(row)
            # A repair removes at most one disputed report. The worlds are witnesses, not an exhaustive set.
            cases = []
            dropped = [None] if condition in ('S', 'I0') else [0, 1]
            target_values = [s['a']] if condition == 'S' else (
                [s['a'], s['b']] if condition == 'CT' else s['alternative_target_values'])
            for drop in dropped:
                for target_value in target_values:
                    if condition == 'CT' and ((drop == 0 and target_value != s['b']) or
                                               (drop == 1 and target_value != s['a'])):
                        continue
                    other_f = s['a'] if condition in ('I0', 'IU') else s['b']
                    if condition == 'IU' and drop == 0:
                        other_f = s['b']
                    world = {(s['target'], s['f']): target_value,
                             (s['target'], s['g']): s['c'],
                             (s['other'], s['f']): other_f,
                             (s['other'], s['g']): s['b'] if condition == 'I0' else s['c']}
                    kept = [a for i, a in enumerate(assignments) if i != drop]
                    assert all(world[(e, f)] == v for e, f, v in kept), (item_id, drop, world, kept)
                    cases.append({'dropped_record_index': drop,
                                  'world': [{'entity': e, 'field': f, 'value': v}
                                            for (e, f), v in sorted(world.items())]})
            assert len(cases) == {'S': 1, 'I0': 2, 'IU': 4, 'CT': 2}[condition]
            witnesses[item_id] = {'displayed_assignments': assignments, 'local_repair_witnesses': cases,
                                  'not_exhaustive': True}
    assert len(rows) == len({r['id'] for r in rows}) == 48
    by_id = {r['id']: r for r in rows}
    for s in scenes:
        a, b = (by_id[f"{s['scene_id']}_{k}"] for k in ('I0', 'IU'))
        assert a['question'] == b['question']
        assert sum(x != y for x, y in zip(a['documents'], b['documents'])) == 1
        word = lambda r: Counter(re.findall(r'[A-Za-z]+|\d+', '\n'.join(r['documents'])))
        assert word(a) == word(b)
        assert sum(map(len, a['documents'])) == sum(map(len, b['documents']))
        for c in plan['condition_order']:
            r = by_id[f"{s['scene_id']}_{c}"]
            assert len(r['documents']) == 5
            rendered = r['question'] + '\n' + '\n'.join(r['documents'])
            assert all(v not in rendered for v in s['alternative_target_values'])
    ordered = sorted(rows, key=lambda r: sha(('scope-input-review-v1|' + r['id']).encode()))
    packet = {'status': 'draft_unapproved_author_exposed',
              'items': [{'item_id': f"P{i:03d}", 'question': r['question'], 'documents': r['documents']}
                        for i, r in enumerate(ordered, 1)]}
    mapping = {f"P{i:03d}": r['id'] for i, r in enumerate(ordered, 1)}
    return {
        'materials.json': {'design_lock_sha256': sha(plan_bytes), 'items': rows},
        'input-packet.json': packet,
        'coordinator.json': {'mapping': mapping, 'witnesses': witnesses,
                             'warning': 'Not model input; witnesses are not exhaustive or gold labels.'},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=('build', 'verify'), required=True)
    parser.add_argument('--version', choices=('v1', 'v2'), default='v1')
    args = parser.parse_args()
    out = BASE / f'2026-11-06-explanation-scope-materials-{args.version}'
    outputs = generate(out)
    if args.stage == 'build':
        assert all(not (out / name).exists() for name in outputs), 'Refusing to overwrite draft outputs'
        for name, data in outputs.items():
            (out / name).write_bytes(encode(data))
    else:
        for name, data in outputs.items():
            assert (out / name).read_bytes() == encode(data), f'Output differs: {name}'
    print(json.dumps({'stage': args.stage, 'version': args.version, 'scenes': 12, 'items': 48, 'primary_pairs': 12,
                      'independent_approval': False, 'formal_gate': False,
                      'gpu_launch_ready': False, 'model_inference': False}))


if __name__ == '__main__':
    main()
