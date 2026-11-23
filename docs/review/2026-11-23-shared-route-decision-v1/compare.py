"""Rebuild the program route from sealed material, then pair with audited model outputs."""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_shared_structured_cpu as cpu
from query_determinacy_structured_rule_baseline import category_lookup

base, contract = cpu.base, cpu.contract
SEAL = '8d3f255c245ba5ecaa60fa5d64eb8bbc86755afba2686b73ca85d6507a56bb58'
MODEL_AUDIT = '577123f9dbf7e6eb24a40ffb5c52bb94bae29c90daa9f320bbadbfb8a8eb61d6'
RECORDS = ROOT / 'docs/review/2026-11-23-shared-structured-cpu-v1/results.json'
MODEL_METHODS = ('direct', 'joint', 'branch')
METHODS = (*MODEL_METHODS, 'program')


def checked_json(path, expected):
    raw = path.read_bytes()
    if base.sha(raw) != expected:
        raise ValueError(f'unexpected SHA-256 for {path.name}')
    return json.loads(raw)


def program_rows(sealed):
    extracts = [row for row in sealed['records'] if row['kind'] == 'extract']
    if len(extracts) != 2 or len({row['case'] for row in extracts}) != 2:
        raise ValueError('expected two recorded extractions')
    observed = {row['case']: row for row in extracts}
    rows = {}
    for case in sealed['public']['cases']:
        cid = case['id']
        spans, sources = contract.materials(case)
        extraction = observed[cid]
        parsed = (contract.extract_candidates(extraction['output'], case['domain'])
                  if extraction['status'] == 'complete' else {'values': None})
        bound = contract.bind(parsed['values'], sources)
        for question in case['questions']:
            if case['domain'] == 'integer':
                numeric = contract.numeric_comparison(question['text'], bound, sources)
                worlds = contract.ensure_worlds(numeric, sources) if numeric is not None else None
                outcome = {'status': 'compared' if worlds is not None else 'unresolved', 'worlds': worlds}
            else:
                outcome = category_lookup(question['text'], bound, sources, spans)
            rows[cid, question['id']] = dict(outcome, bound_from_actual_extraction=bound, spans=spans)
    return rows


def annotations(worlds, reference, expected):
    labels = {w['value']: answer for w, answer in zip(reference['worlds'], expected['world_answers'])}
    correct = [world['answer'] in ('Y','N') and world['answer'] == labels[world['value']] for world in worlds]
    any_wrong = any(world['answer'] in ('Y','N') and not ok for world, ok in zip(worlds, correct))
    return {'wrong_world': any_wrong, 'unknown_world': len(worlds) != 2 or any(w['answer'] == 'X' for w in worlds),
            'worlds_correct_evidence_failed': len(worlds) == 2 and all(correct)
            and any(w['evidence_status'] != 'supports' for w in worlds)}


def compare():
    sealed = checked_json(cpu.RUN / 'seal.json', SEAL)
    program = program_rows(sealed)
    # Score only after the program predictions are produced.
    archive = checked_json(RECORDS, MODEL_AUDIT)
    reference = checked_json(cpu.REFERENCE, sealed['manifest']['reference_sha256'])['cases']
    if archive['seal_sha256'] != SEAL:
        raise ValueError('audited model outputs belong to another run')
    rows, totals = [], {method: Counter() for method in METHODS}
    for old in archive['questions']:
        cid, question = old['case'], old['question']
        ref = reference[cid]
        expected = ref['questions'][question]
        if old['reference'] != expected:
            raise ValueError('audited reference differs')
        result = program[cid, question]
        question_worlds = result['worlds'] or []
        labels = {w['value']: answer for w, answer in zip(ref['worlds'], expected['world_answers'])}
        for world in question_worlds:
            parts = next(w for w in ref['worlds'] if w['value'] == world['value'])
            required = {parts['source_quote']}
            if 'rule_quote' in parts:
                required.add(parts['rule_quote'])
            evidence_texts = {result['spans'][label]['text'] for label in world['evidence_ids']}
            world['correct'] = world['answer'] == labels[world['value']]
            world['evidence_status'] = ('missing_or_wrong' if evidence_texts != required
                                        else 'supports' if world['correct'] else 'contradicts')
        final = contract.final(question_worlds)
        program_score = {
            'worlds': question_worlds, 'final': final, 'status': result['status'],
            'bound_from_actual_extraction': result['bound_from_actual_extraction'],
            'correct_and_supported': final == expected['final'] and len(question_worlds) == 2
            and all(w['evidence_status'] == 'supports' for w in question_worlds),
            'unsupported_split_choice': expected['final'] == 'U' and final in ('Y', 'N'),
        }
        routes = {method: dict(old['methods'][method]) for method in MODEL_METHODS}
        routes['program'] = program_score
        for method, route in routes.items():
            checks = annotations(route['worlds'], ref, expected)
            route.update(checks)
            totals[method].update(planned=1, correct_and_supported=int(route['correct_and_supported']),
                                  final_correct=int(route['final'] == expected['final']),
                                  unsupported_split_choice=int(route['unsupported_split_choice']),
                                  unresolved=int(route['final'] is None),
                                  **{key: int(value) for key, value in checks.items()})
        rows.append({'case': cid, 'question': question, 'reference': expected, 'routes': routes})

    costs = {}
    for method in METHODS:
        kinds = {method} if method == 'direct' else {'extract'} if method == 'program' else {method, 'extract'}
        records = [r for r in archive['records'] if r['kind'] in kinds and r['status'] == 'complete']
        costs[method] = {'model_calls': len(records),
                         'reasoning_calls': sum(r['kind'] != 'extract' for r in records),
                         'input_tokens': sum(r['input_tokens'] for r in records),
                         'output_tokens': sum(r['output_tokens'] for r in records)}
    return {'source_seal_sha256': SEAL, 'source_audit_sha256': MODEL_AUDIT, 'new_model_calls': 0,
            'rows': rows, 'totals': totals, 'costs': costs}


if __name__ == '__main__':
    print(json.dumps(compare(), ensure_ascii=False, sort_keys=True, indent=2))
