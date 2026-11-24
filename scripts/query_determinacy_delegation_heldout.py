"""Run and replay the preregistered CPU delegation comparison."""
import argparse
from collections import Counter
from pathlib import Path
from time import monotonic

import query_determinacy_delegation_collect as cpu
import query_determinacy_delegation_paired as paired
import query_determinacy_shared_live as local
from query_determinacy_delegation import RECORDS, SLOTS, response_object, solve, validate_structure
from query_determinacy_delegation_source import compare_grant, source_structure

ROOT = paired.ROOT
PACK = ROOT / 'docs/review/2026-11-24-delegation-heldout-v2'
MATERIAL = PACK.parent / '2026-11-24-delegation-heldout-v1'
PRIOR = PACK.parent / '2026-11-23-delegation-new-wording-v1'
RUNS = ROOT / 'runs'
ARMS = ('program', 'direct', 'full', 'repair', 'full_checked')
FIELDS = ('exception', 'grant')
SOURCES = {'exception': 'R3', 'grant': 'F1'}
require = paired.require
read = paired.read
write = cpu.write
digest = cpu.digest


def frozen(split):
    lock = PACK / 'development-freeze.json'
    paired.verify_hashes(lock)
    binds = {'development_freeze_sha256': digest(lock)}
    if split == 'heldout':
        material = PACK / 'material-freeze.json'
        paired.verify_hashes(material)
        require(read(material)[str(lock.relative_to(ROOT))] == digest(lock), 'missing development binding')
        binds['material_freeze_sha256'] = digest(material)
        cases = read(MATERIAL / 'cases.json')
    else:
        old_cases = read(PRIOR / 'cases.json')
        cases = {key: old_cases[key] for key in read(PACK / 'protocol.json')['dev_cases']}
    return cases, read(PACK / 'protocol.json'), binds


def tasks(cases, protocol):
    instructions = protocol['prompts']
    plan = {'direct': [], 'extract': [], 'repair': []}
    for key, records in sorted(cases.items()):
        base = source_structure(records)
        missing = [field for field in FIELDS if base[field] is None]
        common = [instructions['common'], *(f'[{name}] {records[name]}' for name in RECORDS), instructions['fields']]
        for arm, route, request, fields in (
            ('direct', 'direct', 'direct', list(FIELDS)),
            ('extract', 'extract', 'both', list(FIELDS)),
            *((('repair', 'extract', missing[0], missing),) if len(missing) == 1 else ()),
        ):
            plan[arm].append({'case': key, 'arm': arm, 'route': route, 'fields': fields,
                              'prompt': '\n'.join([*common, instructions[request]])})
    return [(arm, rows[i:i + cpu.BATCH_SIZE]) for arm, rows in plan.items()
            for i in range(0, len(rows), cpu.BATCH_SIZE)]


def parse_fields(value, fields, records):
    require(isinstance(value, dict) and set(value) == set(fields), 'unexpected field keys')
    validate_structure(dict.fromkeys(FIELDS) | value)
    for field, obj in value.items():
        if obj is None:
            continue
        parties = (obj['grantor'], obj['recipient'])
        require(parties[0] != parties[1] and all(f'「{role}」' in records[SOURCES[field]] for role in parties),
                'non-source or duplicate role name')
    return value


def parse_direct(value, records):
    require(isinstance(value, dict) and set(value) == {'structure', 'worlds', 'final'}, 'invalid direct keys')
    parse_fields(value['structure'], FIELDS, records)
    worlds = value['worlds']
    require(isinstance(worlds, dict) and set(worlds) == set(SLOTS), 'invalid source keys')
    normalized = {}
    for slot, row in worlds.items():
        require(isinstance(row, dict) and 'applies' in row, 'invalid world object')
        applies = row['applies']
        if type(applies) is str and applies in ('true', 'false'):
            applies = applies == 'true'
        normalized[slot] = row | {'applies': applies}
    return paired.direct_result(value | {'worlds': normalized})


def assess(got, result, ref):
    return {'structure': got, 'result': result, 'final': result['final'], 'invalid': None,
            'strict': got == ref['structure'] and result['final'] == ref['result']['final']
            and all(
                all(result['worlds'][slot][field] == ref['result']['worlds'][slot][field]
                    for field in ('applies', 'rule', 'answer'))
                and set(result['worlds'][slot]['evidence']) == set(ref['result']['worlds'][slot]['evidence'])
                for slot in SLOTS)}


def score_call(row, records, ref, base=None):
    explicit_final = None
    try:
        raw = response_object(row['output'])
        if row['arm'] == 'direct' and isinstance(raw, dict) and raw.get('final') in ('Y', 'N', 'U', 'X'):
            explicit_final = raw['final']
        require(row['status'] == 'complete', row['status'])
        if row['arm'] == 'direct':
            got, result = parse_direct(raw, records)
        else:
            got = (base or {}) | parse_fields(raw, row['fields'], records)
            result = solve(records, got)
        scored = assess(got, result, ref)
    except (KeyError, TypeError, ValueError) as error:
        scored = {'structure': None, 'result': None, 'final': explicit_final, 'invalid': str(error), 'strict': False}
    return scored | {'calls': 1, 'input_tokens': len(row['input_token_ids']),
                     'output_tokens': len(row['generated_token_ids'])}


def wrap(scored, expected):
    return scored | {'false_unique': expected in ('U', 'X') and scored['final'] in ('Y', 'N'),
                     'clear_unresolved': scored['invalid'] is None and expected != 'X' and scored['final'] == 'X',
                     'correct_x': scored['invalid'] is None and expected == scored['final'] == 'X'}


def score_case(key, records, ref, calls):
    base = source_structure(records)
    static = assess(base, solve(records, base), ref) | {'calls': 0, 'input_tokens': 0, 'output_tokens': 0}
    direct = score_call(calls['direct', key], records, ref)
    full = score_call(calls['extract', key], records, ref)
    missing = sum(v is None for v in base.values())
    if missing == 1:
        repair = score_call(calls['repair', key], records, ref, base)
    else:
        repair = full if missing == 2 else static
    checked = full
    state = 'invalid_extraction'
    if full['structure'] is not None:
        state = compare_grant(base['grant'], full['structure']['grant'])
        if state in ('roles_reversed', 'different_roles'):
            got = full['structure'] | {'grant': None}
            checked = full | assess(got, solve(records, got), ref)
    expected = ref['result']['final']
    return {'root': ref['root'], 'group': ref.get('group', 'dev'), 'family': ref.get('family', 'development'),
            'expected': expected, 'missing': [k for k, v in base.items() if v is None], 'f1_verification': state,
            'actual_f1_reversed': full['structure'] is not None and ref['structure']['grant'] is not None
            and compare_grant(ref['structure']['grant'], full['structure']['grant']) == 'roles_reversed',
            'arms': {arm: wrap(value, expected) for arm, value in
                     zip(ARMS, (static, direct, full, repair, checked), strict=True)}}


def totals(values):
    return {'n': len(values), 'strict': sum(r['strict'] for r in values),
            'false_unique': sum(r['false_unique'] for r in values),
            'clear_unresolved': sum(r['clear_unresolved'] for r in values),
            'correct_x': sum(r['correct_x'] for r in values),
            'invalid': sum(r['invalid'] is not None for r in values),
            **{k: sum(r[k] for r in values) for k in ('calls', 'input_tokens', 'output_tokens')}}


def summarize(rows):
    by_group = {group: {arm: totals([row['arms'][arm] for row in rows.values()
                                    if group == 'all' or row['group'] == group]) for arm in ARMS}
                for group in ('all', *sorted({row['group'] for row in rows.values()}))}
    by_root = {}
    by_family = {}
    for root in sorted({r['root'] for r in rows.values()}):
        cluster = [row for row in rows.values() if row['root'] == root]
        labels = cluster[0]
        by_root[root] = {'group': labels['group'], 'family': labels['family'],
                         **{arm: totals([row['arms'][arm] for row in cluster]) for arm in ARMS}}
    for family in sorted({r['family'] for r in rows.values()}):
        by_family[family] = {arm: totals([row['arms'][arm] for row in rows.values()
                                         if row['family'] == family]) for arm in ARMS}
    transitions = []
    for case, row in rows.items():
        before, after = (row['arms'][arm] for arm in ('full', 'full_checked'))
        if before['final'] != after['final'] or before['strict'] != after['strict']:
            transitions.append({'case': case, 'verification': row['f1_verification'],
                                'before': before['final'], 'after': after['final'],
                                'blocked_false_unique': before['false_unique'] and not after['false_unique'],
                                'lost_strict': before['strict'] and not after['strict'],
                                'recovered_strict': after['strict'] and not before['strict']})
    return {'groups': by_group, 'roots': by_root, 'families': by_family, 'verification_transitions': transitions,
            'f1_status_counts': dict(Counter(row['f1_verification'] for row in rows.values()))}


def decision(rows, summary, policy):
    roots = {k: v for k, v in summary['roots'].items() if v['group'] == 'novel'}
    comparisons = {}
    for arm in ('direct', 'full', 'repair', 'full_checked'):
        deltas = {k: int(v[arm]['strict'] == v[arm]['n']) - int(v['program']['strict'] == v['program']['n'])
                  for k, v in roots.items()}
        net = sum(deltas.values())
        wo_one = [net - change for change in deltas.values()]
        added = [k for k, r in rows.items() if r['arms'][arm]['false_unique'] and not r['arms']['program']['false_unique']]
        comparisons[arm] = {'net_complete_novel_roots': net, 'root_changes': deltas,
                            'leave_one_novel_root_out_net_range': [min(wo_one), max(wo_one)],
                            'winning_families': sorted({roots[k]['family'] for k, v in deltas.items() if v > 0}),
                            'added_false_unique_all_cases': added}
    repair = comparisons['repair']
    a, b = (summary['groups']['mixed'][arm] for arm in ('repair', 'full'))
    mixed_advantage = (a['strict'] >= b['strict'] and all(not r['arms']['repair']['false_unique']
                       or r['arms']['full']['false_unique'] for r in rows.values() if r['group'] == 'mixed')
                       and a['input_tokens'] + a['output_tokens'] < b['input_tokens'] + b['output_tokens'])
    all_gain = summary['groups']['all']['repair']['strict'] > summary['groups']['all']['full']['strict']
    safe_vs_full = all(not r['arms']['repair']['false_unique'] or r['arms']['full']['false_unique'] for r in rows.values())
    recurs = [r for r in rows.values() if r['actual_f1_reversed'] and r['f1_verification'] == 'roles_reversed'
              and r['arms']['full']['false_unique'] and not r['arms']['full_checked']['false_unique']
              and r['structure_ref_exception_matches_full']]
    enough = (repair['net_complete_novel_roots'] >= policy['novel_net_complete_roots_over_program']
              and len(repair['winning_families']) >= policy['novel_positive_families']
              and len(repair['added_false_unique_all_cases']) <= policy['new_false_unique_vs_program'])
    return {'comparisons_to_frozen_program': comparisons, 'repair_novel_benefit_and_risk_criterion': enough,
            'repair_mixed_cost_advantage': mixed_advantage, 'repair_coverage_advantage_over_full': all_gain and safe_vs_full,
            'safe_for_method_manuscript_in_this_diagnostic': enough and (mixed_advantage or (all_gain and safe_vs_full)),
            'verified_reversal_recurrence': len({r['root'] for r in recurs}) >= 2
            and len({r['family'] for r in recurs}) >= 2,
            'causal_verified_reversal_roots': sorted({r['root'] for r in recurs})}


def collect(split, run, dev):
    cases, protocol, binds = frozen(split)
    plan = tasks(cases, protocol)
    environment = local.environment_snapshot()
    if split == 'heldout':
        report = score('dev', dev)
        require(report['interface_ready'], 'development interface is not ready')
        require(report['environment'] == environment, 'model/runtime changed since development')
        binds['dev_seal_sha256'] = report['seal_sha256']
    run.mkdir(mode=0o700)
    started = monotonic()
    write(run / 'manifest.json', {'split': split, 'generation': cpu.GENERATION,
                                  'environment': environment, 'binds': binds})
    backend = cpu.CpuBackend(environment)
    done = 0
    call_count = sum(len(batch) for _, batch in plan)
    for index, (arm, batch) in enumerate(plan):
        write(run / f'{index:03d}.attempt.json', batch)
        records, seconds = backend.generate(batch)
        require(len(batch) == len(records), 'bad batch count')
        write(run / f'{index:03d}.record.json', {'records': records, 'seconds': seconds})
        done += len(batch)
        print(f'{done}/{call_count} {arm} {"/".join(r["status"] for r in records)} {seconds:.1f}s', flush=True)
    write(run / 'time.json', {'wall_seconds_after_environment_check': monotonic() - started})
    write(run / 'seal.json', {path.name: digest(path) for path in sorted(run.iterdir()) if path.is_file()})


def replay(split, run):
    cases, protocol, binds = frozen(split)
    plan = tasks(cases, protocol)
    seal = read(run / 'seal.json')
    expected = {'manifest.json', 'time.json', *(f'{i:03d}.{kind}.json' for i in range(len(plan))
                                               for kind in ('attempt', 'record'))}
    require(set(seal) == expected == {p.name for p in run.iterdir() if p.name != 'seal.json'}, 'unexpected run files')
    for filename, expected_digest in seal.items():
        require(digest(run / filename) == expected_digest, f'sealed file changed: {filename}')
    manifest = read(run / 'manifest.json')
    require(manifest['split'] == split and manifest['generation'] == cpu.GENERATION, 'manifest mismatch')
    require(set(manifest['binds']) == set(binds) | ({'dev_seal_sha256'} if split == 'heldout' else set())
            and all(manifest['binds'][k] == v for k, v in binds.items()), 'frozen bindings changed')
    eos = manifest['environment']['eos_token_ids']
    tokenizer = local.load_tokenizer()
    records = {}
    seconds = Counter()
    for index, (arm, batch) in enumerate(plan):
        require(batch == read(run / f'{index:03d}.attempt.json'), 'different scheduled prompts')
        saved = read(run / f'{index:03d}.record.json')
        seconds[arm] += saved['seconds']
        for task, row in zip(batch, saved['records'], strict=True):
            require(all(row[k] == v for k, v in task.items()), 'different generation target')
            rendered, ids = local.tokenize(tokenizer, task['prompt'])
            require(row['rendered_prompt'] == rendered and row['input_token_ids'] == ids, 'different prompt tokens')
            tokens = row['generated_token_ids']
            limit = cpu.LIMITS[task['route']]
            require(0 < len(tokens) <= limit and all(type(t) is int and 0 <= t < len(tokenizer) for t in tokens)
                    and not any(t in eos for t in tokens[:-1]) and (tokens[-1] in eos or len(tokens) == limit),
                    'invalid output length or EOS')
            raw = tokenizer.decode(tokens, skip_special_tokens=True)
            require(row['output'] == raw and row['status'] == local.output_status(raw, tokens, eos),
                    'different decoded output')
            records[arm, task['case']] = row
    return cases, protocol, manifest, records, dict(seconds)


def score(split, run):
    cases, protocol, manifest, records, seconds = replay(split, run)
    refs = read(PRIOR / 'author-reference.json' if split == 'dev' else MATERIAL / 'author-reference.json')
    rows = {}
    for key, case in cases.items():
        ref = refs[key]
        row = score_case(key, case, ref, records)
        full = row['arms']['full']['structure']
        row['structure_ref_exception_matches_full'] = full is not None and full['exception'] == ref['structure']['exception']
        rows[key] = row
    summary = summarize(rows)
    report = {'seal_sha256': digest(run / 'seal.json'), 'environment': manifest['environment'],
              'dev_seal_sha256': manifest['binds'].get('dev_seal_sha256'),
              'physical_calls': len(records), 'generation_statuses': dict(Counter(r['status'] for r in records.values())),
              'batch_generation_seconds': seconds, 'time': read(run / 'time.json'),
              'summary': summary, 'rows': rows}
    if split == 'dev':
        report['interface_ready'] = all(r['status'] == 'complete' for r in records.values()) and all(
            summary['groups']['all'][arm]['invalid'] <= 1 for arm in ('direct', 'full', 'repair'))
    else:
        report['decision'] = decision(rows, summary, protocol['decision'])
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('stage', choices=('collect', 'score'))
    cli.add_argument('split', choices=('dev', 'heldout'))
    cli.add_argument('run', type=Path)
    cli.add_argument('--dev', type=Path)
    cli.add_argument('--report', type=Path)
    args = cli.parse_args()
    if args.stage == 'collect':
        require(args.run.parent.resolve() == RUNS and (args.split != 'heldout' or args.dev is not None),
                'use a new local run directory and sealed dev run')
        collect(args.split, args.run, args.dev)
    else:
        report = score(args.split, args.run)
        if args.report:
            write(args.report, report)
        print({k: v for k, v in report.items() if k in
               ('physical_calls', 'generation_statuses', 'batch_generation_seconds', 'interface_ready', 'decision')})


if __name__ == '__main__':
    main()
