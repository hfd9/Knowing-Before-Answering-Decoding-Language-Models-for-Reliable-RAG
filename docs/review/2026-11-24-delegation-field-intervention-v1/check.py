"""Replay the four reference-field interventions on eight exposed paraphrases."""
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parent / '2026-11-23-delegation-new-wording-v1'
CONDITIONS = {'original': (), 'fact_only': ('grant',), 'rule_only': ('exception',),
              'both': ('grant', 'exception')}


def replay():
    spec = importlib.util.spec_from_file_location('frozen_wording_check', ORIGINAL / 'check.py')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    saved = old.read('results.json')
    old.require(old.replay() == saved, 'frozen results differ')
    from query_determinacy_delegation import solve

    refs, cases = old.read('author-reference.json'), old.read('cases.json')
    rows = {}
    for case, item in saved['rows'].items():
        if item['group'] != 'new_paraphrase':
            continue
        ref = refs[case]
        base = item['parsed']
        rows[case] = {'missing': [k for k in CONDITIONS['both'] if base[k] is None],
                      'reference': ref['result'], 'conditions': {}}
        for condition, fields in CONDITIONS.items():
            given = base | {key: ref['structure'][key] for key in fields}
            result = solve(cases[case], given)
            old.require(condition != 'original' or result == item['result'], 'baseline differs')
            rows[case]['conditions'][condition] = {
                'structure': given, 'result': result,
                'strict_grounded': given == ref['structure'] and old.equal_grounded(result, ref['result']),
                'world_answer_matches': sum(value['answer'] == ref['result']['worlds'][slot]['answer']
                                            for slot, value in result['worlds'].items()),
                'false_unique': ref['result']['final'] == 'U' and result['final'] in ('Y', 'N'),
            }
    old.require(len(rows) == 8, 'unexpected diagnosis size')
    groups = {'all': list(rows)}
    for group, missing in (('F1', ['grant']), ('R3', ['exception']), ('F1+R3', ['grant', 'exception'])):
        groups[group] = [case for case, row in rows.items() if row['missing'] == missing]
    old.require([len(g) for g in groups.values()] == [8, 2, 2, 4], 'unexpected missing-field distribution')
    summary = {}
    for group, cases_in_group in groups.items():
        summary[group] = {}
        for condition in CONDITIONS:
            values = [rows[case]['conditions'][condition] for case in cases_in_group]
            summary[group][condition] = {'cases': len(values),
                                         'strict_grounded': sum(r['strict_grounded'] for r in values),
                                         'world_answers_matching': sum(r['world_answer_matches'] for r in values),
                                         'unresolved': sum(r['result']['final'] == 'X' for r in values),
                                         'false_unique': sum(r['false_unique'] for r in values)}
    return {'frozen_source': saved['source_commit'], 'old_material_seal_sha256': saved['material_seal_sha256'],
            'summary': summary, 'rows': rows}


if __name__ == '__main__':
    result = replay()
    if sys.argv[1:] == ['--verify']:
        if result != json.loads((HERE / 'results.json').read_text()):
            raise ValueError('saved intervention results differ')
        print('Verified 32 intervention cells.')
    elif not sys.argv[1:]:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        raise SystemExit('usage: check.py [--verify]')
