"""Run a paired date-resolution pilot with an unchanged evidence-first extractor."""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

import query_determinacy_date_evidence_first as frozen


pilot = frozen.pilot
local = frozen.local
require = frozen.require
PACK = local.ROOT / 'docs/review/2026-11-25-date-multi-rule-pilot-v1'
DIRECT_BATCH = 10
DIRECT_SYSTEM = ('Use only the supplied evidence and facts. Work out which rule applies on each possible date. '
                 'Use exact comparisons, including what happens at equality. Provide a decision that is supported '
                 'even if the actual date is unstated. Do not assume unstated facts.')
DIRECT = ('If scope is contradicted or cannot be established, use UNRESOLVED with reason rule_outside_scope '
          'or scope_not_established respectively. Otherwise, evaluate each still-possible date separately. '
          'With a stated date, evaluate only that date. Compare the case amount with the cutoff for the date '
          'you are evaluating. Give ANSWER_Y or ANSWER_N if the applicable conclusions '
          'agree. If they differ and the date is unstated, use ASK_DATE and ask for the event date. For each '
          'evaluated date cite the comparison, only the applicable dated version, scope and F1 facts by ID. '
          'Return one compact JSON object. Use keys action, branches, ask, reason. Each branch is a list of '
          'three values: the ISO date, Y or N, and a list of evidence IDs. Use an empty branches list when '
          'unresolved. For ASK_DATE set ask to the name of the event whose date is needed, for example "delivery". '
          'Set ask to null for other actions. Set reason to null unless unresolved.')
TAGS = ('ANSWER_Y', 'ANSWER_N', 'ASK_DATE', 'UNRESOLVED')
ABLATION = {'gift-S0', 'gift-D0', 'checks-S0', 'checks-D0'}


def materials():
    rules = pilot.read(PACK / 'rules.json')
    public = {'profiles': {}, 'cases': []}
    reference = {'profiles': {}, 'cases': {}}
    for rule in rules:
        name = rule['id']
        new_day = date.fromisoformat(rule['effective'])
        days = [(new_day - timedelta(days=1)).isoformat(), new_day.isoformat()]
        rule_id, scope_id, *version_ids = rule['labels']
        require(set(rule['labels']) == {'E1', 'E2', 'E3', 'E4'}, 'expected four distinct source labels')
        versions = [[day, day, amount, source] for day, amount, source in zip(days, rule['limits'], version_ids, strict=True)]
        evidence = {rule_id: rule['rule'], scope_id: rule['scope']}
        for first, last, amount, source in versions:
            evidence[source] = (f'For the study window only, coverage from {first} through {last}. '
                                f'The threshold for this version is ${amount:,}.')
        claims = [{'quote': quote, 'statement': statement} for quote, statement in rule['claims']]
        require(all(entry['quote'] in evidence[scope_id] for entry in claims), 'scope claim has no matching anchor')
        public['profiles'][name] = {'question': rule['question'], 'evidence': evidence,
                                    'scope_claims': {'source': scope_id, 'claims': claims}}
        reference['profiles'][name] = {'rule': [rule['comparison'], rule['event'], rule_id], 'versions': versions}

        def add(case_id, amount, answers, actual, scope=True, first_fact=None):
            known = days[actual] if actual is not None else None
            fact = rule['facts'].format(amount=f'${amount:,}')
            if first_fact is not None:
                fact = f'{first_fact.rstrip(".")}. {fact.split(". ", 1)[1]}'
            fact += f' The only possible {rule["event"]} dates are {days[0]} and {days[1]}.'
            if known:
                fact += f' The {rule["event"]} took place on {known}.'
            public['cases'].append({'id': case_id, 'profile': name, 'facts': fact})
            fields = {'scope': scope, 'scope_evidence': sorted([scope_id, 'F1']), 'amount': amount,
                      'range': days, 'date': known, 'fact_evidence': 'F1'}
            ask = None
            if scope is not True:
                category = 'scope_outside' if scope is False else 'scope_unknown'
                outcome = {'tag': 'UNRESOLVED', 'branches': [], 'ask_event': None,
                           'reason': 'rule_outside_scope' if scope is False else 'scope_not_established'}
            else:
                selected = range(2) if actual is None else (actual,)
                branches = [[days[i], answers[i], sorted([rule_id, scope_id, version_ids[i], 'F1'])] for i in selected]
                if actual is not None:
                    category = 'dated'
                elif answers[0] == answers[1]:
                    category = 'same_missing'
                else:
                    category, ask = 'varying_missing', rule['event']
                outcome = {'tag': 'ASK_DATE' if ask else 'ANSWER_Y' if branches[0][1] else 'ANSWER_N',
                           'branches': branches, 'ask_event': ask}
            reference['cases'][case_id] = {'category': category, 'fields': fields, 'outcome': outcome}

        require(rule['cases'][0][1][0] == rule['cases'][0][1][1] and
                rule['cases'][1][1][0] != rule['cases'][1][1][1], 'same and varying controls differ')
        for (amount, answers), prefix in zip(rule['cases'], ('S', 'D'), strict=True):
            for suffix, actual in enumerate((None, 0, 1)):
                add(f'{name}-{prefix}{suffix}', amount, answers, actual)
        if 'controls' in rule:
            amount, answers = rule['cases'][0]
            for suffix, scope, fact in zip(('N', 'U'), (False, None), rule['controls'], strict=True):
                add(f'{name}-{suffix}', amount, answers, None, scope, fact)
    return public, reference


def direct_plan(public, include_ablation=True):
    tasks = []
    modes = ('direct', 'without_scope_annotations') if include_ablation else ('direct',)
    for mode in modes:
        for case in public['cases']:
            if mode != 'direct' and case['id'] not in ABLATION:
                continue
            profile = public['profiles'][case['profile']]
            chunks = [f'[{key}] {source}' for key, source in sorted(profile['evidence'].items())]
            if mode == 'direct':
                annotated = profile['scope_claims']
                chunks.append('Scope conditions supplied by the evidence packet:')
                chunks.extend(f'- [{annotated["source"]}] {claim["statement"]} (anchor: {claim["quote"]})'
                              for claim in annotated['claims'])
            chunks.extend([f'[F1] {case["facts"]}', profile['question'], DIRECT])
            tasks.append({'case': case['id'], 'route': mode, 'messages': [pilot.message('system', DIRECT_SYSTEM),
                                                                          pilot.message('user', '\n\n'.join(chunks))]})
    return tasks


def used_files():
    return (Path(__file__), PACK / 'rules.json', PACK / 'public.json', PACK / 'reference.json',
            PACK / 'protocol.md', PACK / 'sources.md', frozen.PACK / 'freeze.json')


def fingerprints():
    return {str(path.relative_to(local.ROOT)): local.hash_file(path) for path in used_files()}


def parse_direct(text):
    candidate = text.strip()
    fence = re.fullmatch(r'```(?:json)?\s*\n(.*?)\n?```', candidate, re.S | re.I)
    data = json.loads(fence[1] if fence else candidate)
    require(isinstance(data, dict) and data.get('action') in TAGS and isinstance(data.get('branches'), list),
            'action or branch list missing')
    branches = []
    for branch in data['branches']:
        require(isinstance(branch, list) and len(branch) == 3, 'branch must have date, label and evidence')
        day, answer, evidence = branch
        require(isinstance(day, str) and date.fromisoformat(day).isoformat() == day and answer in ('Y', 'N'),
                'invalid dated branch')
        if isinstance(evidence, str):
            evidence = [item.strip() for item in evidence.split(',')]
        require(isinstance(evidence, list) and all(isinstance(item, str) for item in evidence)
                and set(evidence) <= {'E1', 'E2', 'E3', 'E4', 'F1'} and len(set(evidence)) == len(evidence),
                'invalid branch evidence')
        branches.append([day, answer == 'Y', sorted(evidence)])
    require(len({branch[0] for branch in branches}) == len(branches), 'duplicate branch date')
    outcome = {'tag': data['action'], 'ask_event': data.get('ask'), 'branches': sorted(branches)}
    if data['action'] == 'UNRESOLVED' or data.get('reason') is not None:
        outcome['reason'] = data.get('reason')
    return outcome


def gold_picks(public, reference):
    locations = {}
    picks = {}
    for name, profile in reference['profiles'].items():
        comparison, _, rule_id = profile['rule']
        earlier, later = [version[3] for version in profile['versions']]
        locations[name] = {'rule': rule_id, 'scope': public['profiles'][name]['scope_claims']['source'],
                           'earlier': earlier, 'later': later}
        picks[f'{name}/comparison'] = comparison
    for case_id, row in reference['cases'].items():
        picks[f'{case_id}/scope'] = {True: 'yes', False: 'no', None: 'unknown'}[row['fields']['scope']]
    return locations, picks


def preflight(public, reference):
    frozen.verify_freeze()
    require((public, reference) == materials(), 'published material differs from verified sources')
    require(len(public['profiles']) == 6 and len(public['cases']) == 40, 'unexpected rule or case count')
    locations, picks = gold_picks(public, reference)
    rows = frozen.judge(public, reference, locations, picks)
    require(all(row['checks']['strict'] for row in rows.values()), 'manual reference failed program replay')
    for row in rows.values():
        gold = row['expected']
        text = json.dumps({'action': gold['tag'], 'ask': gold['ask_event'], 'reason': gold.get('reason'),
                           'branches': [[day, 'Y' if answer else 'N', ids] for day, answer, ids in gold['branches']]})
        require(parse_direct(text) == gold, 'strong direct interface cannot express the reference')
    controls = frozen.judge(public, reference, locations, picks | {
        f'{name}/comparison': '<=' if row['rule'][0] == '>' else '>' for name, row in reference['profiles'].items()})
    require(all(not row['checks']['strict'] for row in controls.values()), 'wrong comparator passed field checks')
    require(all(not row['checks']['branches'] for case_id, row in controls.items()
                if not reference['cases'][case_id]['category'].startswith('scope_')), 'wrong comparator passed branches')
    return rows


def package():
    public, reference = (pilot.read(PACK / f'{name}.json') for name in ('public', 'reference'))
    lock = pilot.read(PACK / 'freeze.json')
    require(lock['hashes'] == fingerprints(), 'frozen pilot materials or code changed')
    frozen.verify_freeze()
    return public, reference, lock


def batches(phase, plan):
    size = DIRECT_BATCH if phase == 'direct' else frozen.BATCH
    return [(f'{phase}-{index:02d}', plan[index:index + size]) for index in range(0, len(plan), size)]


def collect(run):
    public, _, lock = package()
    environment = local.environment_snapshot()
    require(environment == pilot.read(frozen.PACK / 'freeze.json')['environment'], 'CPU environment changed')
    run.mkdir(mode=0o700)
    pilot.write(run / 'manifest.json', {'hashes': lock['hashes'], 'freeze_sha256': local.hash_file(PACK / 'freeze.json'),
                                       'environment': environment, 'utc': datetime.now(timezone.utc).isoformat()})
    backend = frozen.ChoiceBackend(environment)

    def execute(phase, plan):
        all_rows = []
        for name, tasks in batches(phase, plan):
            pilot.write(run / f'{name}.attempt.json', tasks)
            if phase == 'direct':
                result = pilot.generate(backend, tasks)
            else:
                rows, seconds = backend.rank(tasks)
                result = {'records': rows, 'seconds': seconds}
            pilot.write(run / f'{name}.record.json', result)
            all_rows.extend(result['records'])
            statuses = Counter(row['status'] for row in result['records'] if 'status' in row)
            print(name, len(all_rows), len(plan), round(result['seconds'], 2), dict(statuses), flush=True)
        return all_rows

    located = frozen.selections(public, execute('locate', frozen.locate_plan(public)))
    extract, _ = frozen.extract_plan(public, located)
    execute('extract', extract)
    execute('direct', direct_plan(public))
    pilot.write(run / 'seal.json', {path.name: local.hash_file(path) for path in sorted(run.iterdir())})


def replay(run):
    public, reference, lock = package()
    manifest = pilot.read(run / 'manifest.json')
    require(manifest['hashes'] == lock['hashes'] and manifest['freeze_sha256'] == local.hash_file(PACK / 'freeze.json'),
            'collection binds different inputs')
    require(manifest['environment'] == pilot.read(frozen.PACK / 'freeze.json')['environment'], 'wrong model environment')
    seal = pilot.read(run / 'seal.json')
    require(set(seal) | {'seal.json'} == {path.name for path in run.iterdir()}, 'archive membership changed')
    require(all(local.hash_file(run / name) == sha for name, sha in seal.items()), 'archive bytes changed')
    tokenizer = local.load_tokenizer()
    costs, seen = {}, {'manifest.json'}

    def verify_phase(phase, plan):
        rows, seconds = [], 0.0
        for name, tasks in batches(phase, plan):
            attempt, record = f'{name}.attempt.json', f'{name}.record.json'
            seen.update((attempt, record))
            require(pilot.read(run / attempt) == tasks, 'attempt differs from frozen plan')
            batch = pilot.read(run / record)
            seconds += batch['seconds']
            for task, row in zip(tasks, batch['records'], strict=True):
                require(all(row[key] == value for key, value in task.items()), 'record does not match attempt')
                if phase == 'direct':
                    render, ids = pilot.render(tokenizer, task['messages'])
                    tokens, eos = row['generated_token_ids'], manifest['environment']['eos_token_ids']
                    require(render == row['rendered_prompt'] and 0 < len(tokens) <= pilot.LIMIT and
                            not any(token in eos for token in tokens[:-1]) and
                            (tokens[-1] in eos or len(tokens) == pilot.LIMIT), 'direct record or completion changed')
                    text = tokenizer.decode(tokens, skip_special_tokens=True)
                    require(text == row['output'] and row['status'] == local.output_status(text, tokens, eos),
                            'direct output differs from stored tokens')
                else:
                    ids = local.tokenize(tokenizer, task['prompt'])[1]
                    frozen.choice_scores(row)
                require(ids == row['input_token_ids'], 'input tokens changed')
                rows.append(row)
        costs[phase] = {'calls': len(rows), 'seconds': round(seconds, 2),
                        'input_tokens': sum(len(row['input_token_ids']) for row in rows),
                        'generated_tokens': sum(len(row.get('generated_token_ids', ())) for row in rows)}
        return rows

    located = frozen.selections(public, verify_phase('locate', frozen.locate_plan(public)))
    extract, groups = frozen.extract_plan(public, located)
    picked, conditions = frozen.extraction_picks(verify_phase('extract', extract), groups)
    direct = verify_phase('direct', direct_plan(public))
    require(seen == set(seal), 'unexpected archived batch')
    return make_result(public, reference, direct, located, picked, conditions, costs, local.hash_file(run / 'seal.json'))


def outcome_checks(outcome, final_tag, gold):
    got = {row[0]: row[1:] for row in (outcome or {}).get('branches', ())}
    dates = {day: {'conclusion': day in got and got[day][0] == answer,
                   'evidence': day in got and got[day][1] == evidence}
             for day, answer, evidence in gold['branches']}
    return {'strict': outcome == gold, 'action': final_tag == gold['tag'], 'dates': dates}


def direct_row(record, gold):
    text = record['output']
    outcome, error = None, None
    try:
        outcome = parse_direct(text)
    except (ValueError, TypeError) as exc:
        error = str(exc)
    tags = set(re.findall(r'"action"\s*:\s*"(ANSWER_Y|ANSWER_N|ASK_DATE|UNRESOLVED)"', text))
    tag = outcome['tag'] if outcome else next(iter(tags)) if len(tags) == 1 else None
    passed = outcome if record['status'] == 'complete' else None
    return {'outcome': outcome, 'tag': tag, 'generation_status': record['status'], 'parse_error': error,
            'output_sha256': local.sha(text.encode()), 'checks': outcome_checks(passed, tag, gold)}


def summarize(items):
    groups = Counter(category for category, _ in items)
    stats = {'cases': len(items), 'strict': 0, 'action': 0, 'by_category': {}}
    stats['wrong_unique_on_varying'] = [0, groups['varying_missing']]
    stats['unnecessary_ask_on_same'] = [0, groups['same_missing']]
    stats['dated_grounded'] = [0, groups['dated']]
    stats['scope_wrong_unique'] = [0, groups['scope_unknown'] + groups['scope_outside']]
    stats['dates'] = {'conclusion': 0, 'evidence': 0, 'joint': 0, 'total': 0}
    for category, row in items:
        checks, tag = row['checks'], row['tag']
        stats['strict'] += checks['strict']
        stats['action'] += checks['action']
        counts = stats['by_category'].setdefault(category, [0, groups[category]])
        counts[0] += checks['strict']
        if category == 'varying_missing':
            stats['wrong_unique_on_varying'][0] += tag in ('ANSWER_Y', 'ANSWER_N')
        if category == 'same_missing':
            stats['unnecessary_ask_on_same'][0] += tag == 'ASK_DATE'
        if category == 'dated':
            stats['dated_grounded'][0] += checks['strict']
        if category.startswith('scope_'):
            stats['scope_wrong_unique'][0] += tag in ('ANSWER_Y', 'ANSWER_N')
        for bits in checks['dates'].values():
            stats['dates']['conclusion'] += bits['conclusion']
            stats['dates']['evidence'] += bits['evidence']
            stats['dates']['joint'] += bits['conclusion'] and bits['evidence']
            stats['dates']['total'] += 1
    return stats


def make_result(public, reference, direct, located, picked, conditions, costs, digest):
    evidence = frozen.judge(public, reference, located, picked)
    manual_locations, manual_picks = gold_picks(public, reference)
    manual = frozen.judge(public, reference, manual_locations, manual_picks)
    cases = {case['id']: case for case in public['cases']}
    direct_rows = {(row['route'], row['case']): direct_row(row, reference['cases'][row['case']]['outcome'])
                   for row in direct}
    routes = ('direct', 'frozen', 'manual')
    paired, by_rule, ablation = {}, {}, {}
    for case_id, ref in reference['cases'].items():
        gold = ref['outcome']
        row = {'rule': cases[case_id]['profile'], 'category': ref['category'], 'reference': gold,
               'direct': direct_rows['direct', case_id]}
        for route, scored in (('frozen', evidence[case_id]), ('manual', manual[case_id])):
            tag = (scored['outcome'] or {}).get('tag')
            row[route] = {'tag': tag, 'outcome': scored['outcome'], 'error': scored['error'],
                          'fields': scored['fields'], 'field_checks': scored['field_checks'],
                          'checks': outcome_checks(scored['outcome'], tag, gold)}
        row['paired_strict'] = [row[route]['checks']['strict'] for route in ('direct', 'frozen')]
        paired[case_id] = row
        if case_id in ABLATION:
            ablation[case_id] = {'category': row['category'], 'with': row['direct'],
                                 'without': direct_rows['without_scope_annotations', case_id]}
    for rule in public['profiles']:
        subgroup = [row for row in paired.values() if row['rule'] == rule]
        by_rule[rule] = {route: summarize([(row['category'], row[route]) for row in subgroup]) for route in routes}
    totals = {route: summarize([(row['category'], row[route]) for row in paired.values()]) for route in routes}
    for route in routes:
        totals[route]['complete_core_rules'] = sum(all(row[route]['checks']['strict'] for row in paired.values()
            if row['rule'] == rule and not row['category'].startswith('scope_')) for rule in by_rule)
        totals[route]['complete_all_rules'] = sum(row[route]['strict'] == row[route]['cases'] for row in by_rule.values())
    pairs = Counter(('both' if direct_ok and frozen_ok else 'direct_only' if direct_ok else
                     'frozen_only' if frozen_ok else 'neither') for direct_ok, frozen_ok in
                    (row['paired_strict'] for row in paired.values()))
    return {'seal_sha256': digest, 'locations': located, 'scope_condition_picks': conditions, 'costs': costs,
            'totals': totals, 'by_rule': by_rule, 'paired_strict': dict(pairs), 'cases': paired, 'ablation': ablation}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('build', 'freeze', 'collect', 'archive', 'check-archive'))
    cli.add_argument('path', nargs='?', type=Path)
    args = cli.parse_args()
    if args.action == 'build':
        public, reference = materials()
        for name, data in (('public', public), ('reference', reference)):
            pilot.write(PACK / f'{name}.json', data)
    elif args.action == 'freeze':
        public, reference = (pilot.read(PACK / f'{name}.json') for name in ('public', 'reference'))
        preflight(public, reference)
        pilot.write(PACK / 'freeze.json', {'hashes': fingerprints(), 'utc': datetime.now(timezone.utc).isoformat()})
        print('All 40 author references replayed. Paired materials and scoring frozen.')
    elif args.action == 'collect':
        require(args.path is not None, 'run directory required')
        collect(args.path)
    elif args.action == 'archive':
        require(args.path is not None, 'run directory required')
        result = replay(args.path)
        with ZipFile(PACK / 'raw.zip', 'x', ZIP_DEFLATED) as zipped:
            for path in sorted(args.path.iterdir()):
                zipped.write(path, path.name)
        pilot.write(PACK / 'results.json', result)
        print(local.encode({'totals': result['totals'], 'costs': result['costs'],
                            'paired_strict': result['paired_strict']}).decode(), end='')
    else:
        with tempfile.TemporaryDirectory(prefix='kba-multi-date-replay-') as path:
            with ZipFile(PACK / 'raw.zip') as zipped:
                zipped.extractall(path)
            result = replay(Path(path))
        require(result == pilot.read(PACK / 'results.json'), 'archive replay differs')
        print('Multi-rule paired report and all recorded inputs replayed.')


if __name__ == '__main__':
    main()
