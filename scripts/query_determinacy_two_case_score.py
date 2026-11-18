#!/usr/bin/env python3
"""Connect an already-hashed CPU mock result to the frozen author reference."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/review/2026-11-18-two-case-cpu-v1'


def payload(envelope):
    if not isinstance(envelope, dict) or envelope.get('status') != 'complete':
        return None
    try:
        return json.loads(envelope['output'])
    except (ValueError, KeyError, TypeError):
        return None


def grade_world(world, reference_world, expected, background):
    if not isinstance(world, dict) or world.get('value') != reference_world['value']:
        return {'status': 'unresolved', 'answer_correct': False, 'evidence_ok': False}
    answer = world.get('answer')
    cites = world.get('citations')
    if answer not in ('Y', 'N') or not isinstance(cites, list) or not all(isinstance(c, str) for c in cites):
        return {'status': 'unresolved', 'answer_correct': False, 'evidence_ok': False}
    required = [reference_world['source_quote']]
    if 'rule_quote' in reference_world:
        required.append(reference_world['rule_quote'])
    evidence_ok = all(quote in cites and quote in background for quote in required)
    return {'status': 'scored', 'answer_correct': answer == expected, 'evidence_ok': evidence_ok,
            'answer': answer, 'supported_correct': answer == expected and evidence_ok}


def grade(method, envelope, ref, refq, background, extracted=None):
    expected_values = [x['value'] for x in ref['worlds']]
    if method == 'branch':
        if not isinstance(envelope, list) or len(envelope) != 2 or not extracted:
            return {'status': 'unresolved', 'final_correct': False, 'worlds': []}
        parsed = [payload(x) for x in envelope]
        if any(not isinstance(x, dict) or x.get('value') != extracted[i] for i, x in enumerate(parsed)):
            return {'status': 'unresolved', 'final_correct': False, 'worlds': []}
        codes = [x.get('answer') for x in parsed]
        if any(code not in ('Y', 'N') for code in codes):
            return {'status': 'unresolved', 'final_correct': False, 'worlds': []}
        final = codes[0] if codes[0] == codes[1] and codes[0] in ('Y', 'N') else 'U' if set(codes) == {'Y', 'N'} else 'X'
        worlds = parsed
    else:
        data = payload(envelope)
        if not isinstance(data, dict) or data.get('final') not in ('Y', 'N', 'U') or not isinstance(data.get('worlds'), list):
            return {'status': 'unresolved', 'final_correct': False, 'worlds': []}
        final, worlds = data['final'], data['worlds']
    if len(worlds) != 2 or any(not isinstance(x, dict) for x in worlds):
        return {'status': 'unresolved', 'final_correct': False, 'worlds': []}
    values = [x.get('value') for x in worlds]
    if any(not isinstance(value, str) for value in values) or len(set(values)) != 2 or set(values) != set(expected_values):
        return {'status': 'unresolved', 'final_correct': False, 'worlds': []}
    if method == 'joint' and (not extracted or set(values) != set(extracted)):
        return {'status': 'unresolved', 'final_correct': False, 'worlds': []}
    by_value = {x['value']: x for x in worlds}
    checks = [grade_world(by_value[w['value']], w, refq['world_answers'][i], background)
              for i, w in enumerate(ref['worlds'])]
    final_correct = final == refq['final']
    return {'status': 'scored', 'final': final, 'final_correct': final_correct, 'worlds': checks,
            'all_worlds_correct': all(x['answer_correct'] for x in checks),
            'all_evidence_ok': all(x['evidence_ok'] for x in checks),
            'correct_and_supported': final_correct and all(x['supported_correct'] for x in checks)}


def score(results_path, expected_sha, expected_reference_sha):
    # Refuse an unsealed or modified result before touching reference.json.
    raw = results_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha:
        raise ValueError('result hash does not match precommitted hash')
    data = json.loads(raw)
    public_raw = (BASE / 'public.json').read_bytes()
    if data['schema'] != 'two_world_cpu_mock_results_v1' or data['public_sha256'] != hashlib.sha256(public_raw).hexdigest():
        raise ValueError('result/public mismatch')
    public = json.loads(public_raw)
    ref_raw = (BASE / 'reference.json').read_bytes()
    if hashlib.sha256(ref_raw).hexdigest() != expected_reference_sha:
        raise ValueError('reference hash does not match precommitted hash')
    ref = json.loads(ref_raw)
    if set(data['cases']) != set(ref['cases']) or set(data['cases']) != {c['id'] for c in public['cases']}:
        raise ValueError('case mismatch')
    rows = []
    for case in public['cases']:
        case_ref = ref['cases'][case['id']]
        result = data['cases'][case['id']]
        parsed = result['extraction']['parsed']
        extracted = parsed['values'] if parsed['status'] == 'parsed' else None
        for q in case['questions']:
            refq = case_ref['questions'][q['id']]
            d = result['downstream'][q['id']]
            rows.append({'case': case['id'], 'question': q['id'], 'reference': refq['final'],
                         'direct': grade('direct', result['direct'][q['id']], case_ref, refq, case['background']),
                         'joint': grade('joint', d['joint'], case_ref, refq, case['background'], extracted),
                         'branch': grade('branch', d['branches'], case_ref, refq, case['background'], extracted)})
    return {'result_sha256': digest, 'reference_sha256': hashlib.sha256(ref_raw).hexdigest(),
            'mode': data['mode'], 'simulated_calls': data['simulated_calls'], 'rows': rows}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('input', type=Path)
    cli.add_argument('expected_sha256')
    cli.add_argument('expected_reference_sha256')
    cli.add_argument('output', type=Path)
    args = cli.parse_args()
    value = score(args.input, args.expected_sha256, args.expected_reference_sha256)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
