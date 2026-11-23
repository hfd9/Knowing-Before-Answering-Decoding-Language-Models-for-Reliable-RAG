"""Reconcile the local, sealed two-case run and reproduce its diagnostic counts."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / 'runs'
RUN = RUNS / 'qwen2.5-3b-query-determinacy-shared-pilot-v1'
ANALYSIS = RUNS / 'qwen2.5-3b-query-determinacy-shared-pilot-analysis-v1'
REFERENCE = ROOT / 'docs/review/2026-11-18-two-case-cpu-v1/reference.json'
EXPECTED_SEAL = 'c1ffe2f73e3d2a6b1b62dbf519d8b7e0f16bb3872f12d5b9ddf4bf8ae02dadb1'
ROUTES = ('direct', 'joint', 'branch')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def raw_trace(method, outputs, case_ref):
    """Read explicit labels for a descriptive check independently of the JSON contract.

    Match only the field pairs observed in this run. Display raw outputs separately.
    This deliberately does not repair, rescore or assess quotations.
    """
    worlds = re.findall(r'"value"\s*:\s*"([^"]+)"\s*,\s*"answer"\s*:\s*"([YN])"', ''.join(outputs))
    expected_values = [value['value'] for value in case_ref['worlds']]
    by_value = {value.removesuffix('单位') if value.removesuffix('单位') in expected_values else value: answer
                for value, answer in worlds}
    if len(worlds) != 2 or set(by_value) != set(expected_values):
        raise ValueError('unreadable diagnostic world labels')
    answers = [by_value[value] for value in expected_values]
    if method == 'branch':
        final = answers[0] if answers[0] == answers[1] else 'U'
    else:
        finals = re.findall(r'"final"\s*:\s*"([YNU])"', outputs[0])
        final, = finals
    return final, answers


def audit():
    raw = (ANALYSIS / 'seal.json').read_bytes()
    if sha(raw) != EXPECTED_SEAL:
        raise ValueError('seal digest mismatch')
    seal = json.loads(raw)
    reference_raw = REFERENCE.read_bytes()
    score_raw = (ANALYSIS / 'score.json').read_bytes()
    score = json.loads(score_raw)
    if score['seal_sha256'] != EXPECTED_SEAL or score['reference_sha256'] != sha(reference_raw):
        raise ValueError('score source mismatch')
    ref = json.loads(reference_raw)['cases']

    sources = {}
    def checked(path, snapshot):
        payload = (RUN / path).read_bytes()
        if json.loads(payload) != snapshot:
            raise ValueError(f'live journal differs from seal: {path}')
        sources[path] = sha(payload)

    for key in ('manifest', 'public'):
        checked(f'{key}.json', seal[key])
    for i, preflight in enumerate(seal['device_preflights']):
        checked(f'preflights/{i:04}.json', preflight)

    slots = []
    traces = {}
    for i, entry in enumerate(seal['entries']):
        attempt, record = entry['attempt'], entry['record']
        checked(f'attempts/{i:04}.json', attempt)
        checked(f'records/{i:04}.json', record)
        if sha(record['output'].encode()) != record['output_sha256']:
            raise ValueError('output digest mismatch')
        try:
            value = json.loads(record['output'])
            json_valid = True
        except json.JSONDecodeError:
            value = None
            json_valid = False
        key = (attempt['case'], attempt['question'], attempt['kind'])
        traces.setdefault(key, []).append(record['output'])
        worlds = (value.get('worlds') or [value]) if isinstance(value, dict) else []
        citation_types = [type(world.get('citations')).__name__ for world in worlds]
        generated = record['generated_token_ids']
        slots.append({'index': i, 'case': attempt['case'], 'question': attempt['question'], 'kind': attempt['kind'],
                      'branch': attempt['branch'], 'output': record['output'], 'json_valid': json_valid,
                      'citation_types_if_json_valid': citation_types, 'status': record['status'],
                      'input_tokens': len(record['input_token_ids']), 'output_tokens': len(generated),
                      'eos': bool(generated and generated[-1] in seal['manifest']['extra']['environment']['eos_token_ids']),
                      'elapsed_seconds': record['elapsed_seconds']})

    diagnostic = []
    route_counts = {method: Counter() for method in ROUTES}
    for row in score['rows']:
        case, question = row['case'], row['question']
        reference = ref[case]['questions'][question]
        methods = {}
        for method, counts in route_counts.items():
            final, answers = raw_trace(method, traces[case, question, method], ref[case])
            counts['strict_scored'] += row[method]['status'] == 'scored'
            counts['strict_supported_correct'] += row[method]['correct_and_supported']
            counts['raw_final_matches'] += final == reference['final']
            counts['raw_world_matches'] += sum(a == b for a, b in zip(answers, reference['world_answers']))
            counts['raw_split_yes_or_no'] += reference['final'] == 'U' and final in ('Y', 'N')
            methods[method] = {'raw_final': final, 'raw_world_answers': answers}
        diagnostic.append({'case': case, 'question': question, 'reference': reference, 'methods': methods})

    cost_check = []
    for row in score['route_costs']:
        kinds = {row['route']} | ({'extract'} if row['route'] != 'direct' else set())
        subset = [s for s in slots if s['case'] == row['case'] and s['kind'] in kinds]
        expected = (len(subset), sum(s['input_tokens'] for s in subset), sum(s['output_tokens'] for s in subset),
                    sum(s['elapsed_seconds'] for s in subset))
        actual = tuple(row[k] for k in ('executed_calls', 'input_tokens', 'output_tokens', 'call_seconds_sum'))
        if actual != expected:
            raise ValueError('cost independent sum mismatch')
        cost_check.append(row)
    extract_hits = sum(json.loads(traces[case, None, 'extract'][0]) == [w['value'] for w in reference['worlds']]
                       for case, reference in ref.items())
    device = seal['device_preflights'][0]
    first = datetime.fromisoformat(seal['entries'][0]['record']['completed_at'])
    last = datetime.fromisoformat(seal['entries'][-1]['record']['completed_at'])
    return {'seal_sha256': EXPECTED_SEAL, 'score_sha256': sha(score_raw), 'live_source_sha256': sources,
            'slot_count': len(slots), 'executed_count': sum(s['status'] == 'complete' for s in slots),
            'json_valid_by_kind': {kind: sum(s['json_valid'] for s in slots if s['kind'] == kind)
                                   for kind in (*ROUTES, 'extract')},
            'eos_count': sum(s['eos'] for s in slots), 'extractions_exact': extract_hits,
            'total_input_tokens': sum(s['input_tokens'] for s in slots),
            'total_output_tokens': sum(s['output_tokens'] for s in slots),
            'call_seconds_sum': sum(s['elapsed_seconds'] for s in slots),
            'preflight_to_last_record_seconds': (last - datetime.fromisoformat(device['checked_at'])).total_seconds(),
            'first_to_last_record_seconds': (last - first).total_seconds(),
            'device': {k: v for k, v in device['device'].items() if k != 'gpu_uuid'},
            'route_counts': route_counts, 'route_costs': cost_check, 'development_choice': score['development_choice'],
            'frozen_score_rows': score['rows'], 'descriptive_label_check': diagnostic, 'outputs': slots}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.parse_args()
    print(json.dumps(audit(), ensure_ascii=False, sort_keys=True, indent=2))
