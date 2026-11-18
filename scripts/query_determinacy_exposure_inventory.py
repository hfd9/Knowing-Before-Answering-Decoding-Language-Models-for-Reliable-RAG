#!/usr/bin/env python3
"""Read-only inventory of explicit, previously used query-determinacy inputs.

This is not a candidate screen, does not scan arbitrary directories, and never
opens the sealed confirmation set. Only aggregate counts and file hashes leave
the process; an absent listed file stops rather than silently narrowing scope.
"""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'docs/查询可判定性_探索先导包/prompts.jsonl',
    'docs/review/2026-11-15-query-determinacy-development-v1/material.jsonl',
    'docs/review/2026-11-15-query-determinacy-prompt-control-v1/material.jsonl',
    'docs/review/2026-11-15-query-determinacy-fresh-dev-v1/material.jsonl',
    'docs/review/2026-11-15-query-determinacy-source-order-v1/material.jsonl',
    'docs/review/2026-11-15-query-determinacy-oracle-dev-v1/material.jsonl',
    'docs/review/2026-11-15-query-determinacy-world-extract-dev-v1/material.jsonl',
    'docs/review/2026-11-17-query-determinacy-paraphrase-dev-v1/material.jsonl',
)


def prior_question_groups():
    manifest_path = ROOT / 'runs/qwen2.5-3b-small/data/manifest.json'
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != '3fc899266cfad2009dc3f9baa42050fe37a822eb448afea6b2b3f347fbee3a24':
        raise ValueError('previous whitelist manifest changed')
    manifest = json.loads(raw)
    norm = lambda x: ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', x).casefold()))
    result = {}
    for name, split, count, bases in (('train200', 'train', 600, 200), ('val95', 'val', 285, 95),
                                      ('diagnostic100', 'test', 300, 100)):
        path = ROOT / f'runs/qwen2.5-3b-small/data/instances_{split}.jsonl'
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != manifest['splits'][split]['sha256']:
            raise ValueError('previous whitelist data changed: ' + name)
        rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
        if len(rows) != count or len({x['original_id'] for x in rows}) != bases:
            raise ValueError('previous whitelist count changed: ' + name)
        result[name] = {'rows': count, 'bases': bases, 'sha256': digest,
                        'unique_normalized_questions': len({norm(x['question']) for x in rows})}
    path = ROOT / 'prompts/semantic_transfer_materials_v5.json'
    raw = path.read_bytes()
    units = json.loads(raw)['units']
    if len(units) != 30 or len({x['original_id'] for x in units}) != 30:
        raise ValueError('transfer material count changed')
    result['transfer30'] = {'rows': len(units), 'bases': 30, 'sha256': hashlib.sha256(raw).hexdigest(),
                            'unique_normalized_questions': len({norm(x['question']) for x in units})}
    return result


def inventory():
    result = []
    prompts, questions = set(), set()
    for name in FILES:
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('missing or symlinked listed file: ' + name)
        raw = path.read_bytes()
        rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
        if not rows or any(not isinstance(x.get('prompt'), str) for x in rows):
            raise ValueError('invalid listed input: ' + name)
        q = [line.removeprefix('问题：').strip() for x in rows for line in x['prompt'].splitlines()
             if line.startswith('问题：') and line.removeprefix('问题：').strip()]
        prompts.update(x['prompt'] for x in rows)
        questions.update(q)
        result.append({'path': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'rows': len(rows),
                       'rows_with_explicit_question_line': sum(
                           any(line.startswith('问题：') and line.removeprefix('问题：').strip()
                               for line in x['prompt'].splitlines()) for x in rows)})
    return {'files': result, 'total_rows': sum(x['rows'] for x in result),
            'distinct_exact_prompts': len(prompts), 'distinct_exact_question_lines': len(questions),
            'previous_question_groups': prior_question_groups(),
            'scope': 'explicit local inputs and sampled prior question groups; no candidate comparisons; no held-out 380',
            'warning': 'row counts are not unique base counts or evidence of model/pretraining exposure'}


if __name__ == '__main__':
    print(json.dumps(inventory(), ensure_ascii=False, indent=2))
