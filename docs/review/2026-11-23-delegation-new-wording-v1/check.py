"""Replay the pinned CPU parser on presealed new wording and boundary cases."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))


def read(name):
    return json.loads((HERE / name).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_files(directory, hashes):
    for name, digest in hashes.items():
        require(sha256((directory / name).read_bytes()).hexdigest() == digest, f'changed file: {name}')


def verify_design(cases, references, design, record_names):
    require(set(cases) == set(references), 'public and reference keys differ')
    require(all(set(row) == set(record_names) and all(row.values()) for row in cases.values()), 'invalid record slots')
    wanted = set(design['boundary_controls'])
    for root, changed in design['roots'].items():
        for direction in design['directions']:
            a, b = (f'{root}-{i}-{direction}' for i in (1, 2))
            wanted.update((a, b))
            require({k for k in cases[a] if cases[a][k] != cases[b][k]} == set(changed), 'wrong edit scope')
            first, second = references[a], references[b]
            require([first['wording'], second['wording']] == design['wordings'], 'wrong wording group')
            require(all(item['root'] == root and item['direction'] == direction for item in (first, second)),
                    'root or role metadata differs')
            require(all(first[k] == second[k] for k in ('structure', 'result')), 'paraphrase changes reference')
        for wording in (1, 2):
            a, b = (f'{root}-{wording}-{d}' for d in ('match', 'reverse'))
            require({k for k in cases[a] if cases[a][k] != cases[b][k]} == {'F1'}, 'role swap changes other records')
            grant, flipped = (references[i]['structure']['grant'] for i in (a, b))
            a1, a2 = grant['grantor'], grant['recipient']
            raw = cases[a]['F1']
            require(raw.count(a1) == 1 and raw.count(a2) == 1, 'ambiguous author role spans')
            swapped = raw.replace(a1, '\0').replace(a2, a1).replace('\0', a2)
            require(flipped == {'grantor': a2, 'recipient': a1} and swapped == cases[b]['F1'], 'incorrect role swap')
            require(references[a]['result']['final'] in ('Y', 'N') and references[b]['result']['final'] == 'U',
                    'role swap does not change uniqueness')
    for name in design['boundary_controls']:
        ref = references[name]
        require(ref['control'] == name and ref['structure'][ref['unknown_field']] is None
                and ref['result']['final'] == 'X', 'boundary reference must be unresolved')
    require(set(cases) == wanted, 'unexpected material')


def equal_grounded(observed, expected):
    if observed['final'] != expected['final']:
        return False
    for slot, ref in expected['worlds'].items():
        row = observed['worlds'][slot]
        if any(row[k] != ref[k] for k in ('applies', 'rule', 'answer')) or set(row['evidence']) != set(ref['evidence']):
            return False
    return True


def replay():
    seal = read('material-seal.json')
    verify_files(HERE, seal['sha256'])
    source = read('source-freeze.json')
    verify_files(ROOT, source['source_sha256'])
    from query_determinacy_delegation import RECORDS, solve
    from query_determinacy_delegation_source import solve_from_sources, source_structure

    cases, refs = read('cases.json'), read('author-reference.json')
    design = source['design']
    verify_design(cases, refs, design, RECORDS)

    rows = {}
    for name, records in cases.items():
        if 'control' not in refs[name]:
            ref = refs[name]
            require(equal_grounded(solve(records, ref['structure']), ref['result']), 'incoherent author reference')
        parsed = source_structure(records)
        output = solve_from_sources(records)
        target = refs[name]['result']
        control = 'control' in refs[name]
        rows[name] = {'group': 'boundary' if control else refs[name]['wording'], 'parsed': parsed, 'result': output,
                      'expected_final': target['final'],
                      'strict_grounded': None if control else parsed == refs[name]['structure']
                      and equal_grounded(output, target),
                      'world_answer_match': {w: v['answer'] == target['worlds'][w]['answer']
                                             for w, v in output['worlds'].items()},
                      'false_unique': target['final'] in ('U', 'X') and output['final'] in ('Y', 'N')}

    group_summary = {}
    for group in (*design['wordings'], 'boundary'):
        group_rows = [r for r in rows.values() if r['group'] == group]
        blocked = [r for r in group_rows if r['expected_final'] != 'X' and r['result']['final'] == 'X']
        group_summary[group] = {'versions': len(group_rows),
                                'strict_grounded': sum(r['strict_grounded'] is True for r in group_rows),
                                'unresolved': sum(r['result']['final'] == 'X' for r in group_rows),
                                'false_unique': sum(r['false_unique'] for r in group_rows),
                                'clear_but_unresolved': len(blocked),
                                'missing_on_clear_unresolved': dict(Counter(
                                    '+'.join(k for k, field in (('F1', 'grant'), ('R3', 'exception'))
                                             if row['parsed'][field] is None) or 'neither' for row in blocked))}
    paired = {root: {wording: all(rows[f'{root}-{i}-{d}']['strict_grounded'] for d in design['directions'])
                     for i, wording in enumerate(design['wordings'], 1)} for root in design['roots']}
    return {'source_commit': source['snapshot_commit'], 'material_seal_sha256': sha256(
                (HERE / 'material-seal.json').read_bytes()).hexdigest(),
            'groups': group_summary, 'direction_pairs': paired, 'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    result = replay()
    if args.verify:
        require(result == read('results.json'), 'saved replay differs')
        print(f"Verified {len(result['rows'])} cases against their frozen CPU replay.")
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
