"""Seal and score the two-case line-output rerun against the frozen author reference."""
import argparse
from collections import Counter
import json
from pathlib import Path

import query_determinacy_shared_lines_run as run
from query_determinacy_shared_lines import merge, parse

METHODS = ('direct', 'joint', 'branch')
REFERENCE = run.base.PILOT_PUBLIC.with_name('reference.json')


def decode(record, domain, branch):
    if record is None:
        return {'status': 'unexecuted', 'final': None, 'worlds': []}
    if record['status'] != 'complete':
        return {'status': record['status'], 'final': None, 'worlds': []}
    try:
        final, worlds = parse(record['output'], domain, single_world=branch)
    except ValueError as error:
        return {'status': 'format_invalid', 'error': str(error), 'final': None, 'worlds': []}
    return {'status': 'readable', 'final': final, 'worlds': worlds}


def required_ids(case_ref, spans):
    """Connect expected source/rule spans after collection is sealed."""
    result = {}
    for world in case_ref['worlds']:
        expected = {}
        for field, prefix in (('source_quote', 'S'), ('rule_quote', 'R')):
            if field in world:
                ids = [label for label, span in spans.items() if label.startswith(prefix) and span['text'] == world[field]]
                if len(ids) != 1:
                    raise ValueError('reference text does not uniquely match a public evidence span')
                expected[field] = ids[0]
        if 'source_quote' not in expected:
            raise ValueError('reference missing source quote')
        result[world['value']] = sorted(expected.values())
    return result


def grade(method, records, domain, values, case_ref, question_ref, evidence_by_value):
    branch = method == 'branch'
    outputs = [decode(record, domain, branch) for record in records]
    readable = all(output['status'] == 'readable' for output in outputs)
    worlds = [world for output in outputs for world in output['worlds']]
    actual_values = [world['value'] for world in worlds]
    expected = {world['value']: answer for world, answer in zip(case_ref['worlds'], question_ref['world_answers'])}
    reference_candidates_ok = set(actual_values) == set(expected) if readable else None
    if method == 'direct' or not readable:
        extraction_binding_ok = None
    elif branch:
        extraction_binding_ok = actual_values == values
    else:
        extraction_binding_ok = values is not None and set(actual_values) == set(values)

    judged_worlds = []
    for world in worlds:
        label = expected.get(world['value'])
        required = evidence_by_value.get(world['value'])
        if required is None:
            evidence = 'unknown_world'
        elif sorted(world['evidence_ids']) != required:
            evidence = 'missing_or_wrong_id'
        else:
            evidence = 'supports' if label == world['answer'] else 'contradicts'
        judged_worlds.append(dict(world, expected=label, correct=(label == world['answer']) if label else None,
                                  required_evidence_ids=required, evidence_status=evidence))

    derived = merge([world['answer'] for world in worlds]) if readable else None
    final = (derived if extraction_binding_ok else None) if branch else outputs[0]['final']
    consistent = (final == derived) if final is not None else None
    final_correct = (final == question_ref['final']) if final is not None else None
    resolved = readable and bool(reference_candidates_ok) and extraction_binding_ok is not False
    supported_final = None
    if resolved and all(w['evidence_status'] in ('supports', 'contradicts') for w in judged_worlds):
        supported_final = merge([w['expected'] for w in judged_worlds])
    return {'readable': readable, 'resolved': resolved, 'parts': [output['status'] for output in outputs],
            'format_errors': [output['error'] for output in outputs if 'error' in output],
            'reference_candidates_ok': reference_candidates_ok, 'extraction_binding_ok': extraction_binding_ok,
            'final': final, 'merged_world_labels': derived, 'final_matches_merge': consistent,
            'final_correct': final_correct, 'worlds': judged_worlds, 'evidence_implies': supported_final,
            'unsupported_split_choice': question_ref['final'] == 'U' and final in ('Y', 'N') and supported_final != final,
            'correct_and_supported': bool(resolved and final_correct and consistent
                                          and all(w['correct'] and w['evidence_status'] == 'supports' for w in judged_worlds))}


def route_cost(case_slots, method):
    kinds = {method} if method == 'direct' else {method, 'extract'}
    calls = [entry['record'] for entry in case_slots if entry['attempt']['kind'] in kinds]
    executed = [record for record in calls if record['status'] != 'skipped_extract']

    def sum_tokens(field):
        return sum(record[field] for record in executed) if all(record.get(field) is not None for record in executed) else None

    return {'planned_calls': {'direct': 3, 'joint': 4, 'branch': 7}[method], 'attempted_calls': len(executed),
            'skipped': len(calls) - len(executed), 'input_tokens': sum_tokens('input_tokens'),
            'output_tokens': sum_tokens('output_tokens'), 'call_seconds_sum': sum(r['elapsed_seconds'] for r in executed)}


def score_state(state, reference):
    slots = {(a['case'], a['question'], a['kind'], a['branch']): r
             for a, r in ((entry['attempt'], entry['record']) for entry in state['entries'])}
    rows, extractions, costs = [], {}, {}
    for case in state['public']['cases']:
        cid, domain = case['id'], case['domain']
        case_ref = reference['cases'][cid]
        span_map = state['manifest']['extra']['evidence_map'][cid]
        evidence_by_value = required_ids(case_ref, span_map)
        record = slots.get((cid, None, 'extract', None))
        extract = (run.base.extract.parse(record['output'], domain, record['status'] == 'complete')
                   if record is not None else {'status': 'unexecuted', 'values': None, 'types': None})
        values = extract['values']
        extractions[cid] = dict(extract, matches_reference=None if values is None else set(values) == set(evidence_by_value))
        case_slots = [entry for entry in state['entries'] if entry['attempt']['case'] == cid]
        costs[cid] = {method: route_cost(case_slots, method) for method in METHODS}
        for question in case['questions']:
            qid = question['id']
            qref = case_ref['questions'][qid]
            row = {'case': cid, 'question': qid, 'reference': qref, 'methods': {}}
            for method in METHODS:
                records = [slots.get((cid, qid, method, branch)) for branch in ((0, 1) if method == 'branch' else (None,))]
                row['methods'][method] = grade(method, records, domain, values, case_ref, qref, evidence_by_value)
            rows.append(row)

    totals = {}
    for method in METHODS:
        counts = Counter(planned=len(rows))
        for row in rows:
            result = row['methods'][method]
            counts['readable'] += result['readable']
            counts['unresolved'] += not result['resolved']
            counts['correct_and_supported'] += result['correct_and_supported']
            counts['unsupported_split_choice'] += result['unsupported_split_choice']
            if row['reference']['final'] != 'U':
                counts['same_answer_planned'] += 1
                counts['same_answer_correct_and_supported'] += result['correct_and_supported']
            else:
                counts['split_answer_planned'] += 1
        totals[method] = dict(counts)
    return {'rows': rows, 'method_totals': totals, 'extractions': extractions, 'costs_by_case': costs,
            'scored_slots': state['count'], 'planned_slots': state['total'], 'blocked': state['blocked']}


def seal(run_dir, output):
    snapshot = run.process(run_dir)
    raw = run.base.encode(snapshot)
    run.base.write_new(output, raw)
    return run.base.sha(raw)


def score_sealed(path, digest):
    raw = path.read_bytes()
    if run.base.sha(raw) != digest:
        raise ValueError('seal SHA-256 mismatch before reference access')
    state = json.loads(raw)
    release, public, extra = run.release_config()
    if state['manifest']['extra'] != extra or state['public'] != public:
        raise ValueError('seal release binding mismatch')
    reference_raw = REFERENCE.read_bytes()
    if run.base.sha(reference_raw) != release['reference_sha256']:
        raise ValueError('scoring reference differs from release')
    return dict(score_state(state, json.loads(reference_raw)), seal_sha256=digest,
                reference_sha256=release['reference_sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    stages = parser.add_subparsers(dest='stage', required=True)
    seal_args = stages.add_parser('seal')
    seal_args.add_argument('output', type=Path)
    score_args = stages.add_parser('score')
    score_args.add_argument('seal', type=Path)
    score_args.add_argument('digest')
    score_args.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.stage == 'seal':
        print(seal(run.RUN, args.output))
    else:
        run.base.write_new(args.output, run.base.encode(score_sealed(args.seal, args.digest)))


if __name__ == '__main__':
    main()
