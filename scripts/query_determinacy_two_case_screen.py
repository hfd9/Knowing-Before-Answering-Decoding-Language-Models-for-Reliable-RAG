#!/usr/bin/env python3
"""Screen fixed public candidates against explicit previously allowed files only."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import query_determinacy_collision_screen as collision
import query_determinacy_exposure_inventory as inventory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/review/2026-11-18-two-case-cpu-v1'
TRANSFER = ROOT / 'runs/qwen2.5-3b-semantic-transfer-materials-v5/materials/inputs.json'
TRANSFER_SHA = '2b0ed2bde91624a7eab2eec38c66f4d2d9c2f875760ca7d49995c847c512ae97'


def refs():
    recorded = json.loads((ROOT / 'docs/review/2026-11-18-shared-extract-feasibility-v1/allowed-input-inventory.json').read_bytes())
    if inventory.inventory() != recorded:
        raise ValueError('previous allowlist inventory changed')
    questions, backgrounds = {}, {}
    def add(bucket, text, group):
        if isinstance(text, str) and collision.normalize(text):
            bucket.setdefault(text, set()).add(group)
    for filename in inventory.FILES:
        rows = [json.loads(line) for line in (ROOT / filename).read_text().splitlines() if line.strip()]
        for row in rows:
            lines = row['prompt'].splitlines()
            for line in lines:
                if line.startswith('问题：'):
                    add(questions, line.removeprefix('问题：').strip(), filename)
            bg = '\n'.join(line for line in lines if not line.startswith('问题：'))
            add(backgrounds, bg, filename)
    for split in ('train', 'val', 'test'):
        path = ROOT / f'runs/qwen2.5-3b-small/data/instances_{split}.jsonl'
        for line in path.read_text().splitlines():
            row = json.loads(line)
            add(questions, row['question'], 'sampled_' + split)
            for doc in row['docs']:
                add(backgrounds, doc, 'sampled_' + split)
    path = ROOT / 'prompts/semantic_transfer_materials_v5.json'
    for unit in json.loads(path.read_bytes())['units']:
        add(questions, unit['question'], 'transfer30_questions')
    raw = TRANSFER.read_bytes()
    if hashlib.sha256(raw).hexdigest() != TRANSFER_SHA:
        raise ValueError('transfer documents changed')
    for row in json.loads(raw):
        for doc in row['docs']:
            add(backgrounds, doc, 'transfer30_documents')
    return questions, backgrounds


def evaluate(text, bucket):
    totals, groups, examples = Counter(), {}, []
    for prior, labels in bucket.items():
        result = collision.compare(text, prior)
        totals['comparisons'] += 1
        totals['short'] += int(result['short'])
        hits = [k for k in ('exact', 'containment', 'near') if result[k] is True]
        for flag in hits:
            totals[flag] += 1
            for label in sorted(labels):
                groups.setdefault(label, Counter())[flag] += 1
        if hits:
            examples.append({'old_sha256': hashlib.sha256(prior.encode()).hexdigest(),
                             'groups': sorted(labels), 'flags': hits})
    return {'counts': dict(totals), 'matched_groups': {k: dict(v) for k, v in sorted(groups.items())},
            'match_fingerprints': examples,
            'manual_review_required': bool(examples) or totals['short'] > 0}


def screen(expanded=False):
    public_raw = (OUT / ('public-12-v2.json' if expanded else 'public.json')).read_bytes()
    cases = json.loads(public_raw)['cases']
    if len(cases) != (12 if expanded else 2):
        raise ValueError('unexpected case count')
    questions, backgrounds = refs()
    result = []
    for case in cases:
        result.append({'case': case['id'], 'background': evaluate(case['background'], backgrounds),
                       'questions': {q['id']: evaluate(q['text'], questions) for q in case['questions']}})
    return {'schema': 'pilot_overlap_triage_v1', 'public_sha256': hashlib.sha256(public_raw).hexdigest(),
            'question_references': len(questions), 'background_references': len(backgrounds), 'cases': result,
            'limits': 'Only explicit previous allowlist; short includes unknown; no held-out 380 or pretraining; flags are not semantic judgments.'}


if __name__ == '__main__':
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] != '--expanded'):
        raise SystemExit('usage: script [--expanded]')
    print(json.dumps(screen('--expanded' in sys.argv), ensure_ascii=False, indent=2, sort_keys=True))
