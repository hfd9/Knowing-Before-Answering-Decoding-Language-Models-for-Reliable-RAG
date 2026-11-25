"""Locate dated rule evidence, extract supported fields and replay CPU decisions."""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from pathlib import Path
import re
import tempfile
import time
from zipfile import ZIP_DEFLATED, ZipFile

import query_determinacy_date_pilot as pilot
from query_determinacy_delegation_collect import CpuBackend
import query_determinacy_threshold_versions as kernel


local = pilot.local
ROOT = local.ROOT
PACK = ROOT / 'docs/review/2026-11-25-date-evidence-first-v1'
DEV_SOURCE = ROOT / 'docs/review/2026-11-24-date-source-extraction-v1'
LETTERS = 'ABCDE'
BATCH = 4
DAY_PATTERN = (r'\b(?:\d{4}-\d{2}-\d{2}|(?:January|February|March|April|May|June|July|August|September|'
               r'October|November|December) \d{1,2}, \d{4})\b')
MONEY_PATTERN = r'\$(\d{1,3}(?:,\d{3})+|\d+)(?![\d,]|\.\d)'
LOCATE = {
    'rule': 'Which excerpt states how the transaction amount is compared with the applicable threshold?',
    'scope': 'Which excerpt gives the eligibility conditions for applying the amount test to the type of transaction?',
    'earlier': 'Which excerpt states the dollar threshold and date interval for the earlier of the two versions?',
    'later': 'Which excerpt states the dollar threshold and date interval for the later of the two versions?',
}
COMPARISON = {
    '>': 'The transaction amount is strictly greater than the threshold.',
    '<=': 'The transaction amount is equal to or less than the threshold.',
    'unknown': 'Neither comparison is stated in the quoted source.',
}
SCOPE = {
    'yes': 'The case facts affirm all the stated scope conditions for applying this amount test.',
    'no': 'The case facts affirmatively contradict a stated scope condition.',
    'unknown': 'A required scope condition is neither affirmed nor contradicted by the case facts.',
}
require = pilot.require


def choice(task_id, context, question, options, rotate=0):
    pairs = list(options.items())
    pairs = pairs[rotate % len(pairs):] + pairs[:rotate % len(pairs)]
    labels = '\n'.join(f'{letter}. {label}' for letter, (_, label) in zip(LETTERS, pairs))
    prompt = (f'{context}\n\n{question}\n{labels}\n'
              'Use only the text above. Reply with one capital letter for the best option.')
    return {'id': task_id, 'prompt': prompt, 'choices': [key for key, _ in pairs]}


def locate_plan(public):
    tasks = []
    for name, profile in public['profiles'].items():
        items = sorted(profile['evidence'].items())
        context = '\n'.join(f'[{key}] {value}' for key, value in items)
        choices = {key: f'Excerpt {key}.' for key, _ in items} | {'unknown': 'None of these excerpts.'}
        require(len(choices) <= len(LETTERS), 'too many evidence candidates')
        for index, (role, question) in enumerate(LOCATE.items()):
            tasks.append(choice(f'{name}/{role}', context, question, choices, index))
    return tasks


def selections(public, picked):
    return {name: {role: picked[f'{name}/{role}'] for role in LOCATE} for name in public['profiles']}


def extract_plan(public, located):
    tasks = []
    for name, profile in public['profiles'].items():
        rule_id = located[name]['rule']
        if rule_id != 'unknown':
            tasks.append(choice(f'{name}/comparison', f'[{rule_id}] {profile["evidence"][rule_id]}',
                                'What amount comparison does this excerpt require?', COMPARISON))
    for case in public['cases']:
        name = case['profile']
        scope_id = located[name]['scope']
        if scope_id == 'unknown':
            continue
        source = public['profiles'][name]['evidence'][scope_id]
        context = f'[{scope_id}] Rule scope: {source}\n[F1] Case facts: {case["facts"]}'
        tasks.append(choice(f'{case["id"]}/scope', context,
                            'Does this case meet the rule scope? Set aside the amount and date tests. '
                            'A condition must be supported by the case facts.', SCOPE))
    return tasks


def parse_days(text):
    return [date.fromisoformat(value) if value[0].isdigit() else datetime.strptime(value, '%B %d, %Y').date()
            for value in re.findall(DAY_PATTERN, text)]


def amount(text):
    matches = re.findall(MONEY_PATTERN, text)
    require(len(matches) == 1, 'expected exactly one whole USD amount in the cited passage')
    return int(matches[0].replace(',', ''))


def rule_fields(profile, ids, comparison):
    require(set(ids.values()) == set(profile['evidence']), 'unresolved or non-distinct evidence roles')
    require(comparison in kernel.COMPARISONS, 'comparison unresolved')
    versions = []
    for role in ('earlier', 'later'):
        source_id = ids[role]
        text = profile['evidence'][source_id]
        days = parse_days(text)
        require(len(days) == 2 and days[0] <= days[1], 'version excerpt does not give one ordered interval')
        versions.append([days[0].isoformat(), days[1].isoformat(), amount(text), source_id])
    require(versions[0][1] < versions[1][0], 'cited versions are misordered or overlap')
    return versions


def fact_fields(facts, rule_text):
    window = re.search(r'\b(?:the )?only possible ([a-z -]+?) dates are ([^.]+)\.', facts, re.I)
    require(window is not None, 'case has no explicit admissible date window')
    event, date_list = window.groups()
    event = event.lower()
    require(re.search(rf'\b{re.escape(event)}\b', rule_text, re.I) is not None, 'event not supported by cited rule')
    days = parse_days(date_list)
    require(len(days) == 2 and days[1] - days[0] == timedelta(days=1), 'case does not give two adjacent dates')
    actual = parse_days(facts[window.end():])
    require(len(actual) <= 1 and (not actual or actual[0] in days), 'actual date missing or inconsistent')
    return event, amount(facts), [day.isoformat() for day in days], actual[0].isoformat() if actual else None


def fields_for(public, case, locations, picked):
    name = case['profile']
    profile = public['profiles'][name]
    ids = locations[name]
    comparison = picked.get(f'{name}/comparison')
    versions = rule_fields(profile, ids, comparison)
    event, value, window, actual = fact_fields(case['facts'], profile['evidence'][ids['rule']])
    scope = {'yes': True, 'no': False, 'unknown': None}[picked.get(f'{case["id"]}/scope', 'unknown')]
    return {'rule': [comparison, event, ids['rule']], 'scope': scope, 'scope_evidence': sorted([ids['scope'], 'F1']),
            'amount': value, 'range': window, 'date': actual, 'fact_evidence': 'F1', 'versions': versions}


def solve(fields):
    comparison, event, citation = fields['rule']
    versions = [kernel.ThresholdVersion(date.fromisoformat(first), date.fromisoformat(last), value, source)
                for first, last, value, source in fields['versions']]
    rule = kernel.ThresholdRule(comparison, event, citation, tuple(versions))
    first, last = map(date.fromisoformat, fields['range'])
    actual = date.fromisoformat(fields['date']) if fields['date'] else None
    output = kernel.evaluate(rule, fields['amount'], first, last, scope_established=fields['scope'], event_date=actual)
    action = output['action']
    tag = {'unresolved': 'UNRESOLVED', 'ask_date': 'ASK_DATE',
           'answer': 'ANSWER_Y' if output['answer'] else 'ANSWER_N'}[action]
    branches = [[day['from'], day['answer'], sorted(set(day['evidence'] + fields['scope_evidence'] +
                                                       [fields['fact_evidence']]))] for day in output['branches']]
    require(all(day['from'] == day['through'] for day in output['branches']), 'non-daily branch in two-day fixture')
    result = {'tag': tag, 'branches': branches, 'ask_event': output.get('ask_event')}
    if action == 'unresolved':
        result['reason'] = output['reason']
    return result


def judge(public, reference, located, picked):
    rows = {}
    for case in public['cases']:
        case_id = case['id']
        expected = reference['cases'][case_id]
        target = reference['profiles'][case['profile']] | expected['fields']
        outcome, fields, error = None, None, None
        try:
            fields = fields_for(public, case, located, picked)
            outcome = solve(fields)
        except (ValueError, KeyError) as exc:
            error = str(exc)
        field_checks = {key: fields is not None and fields[key] == value for key, value in target.items()}
        if fields is not None:
            field_checks.update(dict(zip(('comparison', 'event', 'rule_id'),
                                         (got == want for got, want in zip(fields['rule'], target['rule'], strict=True)),
                                         strict=True)))
        checks = {'fields': all(field_checks.values()), 'action': outcome is not None and
                  outcome['tag'] == expected['outcome']['tag'], 'branches': outcome is not None and
                  outcome['branches'] == expected['outcome']['branches'], 'outcome': outcome == expected['outcome']}
        checks['strict'] = checks['fields'] and checks['outcome']
        rows[case_id] = {'category': expected['category'], 'fields': fields, 'field_checks': field_checks,
                         'outcome': outcome, 'expected': expected['outcome'], 'checks': checks, 'error': error}
    return rows


class ChoiceBackend(CpuBackend):
    def rank(self, tasks):
        torch = self.torch
        tokens = [local.tokenize(self.tokenizer, task['prompt'])[1] for task in tasks]
        width = max(map(len, tokens))
        require(width <= self.context, 'choice prompt exceeds model context')
        pad = self.tokenizer.pad_token_id
        inputs = [[pad] * (width - len(ids)) + ids for ids in tokens]
        masks = [[0] * (width - len(ids)) + [1] * len(ids) for ids in tokens]
        label_tokens = choice_tokens(self.tokenizer)
        started = time.monotonic()
        with torch.inference_mode():
            logits = self.model(input_ids=torch.tensor(inputs, device='cpu'),
                                attention_mask=torch.tensor(masks, device='cpu'),
                                logits_to_keep=1, use_cache=False).logits[:, -1, label_tokens]
        seconds = time.monotonic() - started
        rows = [dict(task, input_token_ids=ids, scores=values[:len(task['choices'])])
                for task, ids, values in zip(tasks, tokens, logits.tolist(), strict=True)]
        return rows, seconds


def choice_tokens(tokenizer):
    tokens = [tokenizer(letter, add_special_tokens=False)['input_ids'] for letter in LETTERS]
    require(all(len(token) == 1 for token in tokens), 'choice labels must be single tokens')
    return [token[0] for token in tokens]


def best(row):
    scores = row['scores']
    require(len(scores) == len(row['choices']) and all(isfinite(score) for score in scores), 'bad choice scores')
    maximum = max(scores)
    require(scores.count(maximum) == 1, 'tied choice scores')
    return row['choices'][scores.index(maximum)]


def contract(split):
    paths = [Path(__file__), Path(kernel.__file__), Path(pilot.__file__), Path(local.__file__),
             ROOT / 'scripts/query_determinacy_delegation_collect.py', PACK / 'protocol.md', PACK / f'{split}-public.json',
             PACK / f'{split}-reference.json']
    if split == 'dev':
        paths.extend(DEV_SOURCE / name for name in ('public.json', 'reference.json'))
    else:
        paths.append(PACK / 'freeze.json')
    return {str(path.relative_to(ROOT)): local.hash_file(path) for path in paths}


def collect(split, run):
    if split == 'heldout':
        verify_freeze()
    public = pilot.read(PACK / f'{split}-public.json')
    environment = local.environment_snapshot()
    if split == 'heldout':
        require(environment == pilot.read(PACK / 'freeze.json')['environment'], 'runtime changed after freeze')
    run.mkdir(mode=0o700)
    pilot.write(run / 'manifest.json', {'split': split, 'hashes': contract(split), 'environment': environment,
                                       'utc': datetime.now(timezone.utc).isoformat()})
    backend = ChoiceBackend(environment)

    def execute(phase, plan):
        results = []
        for offset in range(0, len(plan), BATCH):
            tasks = plan[offset:offset + BATCH]
            prefix = run / f'{phase}-{offset:02d}'
            pilot.write(prefix.with_suffix('.attempt.json'), tasks)
            rows, seconds = backend.rank(tasks)
            pilot.write(prefix.with_suffix('.record.json'), {'rows': rows, 'seconds': seconds})
            results.extend(rows)
            print(phase, offset + len(tasks), len(plan), f'{seconds:.2f}s',
                  ' '.join(f'{row["id"]}={best(row)}' for row in rows), flush=True)
        return {row['id']: best(row) for row in results}

    located = selections(public, execute('locate', locate_plan(public)))
    execute('extract', extract_plan(public, located))
    pilot.write(run / 'seal.json', {path.name: local.hash_file(path) for path in sorted(run.iterdir())})


def verify(run):
    manifest = pilot.read(run / 'manifest.json')
    split = manifest['split']
    require(manifest['hashes'] == contract(split), 'source contract changed')
    if split == 'heldout':
        verify_freeze()
    seal = pilot.read(run / 'seal.json')
    require(set(seal) | {'seal.json'} == {path.name for path in run.iterdir()}, 'unexpected archive membership')
    require(all(local.hash_file(run / name) == sha for name, sha in seal.items()), 'archive content changed')
    public = pilot.read(PACK / f'{split}-public.json')
    reference = pilot.read(PACK / f'{split}-reference.json')
    tokenizer = local.load_tokenizer()
    token_counts, seconds, seen = [], [], {'manifest.json'}

    def replay(phase, plan):
        picked = {}
        for offset in range(0, len(plan), BATCH):
            prefix = f'{phase}-{offset:02d}'
            attempt, record = (f'{prefix}.{name}.json' for name in ('attempt', 'record'))
            seen.update((attempt, record))
            tasks = plan[offset:offset + BATCH]
            require(pilot.read(run / attempt) == tasks, 'attempt differs from reconstructed plan')
            batch = pilot.read(run / record)
            seconds.append(batch['seconds'])
            for task, row in zip(tasks, batch['rows'], strict=True):
                require(all(row[key] == value for key, value in task.items()), 'choice task changed')
                ids = local.tokenize(tokenizer, row['prompt'])[1]
                require(ids == row['input_token_ids'], 'prompt token IDs differ')
                token_counts.append(len(ids))
                picked[row['id']] = best(row)
        return picked

    located = selections(public, replay('locate', locate_plan(public)))
    picked = replay('extract', extract_plan(public, located))
    require(seen == set(seal), 'archive has unplanned batches')
    rows = judge(public, reference, located, picked)
    counts = {key: sum(row['checks'][key] for row in rows.values())
              for key in ('fields', 'action', 'branches', 'outcome', 'strict')}
    field_counts = Counter(key for row in rows.values() for key, valid in row['field_checks'].items() if valid)
    return {'split': split, 'seal_sha256': local.hash_file(run / 'seal.json'), 'locations': located, 'picks': picked,
            'model_choices': len(token_counts), 'input_tokens': sum(token_counts), 'seconds': round(sum(seconds), 2),
            'case_count': len(rows), 'counts': counts, 'field_counts': dict(field_counts),
            'passes': counts['strict'] == len(rows), 'rows': rows}


def verify_freeze():
    frozen = pilot.read(PACK / 'freeze.json')
    require(frozen['contract'] == contract('dev'), 'development artifacts changed after freeze')
    require(frozen['result_sha256'] == local.hash_file(PACK / 'dev-results.json') and
            frozen['archive_sha256'] == local.hash_file(PACK / 'dev-raw.zip'), 'development archive changed')
    require(pilot.read(PACK / 'dev-results.json')['passes'], 'development has not passed')


def archive(run):
    result = verify(run)
    split = result['split']
    with ZipFile(PACK / f'{split}-raw.zip', 'x', ZIP_DEFLATED) as zipped:
        for path in sorted(run.iterdir()):
            zipped.write(path, path.name)
    pilot.write(PACK / f'{split}-results.json', result)
    if split == 'dev' and result['passes']:
        manifest = pilot.read(run / 'manifest.json')
        pilot.write(PACK / 'freeze.json', {'contract': manifest['hashes'], 'environment': manifest['environment'],
                    'utc': datetime.now(timezone.utc).isoformat(),
                    'result_sha256': local.hash_file(PACK / 'dev-results.json'),
                    'archive_sha256': local.hash_file(PACK / 'dev-raw.zip')})
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('collect', 'score', 'archive', 'check-archive'))
    cli.add_argument('value', help='archive split or filesystem run directory')
    cli.add_argument('--split', choices=('dev', 'heldout'), default='dev')
    args = cli.parse_args()
    if args.action == 'collect':
        collect(args.split, Path(args.value))
    elif args.action == 'check-archive':
        require(args.value in ('dev', 'heldout'), 'use dev or heldout')
        with tempfile.TemporaryDirectory(prefix='kba-date-evidence-replay-') as directory:
            with ZipFile(PACK / f'{args.value}-raw.zip') as zipped:
                zipped.extractall(directory)
            result = verify(Path(directory))
        require(result == pilot.read(PACK / f'{args.value}-results.json'), 'archived scores changed')
        print(f'{args.value}: {result["case_count"]} cases and {result["model_choices"]} choices replayed')
    else:
        result = (verify if args.action == 'score' else archive)(Path(args.value))
        print(local.encode({key: value for key, value in result.items() if key != 'rows'}).decode(), end='')


if __name__ == '__main__':
    main()
