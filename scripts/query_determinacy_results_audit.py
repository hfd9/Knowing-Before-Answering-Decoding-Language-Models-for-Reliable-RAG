#!/usr/bin/env python3
"""Read-only aggregation of manually reviewed answer commitments and fixed journals."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATERIAL = ROOT / 'docs/查询可判定性_探索先导包'
JUDGMENTS = ROOT / 'docs/review/2026-11-12-query-determinacy-results-v1/commitments.csv'
RUNS = (
    ('qwen2.5-3b-query-determinacy-pilot-v1', '2026-11-12-query-determinacy-pilot-v1', 1),
    ('qwen2.5-3b-query-determinacy-remaining-v2', '2026-11-12-query-determinacy-remaining-v2', 16),
    ('qwen2.5-3b-query-determinacy-unattempted-v4', '2026-11-12-query-determinacy-unattempted-v4', 4),
    ('qwen2.5-3b-query-determinacy-unattempted-v5', '2026-11-12-query-determinacy-unattempted-v5', 123),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def collect():
    rows = {}
    file_hashes = {}
    for name, archive, length in RUNS:
        run = ROOT / 'runs' / name
        manifest_path = run / 'manifest.json'
        archived = ROOT / 'docs/review' / archive / 'manifest.json'
        require(manifest_path.read_bytes() == archived.read_bytes(), f'{name}: manifest mismatch')
        manifest_hash = sha(manifest_path)
        manifest = json.loads(manifest_path.read_text())
        for material_name, expected_sha in manifest['materials_sha256'].items():
            require(sha(MATERIAL / material_name) == expected_sha, f'{name}: material changed')
        eos = set(manifest['generation']['eos_token_ids'])
        for folder in ('attempts', 'records'):
            expected = [f'{i:03d}.json' for i in range(length)]
            require(sorted(p.name for p in (run / folder).iterdir()) == expected, f'{name}: journal size mismatch')
        file_hashes[str(manifest_path.relative_to(ROOT))] = manifest_hash
        receipt_names = set()
        for index in range(length):
            ap, rp = (run / sub / f'{index:03d}.json' for sub in ('attempts', 'records'))
            item = manifest['items'][index]
            attempt, record = json.loads(ap.read_text()), json.loads(rp.read_text())
            ah, rh = sha(ap), sha(rp)
            require(attempt == {'index': index, 'id': item['id'], 'manifest_sha256': manifest_hash}, 'attempt binding mismatch')
            ids = record.get('generated_token_ids')
            require(isinstance(ids, list), 'missing generated token ids')
            ids_hash = hashlib.sha256(json.dumps(ids, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            require(record['id'] == item['id'] and record['index'] == index and record['attempt_sha256'] == ah
                    and record['generated_token_ids_sha256'] == ids_hash, 'record binding mismatch')
            require(item['id'] not in rows, 'duplicate attempted id')
            status = 'complete' if ids and ids[-1] in eos and record['output'].strip() else 'technical_failure'
            if name.endswith('unattempted-v5') and status == 'technical_failure':
                receipt_path = run / 'automatic_failures' / f'{index:03d}.json'
                technical = 'empty' if not record['output'].strip() else 'truncated_or_unexpected_stop'
                expected_receipt = {'index': index, 'id': item['id'], 'technical_status': technical,
                                    'attempt_sha256': ah, 'record_sha256': rh,
                                    'decision': 'automatic_technical_failure_unscored_do_not_retry'}
                require(json.loads(receipt_path.read_text()) == expected_receipt, 'failure receipt mismatch')
                receipt_names.add(receipt_path.name)
                file_hashes[str(receipt_path.relative_to(ROOT))] = sha(receipt_path)
            rows[item['id']] = {'status': status, 'output': record['output'], 'source': str(rp.relative_to(ROOT)), 'record_sha256': rh}
            file_hashes[str(ap.relative_to(ROOT))] = ah
            file_hashes[str(rp.relative_to(ROOT))] = rh
        if name.endswith('unattempted-v5'):
            require({p.name for p in (run / 'automatic_failures').iterdir()} == receipt_names, 'unexpected failure receipts')
    return rows, file_hashes


def analyze():
    outputs, files = collect()
    with (MATERIAL / 'key.csv').open(encoding='utf-8-sig', newline='') as f:
        keys = list(csv.DictReader(f))
    with JUDGMENTS.open(encoding='utf-8', newline='') as f:
        judgments = {(r['case'], r['question']): r for r in csv.DictReader(f)}
    require(len(outputs) == 144 and len(keys) == 144 and len(judgments) == 36, 'count mismatch')
    require({x['id'] for x in keys} == set(outputs), 'input/result IDs differ')
    grid = collections.defaultdict(dict)
    for row in keys:
        key = (row['底题'], row['问题'])
        slot = {'来源断言': 'assertion', '分列候选': 'candidate'}.get(row['材料形式'])
        if slot is None:
            require(row['材料形式'] == '单来源假设' and row['单来源取值'] in ('甲', '乙'), 'invalid condition')
            slot = 'single_a' if row['单来源取值'] == '甲' else 'single_b'
        code = judgments[key][slot]
        require(code in ('Y', 'N', 'U', 'X', 'T'), 'invalid commitment')
        result = outputs[row['id']]
        require((code == 'T') == (result['status'] == 'technical_failure'), 'technical state mismatch')
        expected = {'是': 'Y', '否': 'N', '无法唯一确定': 'U'}[row['参考结论']]
        if code == 'T': category = 'technical_missing'
        elif code == 'X': category = 'unknown'
        elif code == expected: category = 'correct'
        elif code == 'U': category = 'overreserve'
        elif expected == 'U': category = 'unsupported_choice'
        else: category = 'wrong'
        require(slot not in grid[key], 'duplicate condition')
        grid[key][slot] = {'id': row['id'], 'family': row['任务族'], 'expected': expected,
                           'code': code, 'category': category, **result}
    determinate = [g for g in grid.values() if g['assertion']['expected'] != 'U']
    split = [g for g in grid.values() if g['assertion']['expected'] == 'U']
    require(len(determinate) == 24 and len(split) == 12, 'semantic grid differs')
    counts = {}
    for name, groups, slots in (('determinate', determinate, ('assertion', 'candidate')),
                                ('split', split, ('assertion', 'candidate')),
                                ('single', list(grid.values()), ('single_a', 'single_b'))):
        counts[name] = {slot: dict(collections.Counter(g[slot]['category'] for g in groups)) for slot in slots}
    transitions = collections.Counter((g['candidate']['category'], g['assertion']['category']) for g in determinate)
    by_family = {}
    for family in ('数值比较', '类别规则'):
        chosen = [g for g in determinate if g['assertion']['family'] == family]
        by_family[family] = {
            'questions': len(chosen),
            'candidate_correct_assertion_overreserve': sum(g['candidate']['category'] == 'correct' and g['assertion']['category'] == 'overreserve' for g in chosen),
            'assertion_correct_candidate_overreserve': sum(g['assertion']['category'] == 'correct' and g['candidate']['category'] == 'overreserve' for g in chosen),
        }
    both_singles = [g for g in determinate if g['single_a']['category'] == g['single_b']['category'] == 'correct']
    result = {
        'total': len(outputs), 'technical_complete': sum(r['status'] == 'complete' for r in outputs.values()),
        'technical_failures': sum(r['status'] != 'complete' for r in outputs.values()),
        'counts': counts,
        'determinate_pair_transitions_candidate_to_assertion': {f'{a}->{b}': n for (a, b), n in sorted(transitions.items())},
        'determinate_by_family': by_family,
        'posthoc_both_singles_correct': {'questions': len(both_singles),
            'candidate_correct_assertion_overreserve': sum(g['candidate']['category'] == 'correct' and g['assertion']['category'] == 'overreserve' for g in both_singles),
            'assertion_correct_candidate_overreserve': sum(g['assertion']['category'] == 'correct' and g['candidate']['category'] == 'overreserve' for g in both_singles)},
        'source_file_count': len(files), 'manual_review_informed_not_independent': True,
        'judgments_sha256': sha(JUDGMENTS), 'key_sha256': sha(MATERIAL / 'key.csv'),
    }
    return result


if __name__ == '__main__':
    print(json.dumps(analyze(), ensure_ascii=False, indent=2))
