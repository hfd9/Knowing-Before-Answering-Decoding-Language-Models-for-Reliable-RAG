"""Verify the frozen diagnostic and score separately collected raw responses."""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path

from query_determinacy_delegation import (
    RECORDS, SLOTS, context, response_object, solve, structured_from_parser, validate_structure,
)


ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'docs/review/2026-11-23-rule-applicability-paired-v1'
ROUTES = ('direct', 'extract')


def read(path):
    return json.loads(path.read_text())


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def verify_hashes(path):
    for filename, digest in read(path).items():
        require(sha256((ROOT / filename).read_bytes()).hexdigest() == digest, f'file changed: {filename}')


def prompt(records, instructions, route):
    return '\n'.join([instructions['common'],
                     *(f'[{key}] {records[key]}' for key in RECORDS), instructions[route]])


def inspect_split(cases, references, expected_count):
    require(cases.keys() == references.keys(), 'reference ids differ')
    groups = defaultdict(dict)
    for case_id, records in cases.items():
        ref = references[case_id]
        require(set(records) == set(RECORDS) and all(records.values()), f'invalid source slots: {case_id}')
        require({answer for _, answer in context(records).values()} == {'Y', 'N'}, 'defaults must disagree')
        require(solve(records, ref['structure']) == ref['result'], f'reference replay differs: {case_id}')
        group = groups[ref['root']]
        key = (ref['wording'], ref['direction'])
        require(key not in group, f'duplicate variant: {case_id}')
        group[key] = case_id
    require(len(groups) == expected_count, 'wrong root count')
    for variants in groups.values():
        require(set(variants) == {(w, d) for w in (1, 2) for d in ('match', 'reverse')}, 'incomplete root')
        ids = list(variants.values())
        require(len({references[i]['family'] for i in ids}) == 1, 'multiple wording families in one root')
        for key in ('W1', 'W2', 'R1', 'R2'):
            require(len({cases[i][key] for i in ids}) == 1, 'changed non-target record')
        for wording in (1, 2):
            a, b = (variants[wording, direction] for direction in ('match', 'reverse'))
            require(cases[a]['R3'] == cases[b]['R3'], 'rule changed with actual authorization')
            left, right = (references[i]['structure']['grant'] for i in (a, b))
            for case_id, grant in ((a, left), (b, right)):
                fact = cases[case_id]['F1']
                require(all(fact.count(role) == 1 for role in grant.values()), 'ambiguous role occurrence')
            swapped = cases[a]['F1'].replace(left['grantor'], '\0').replace(left['recipient'], left['grantor'])
            swapped = swapped.replace('\0', left['recipient'])
            require(swapped == cases[b]['F1'], 'role swap changed other text')
            require(left['grantor'] == right['recipient'] and left['recipient'] == right['grantor'],
                    'wrong role swap in reference')
            require(references[a]['result']['final'] in ('Y', 'N') and references[b]['result']['final'] == 'U',
                    'expected unique-to-disagreement change')
        for direction in ('match', 'reverse'):
            a, b = (variants[wording, direction] for wording in (1, 2))
            require(all(cases[a][k] != cases[b][k] for k in ('R3', 'F1')), 'empty paraphrase')
            require(all(references[a][k] == references[b][k] for k in ('structure', 'result')),
                    'paraphrase changes reference semantics')
    return groups


def load_packet():
    verify_hashes(PACK / 'development-freeze.json')
    verify_hashes(PACK / 'material-freeze.json')
    policy, instructions = (read(PACK / name) for name in ('decision.json', 'prompts.json'))
    dev, held = (read(PACK / f'{part}-cases.json') for part in ('dev', 'heldout'))
    dev_ref, held_ref = (read(PACK / f'{part}-reference.json') for part in ('dev', 'heldout'))
    dev_groups = inspect_split(dev, dev_ref, policy['development_roots'])
    held_groups = inspect_split(held, held_ref, policy['heldout_roots'])
    require(not (dev.keys() & held.keys() or dev_groups.keys() & held_groups.keys()), 'split overlap')
    dev_families = {ref['family'] for ref in dev_ref.values()}
    held_families = {ref['family'] for ref in held_ref.values()}
    require(not (dev_families & held_families) and len(held_families) == policy['heldout_wording_families'],
            'wording family split overlap or wrong count')
    for slot in ('R3', 'F1'):
        require(not ({row[slot] for row in dev.values()} & {row[slot] for row in held.values()}),
                f'verbatim repeat across splits: {slot}')
    require(all(len(group) == policy['variants_per_root'] for group in (*dev_groups.values(), *held_groups.values())),
            'variant count differs from protocol')
    require({ref['result']['final'] for ref in held_ref.values()} == {'Y', 'N', 'U'}, 'unbalanced outcome types')
    return policy, instructions, dev, dev_ref, held, held_ref, held_groups


def direct_result(value):
    require(isinstance(value, dict) and set(value) == {'structure', 'worlds', 'final'}, 'invalid direct keys')
    structure = validate_structure(value['structure'])
    worlds = value['worlds']
    require(isinstance(worlds, dict) and set(worlds) == set(SLOTS), 'invalid source keys')
    for row in worlds.values():
        require(isinstance(row, dict) and set(row) == {'applies', 'rule', 'answer', 'evidence'}, 'invalid world keys')
        require(row['applies'] is None or type(row['applies']) is bool, 'invalid applicability')
        require(row['rule'] in (None, 'R1', 'R2', 'R3') and row['answer'] in ('X', 'Y', 'N'), 'invalid answer or rule')
        evidence = row['evidence']
        require(isinstance(evidence, list) and all(item in RECORDS for item in evidence)
                and len(evidence) == len(set(evidence)), 'invalid or duplicate evidence ids')
    require(value['final'] in ('X', 'Y', 'N', 'U'), 'invalid final answer')
    return structure, {'worlds': worlds, 'final': value['final']}


def judge(records, ref, route, raw=None):
    explicit_final = None
    try:
        if route == 'direct':
            response = response_object(raw)
            if isinstance(response, dict):
                explicit_final = response.get('final')
            structure, result = direct_result(response)
        else:
            structure = structured_from_parser(records) if route == 'parser' else response_object(raw)
            result = solve(records, structure)
    except (ValueError, TypeError, KeyError) as error:
        return {'status': 'invalid', 'error': str(error), 'correct_grounded': False, 'final': explicit_final,
                'unfounded_unique': ref['result']['final'] == 'U' and explicit_final in ('Y', 'N')}

    correct_edges = {key: structure[key] == ref['structure'][key] for key in ('exception', 'grant')}
    worlds = {}
    for slot in SLOTS:
        got, want = result['worlds'][slot], ref['result']['worlds'][slot]
        worlds[slot] = {key: got[key] == want[key] for key in ('applies', 'rule', 'answer')}
        worlds[slot]['evidence'] = set(got['evidence']) == set(want['evidence'])
    final = result['final']
    correct = final == ref['result']['final'] and all(correct_edges.values())
    correct = correct and all(all(bits.values()) for bits in worlds.values())
    return {'status': 'unresolved' if final == 'X' else 'answered', 'structure': structure, 'result': result,
            'structure_correct': correct_edges, 'world_correct': worlds, 'correct_grounded': correct, 'final': final,
            'unfounded_unique': ref['result']['final'] == 'U' and final in ('Y', 'N')}


def summarize(rows, groups, refs):
    roots = {}
    for root, ids in groups.items():
        def correct(wording, direction):
            return rows[ids[wording, direction]]['correct_grounded']

        def finals(keys):
            values = [rows[ids[key]]['final'] for key in keys]
            return values if all(v in ('Y', 'N', 'U') for v in values) else None

        wording_finals = [finals([(w, d) for w in (1, 2)]) for d in ('match', 'reverse')]
        direction_finals = [finals([(w, d) for d in ('match', 'reverse')]) for w in (1, 2)]
        roots[root] = {
            'family': refs[ids[1, 'match']]['family'],
            'wording_pairs': [all(correct(w, d) for w in (1, 2)) for d in ('match', 'reverse')],
            'direction_pairs': [all(correct(w, d) for d in ('match', 'reverse')) for w in (1, 2)],
            'wording_changed_answer': [None if v is None else v[0] != v[1] for v in wording_finals],
            'direction_expected_transition': [None if v is None else v == [refs[ids[w, 'match']]['result']['final'], 'U']
                                              for w, v in enumerate(direction_finals, 1)],
            'all_correct_grounded': all(rows[i]['correct_grounded'] for i in ids.values()),
        }
    return {'roots': roots, 'correct_grounded': sum(row['correct_grounded'] for row in rows.values()),
            'invalid': [i for i, row in rows.items() if row['status'] == 'invalid'],
            'unresolved': [i for i, row in rows.items() if row['status'] == 'unresolved'],
            'unfounded_unique': [i for i, row in rows.items() if row['unfounded_unique']]}


def compare(summary, baseline, policy):
    changed = {k: int(row['all_correct_grounded']) - int(baseline['roots'][k]['all_correct_grounded'])
               for k, row in summary['roots'].items()}
    wins = [k for k, delta in changed.items() if delta == 1]
    losses = [k for k, delta in changed.items() if delta == -1]
    families = {summary['roots'][k]['family'] for k in wins}
    new_risk = sorted(set(summary['unfounded_unique']) - set(baseline['unfounded_unique']))
    enough = len(wins) - len(losses) >= policy['minimum_net_root_gain']
    if policy['require_win_in_each_heldout_wording_family']:
        enough = enough and len(families) == policy['heldout_wording_families']
    safe_enough = len(new_risk) <= policy['maximum_new_unfounded_unique']
    decision = 'continue_candidate' if enough and safe_enough else 'no_expansion_signal'
    if policy['technical_failure_blocks_go'] and (summary['invalid'] or baseline['invalid']):
        decision = 'technical_inconclusive'
    return {'wins': wins, 'losses': losses, 'winning_families': sorted(families),
            'new_unfounded_unique': new_risk, 'decision': decision}


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('action', choices=('verify', 'prompts', 'score'))
    cli.add_argument('--split', choices=('dev', 'heldout'), default='dev')
    cli.add_argument('--responses', type=Path)
    args = cli.parse_args()
    policy, instructions, dev, dev_ref, held, held_ref, groups = load_packet()
    if args.action == 'verify':
        output = {'development_versions': len(dev), 'heldout_versions': len(held), 'heldout_roots': len(groups),
                  'reference_replay': 'passed'}
    elif args.action == 'prompts':
        cases = dev if args.split == 'dev' else held
        output = {i: {route: prompt(row, instructions, route) for route in ROUTES} for i, row in sorted(cases.items())}
    else:
        if args.responses is None:
            cli.error('score requires --responses with both complete held-out routes')
        raw = read(args.responses)
        require(set(raw) == set(ROUTES), 'response file must contain direct and extract')
        for route in ROUTES:
            require(raw[route].keys() == held.keys() and all(isinstance(s, str) for s in raw[route].values()),
                    f'incomplete or invalid held-out responses for {route}')
        routes = {route: {i: judge(row, held_ref[i], route, raw.get(route, {}).get(i)) for i, row in held.items()}
                  for route in ('parser', *ROUTES)}
        summary = {route: summarize(rows, groups, held_ref) for route, rows in routes.items()}
        output = {'rows': routes, 'summary': summary,
                  'comparison': {r: compare(summary[r], summary['parser'], policy) for r in ROUTES}}
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
