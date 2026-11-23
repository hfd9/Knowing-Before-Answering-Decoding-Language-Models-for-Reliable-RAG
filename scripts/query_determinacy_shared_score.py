#!/usr/bin/env python3
"""Seal a completed CPU/real journal and score against a separately supplied reference.

The seal precedes any reference read. Byte-level citations are a conservative
mechanical check, not proof of semantic support or an independent assessment.
"""
import argparse
import json
from pathlib import Path

import query_determinacy_shared_live as live


def seal(run, output):
    with live.locked(run):
        state = live.replay(run)
        preflights = sorted((run / 'preflights').iterdir())
        if any(p.is_symlink() or p.name != f'{i:04d}.json' for i, p in enumerate(preflights)):
            raise ValueError('invalid preflight journal')
        payload = {'schema': 'shared_live_seal_v1', 'manifest': state['manifest'], 'public': state['public'],
                   'entries': state['entries'], 'count': state['count'], 'total': state['total'],
                   'technical_blocked': state['blocked'],
                   'device_preflights': [json.loads(p.read_bytes()) for p in preflights]}
        raw = live.encode(payload)
        live.write_new(output, raw)
    return live.sha(raw)


def parse_response(record):
    if not record or record['status'] != 'complete':
        return None
    try:
        value = json.loads(record['output'])
    except (ValueError, TypeError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def grade(method, records, expected, qref, background, extracted):
    # Retain final correctness even when worlds or evidence are invalid.
    result = {'status': 'unresolved', 'final': None, 'final_correct': None,
              'worlds': [], 'all_worlds_correct': None, 'all_evidence_ok': None,
              'final_consistent_with_worlds': None, 'correct_and_supported': False}
    if method == 'branch':
        if not extracted or len(records) != 2:
            return result
        worlds = [parse_response(record) for record in records]
        if any(not isinstance(w, dict) for w in worlds):
            return result
        answers = [w.get('answer') for w in worlds]
        if any(a not in ('Y', 'N') for a in answers):
            return result
        result['final'] = answers[0] if answers[0] == answers[1] else 'U'
    else:
        data = parse_response(records[0]) if records else None
        if not data:
            return result
        if data.get('final') in ('Y', 'N', 'U'):
            result['final'] = data['final']
        worlds = data.get('worlds')
    if result['final'] is not None:
        result['final_correct'] = result['final'] == qref['final']
    if not isinstance(worlds, list) or len(worlds) != 2 or any(not isinstance(w, dict) for w in worlds):
        return result
    values = [w.get('value') for w in worlds]
    if any(not isinstance(v, str) for v in values) or len(set(values)) != 2:
        return result
    if method in ('joint', 'branch') and (not extracted or set(values) != set(extracted)):
        return result
    if method == 'branch' and values != extracted:
        return result
    refs = expected['worlds']
    if set(values) != {r['value'] for r in refs}:
        result['status'] = 'wrong_candidates'
        return result
    by_value = {w['value']: w for w in worlds}
    checks = []
    for index, ref in enumerate(refs):
        world = by_value[ref['value']]
        cites = world.get('citations')
        answer = world.get('answer')
        required = [ref['source_quote']]
        if 'rule_quote' in ref:
            required.append(ref['rule_quote'])
        valid = answer in ('Y', 'N') and isinstance(cites, list) and all(isinstance(c, str) for c in cites)
        evidence = valid and all(q in cites and q in background for q in required)
        checks.append({'value': ref['value'], 'answer': answer, 'valid': valid,
                       'answer_correct': valid and answer == qref['world_answers'][index],
                       'evidence_ok': bool(evidence)})
    result['worlds'] = checks
    if not all(c['valid'] for c in checks) or result['final'] is None:
        return result
    codes = [c['answer'] for c in checks]
    derived = codes[0] if codes[0] == codes[1] else 'U'
    result.update(status='scored', all_worlds_correct=all(c['answer_correct'] for c in checks),
                  all_evidence_ok=all(c['evidence_ok'] for c in checks),
                  final_consistent_with_worlds=result['final'] == derived)
    result['correct_and_supported'] = bool(result['final_correct'] and result['all_worlds_correct']
                                           and result['all_evidence_ok'] and result['final_consistent_with_worlds'])
    return result


def development_choice(rows, costs):
    """A conservative development-only heuristic; never a safety guarantee."""
    routes = ('direct', 'joint', 'branch')
    if not rows or not costs or any(r[m]['status'] != 'scored' for r in rows for m in routes):
        return {'status': 'no_conclusion', 'reason': 'unscored_or_missing'}
    totals = {}
    for method in routes:
        group = [c for c in costs if c['route'] == method]
        if not group or any(c['journal_slots'] != c['planned_calls'] or c['skipped_extract']
                            or c['input_tokens'] is None or c['output_tokens'] is None for c in group):
            return {'status': 'no_conclusion', 'reason': 'incomplete_cost'}
        totals[method] = sum(c['input_tokens'] + c['output_tokens'] for c in group)
    def dominates(candidate, other):
        if totals[candidate] >= totals[other] or not any(r[candidate]['correct_and_supported'] for r in rows):
            return False
        for row in rows:
            a, b = row[candidate], row[other]
            if b['correct_and_supported'] and not a['correct_and_supported']:
                return False
            if (row['reference_final'] == 'U' and a['final'] in ('Y', 'N')
                    and b['final'] not in ('Y', 'N')):
                return False
        return True
    winners = [m for m in routes if all(dominates(m, n) for n in routes if n != m)]
    return {'status': 'candidate' if len(winners) == 1 else 'no_conclusion',
            'candidate': winners[0] if len(winners) == 1 else None,
            'reason': 'paired_development_heuristic', 'route_total_tokens': totals}


def score(sealed, seal_sha, reference, reference_sha):
    raw = sealed.read_bytes()
    if live.sha(raw) != seal_sha:
        raise ValueError('seal hash mismatch before reference access')
    data = json.loads(raw)
    if data.get('schema') != 'shared_live_seal_v1':
        raise ValueError('invalid seal')
    public = data['public']
    live.validate_public(public)
    extra = data['manifest']['extra']
    if extra.get('mode') == live.PILOT_MODE:
        release, release_digest = live.read_pilot_release(live.PILOT_RUN)
        if extra.get('release_sha256') != release_digest or reference_sha != release['scoring_reference_sha256']:
            raise ValueError('pilot seal or scoring reference does not match release')
    raw_ref = reference.read_bytes()
    if live.sha(raw_ref) != reference_sha:
        raise ValueError('reference hash mismatch')
    ref = json.loads(raw_ref)
    if set(ref['cases']) != {c['id'] for c in public['cases']}:
        raise ValueError('reference case mismatch')
    entries = data['entries']
    by_slot = {(e['attempt']['case'], e['attempt']['question'], e['attempt']['kind'], e['attempt']['branch']): e['record'] for e in entries}
    rows = []
    costs = []
    for case in public['cases']:
        cr = ref['cases'][case['id']]
        if set(cr['questions']) != {q['id'] for q in case['questions']}:
            raise ValueError('reference question mismatch')
        ext = by_slot.get((case['id'], None, 'extract', None))
        parsed = live.extract.parse(ext['output'], case['domain'], ext['status'] == 'complete') if ext else {'status': 'unattempted', 'values': None}
        values = parsed['values']
        case_entries = [e for e in entries if e['attempt']['case'] == case['id']]
        for route, kinds, planned in (('direct', {'direct'}, 3), ('joint', {'extract', 'joint'}, 4),
                                      ('branch', {'extract', 'branch'}, 7)):
            records = [e['record'] for e in case_entries if e['attempt']['kind'] in kinds]
            invoked = [r for r in records if r['status'] != 'skipped_extract']
            tokens = lambda field: (sum(r[field] for r in invoked)
                                    if all(type(r.get(field)) is int and r[field] >= 0 for r in invoked)
                                    else None)
            costs.append({'case': case['id'], 'route': route, 'planned_calls': planned,
                          'journal_slots': len(records), 'executed_calls': len(invoked),
                          'skipped_extract': len(records) - len(invoked),
                          'input_tokens': tokens('input_tokens'), 'output_tokens': tokens('output_tokens'),
                          'call_seconds_sum': sum(r['elapsed_seconds'] for r in invoked)})
        for question in case['questions']:
            cid, qid = case['id'], question['id']
            get = lambda kind, branch=None: by_slot.get((cid, qid, kind, branch))
            rows.append({'case': cid, 'question': qid, 'reference_final': cr['questions'][qid]['final'],
                         'extraction_status': parsed['status'], 'extracted': values,
                         'extraction_correct': None if values is None else set(values) == {w['value'] for w in cr['worlds']},
                         'direct': grade('direct', [get('direct')], cr, cr['questions'][qid], case['background'], None),
                         'joint': grade('joint', [get('joint')], cr, cr['questions'][qid], case['background'], values),
                         'branch': grade('branch', [get('branch', 0), get('branch', 1)], cr, cr['questions'][qid], case['background'], values)})
    return {'schema': 'shared_live_score_v1', 'seal_sha256': seal_sha, 'reference_sha256': reference_sha,
            'count_planned_questions': len(rows), 'journal_slots': data['count'], 'journal_total': data['total'],
            'technical_blocked': data['technical_blocked'], 'rows': rows, 'route_costs': costs,
            'development_choice': development_choice(rows, costs),
            'note': 'informed reference, exact quote check only; no independent semantic certification'}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest='stage', required=True)
    s = sub.add_parser('seal'); s.add_argument('run', type=Path); s.add_argument('output', type=Path)
    s = sub.add_parser('score'); s.add_argument('seal', type=Path); s.add_argument('seal_sha'); s.add_argument('reference', type=Path); s.add_argument('reference_sha'); s.add_argument('output', type=Path)
    args = cli.parse_args()
    if args.stage == 'seal':
        print(seal(args.run, args.output))
    else:
        result = score(args.seal, args.seal_sha, args.reference, args.reference_sha)
        live.write_new(args.output, live.encode(result))


if __name__ == '__main__':
    main()
