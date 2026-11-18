#!/usr/bin/env python3
"""CPU-only scheduling prototype for a shared-extraction comparison.

No model, persistence, prompt rendering, retries, evaluation or production
collection is implemented. An actual study needs a separately reviewed runner.
"""
import query_determinacy_extract_v2 as extract


def simulate(background, questions, invoke):
    """Call an injected mock and preserve outputs; no references are accepted."""
    if set(background) != {'id', 'evidence', 'domain'}:
        raise ValueError('background must contain only id, evidence and domain')
    if background['domain'] not in ('integer', 'identifier'):
        raise ValueError('unknown domain')
    if len(questions) != 3 or any(set(q) != {'id', 'text'} for q in questions):
        raise ValueError('expected three reference-free question objects')
    if len({q['id'] for q in questions}) != 3:
        raise ValueError('question IDs must be unique')
    if not all(isinstance(background[k], str) and background[k] for k in ('id', 'evidence')):
        raise ValueError('invalid background')
    if not all(isinstance(q[k], str) and q[k] for q in questions for k in ('id', 'text')):
        raise ValueError('invalid question')

    calls = []

    def call(kind, question=None, values=None):
        request = {'kind': kind, 'background_id': background['id'], 'evidence': background['evidence'],
                   'question_id': question['id'] if question else None,
                   'question': question['text'] if question else None,
                   'values': values}
        result = invoke(dict(request))
        if type(result) is not dict or set(result) != {'status', 'output'}:
            raise ValueError('invalid mock response envelope')
        if result['status'] not in ('complete', 'technical_failure') or not isinstance(result['output'], str):
            raise ValueError('invalid mock response')
        calls.append({'request': request, 'response': dict(result)})
        return result

    # Direct calls remain measurable even when shared extraction is unusable.
    direct = {q['id']: call('direct', q) for q in questions}
    raw = call('extract')
    parsed = extract.parse(raw['output'], background['domain'], raw['status'] == 'complete')
    downstream = {}
    for q in questions:
        if parsed['status'] != 'parsed':
            downstream[q['id']] = {'status': parsed['status'], 'joint': None, 'branches': None}
            continue
        # Immutable values make it explicit both arms receive the same prediction.
        values = tuple(parsed['values'])
        joint = call('joint', q, values)
        branches = [call('branch', q, (value,)) for value in values]
        downstream[q['id']] = {'status': 'attempted', 'joint': joint, 'branches': branches}
    return {'direct': direct, 'extraction': {'raw': raw, 'parsed': parsed},
            'downstream': downstream, 'calls': calls}
