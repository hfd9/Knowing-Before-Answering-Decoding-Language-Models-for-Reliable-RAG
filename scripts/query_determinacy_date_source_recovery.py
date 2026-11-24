"""Collect a separately sealed interface recovery on the same six source cases."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import query_determinacy_date_source_extraction as study
from query_determinacy_delegation_collect import CpuBackend, LIMITS


PACK = study.PACK
pilot = study.pilot
local = pilot.local
require = study.require
GUIDANCE = {
    'direct': ('Answer in clear short sentences using only these excerpts and facts. Show whether the exemption '
               'applies on every date still possible, citing the relevant rule, annual threshold, scope and facts '
               'by evidence ID. If the actual date is known, use it. Conclude with one answer when all applicable '
               'dates agree. Otherwise ask for the fact needed for a unique determination.'),
    'extract': ('Extract only the facts and rules needed for a separate solver. Do not decide the exemption. '
                'Return one compact JSON object. Use ISO dates, integer dollar amounts without commas, and null '
                'for an unstated actual date or other unknown value. Use > or <= for the comparison, the legal '
                'event name for event, and true, false or null for scope. Include all listed annual versions. '
                'Supply evidence IDs for each group. Fill this object with values from the excerpts and facts: '
                '{"comparison":null,"event":null,"rule_id":null,"scope":null,"scope_ids":[],"amount":null,'
                '"fact_id":null,"first":null,"last":null,"date":null,"versions":'
                '[{"from":null,"through":null,"threshold":null,"id":null}]}'),
}


def plan(public):
    return [{'case': case['id'], 'method': method, 'route': 'direct', 'prompt': study.source_packet(
        public['profiles'][case['profile']], case['facts']) + '\n\n' + GUIDANCE[method]}
            for method in study.METHODS for case in public['cases']]


def parse(text):
    text = text.strip()
    fence = re.fullmatch(r'```(?:json)?\s*\n(.*?)\n```', text, re.S | re.I)
    data = json.loads(fence[1] if fence else text)
    expected = {'comparison', 'event', 'rule_id', 'scope', 'scope_ids', 'amount', 'fact_id', 'first', 'last', 'date', 'versions'}
    require(isinstance(data, dict) and set(data) == expected, 'missing or extra JSON fields')
    require(isinstance(data['versions'], list) and (data['scope'] is None or type(data['scope']) is bool),
            'invalid versions or scope')
    require(isinstance(data['scope_ids'], list) and all(isinstance(item, str) for item in data['scope_ids']), 'invalid scope IDs')
    require(type(data['amount']) is int, 'invalid amount')
    scope = 'UNKNOWN' if data['scope'] is None else str(data['scope']).upper()
    actual_date = 'NONE' if data['date'] is None else data['date']
    rows = [['R', data['comparison'], data['event'], data['rule_id']],
            ['S', scope, ','.join(data['scope_ids'])],
            ['F', str(data['amount']), data['first'], data['last'], actual_date, data['fact_id']]]
    for version in data['versions']:
        require(isinstance(version, dict) and set(version) == {'from', 'through', 'threshold', 'id'} and
                type(version['threshold']) is int, 'invalid version fields')
        rows.append(['V', version['from'], version['through'], str(version['threshold']), version['id']])
    require(all(isinstance(field, str) for row in rows for field in row), 'unknown required JSON value')
    return study.parse_extract(rows)


def fingerprints():
    sources = study.contract()
    for path in (Path(__file__), PACK / 'freeze.json', PACK / 'interface-recovery.md'):
        sources[str(path.resolve().relative_to(local.ROOT))] = local.hash_file(path)
    return sources


def collect(run):
    sources = pilot.read(PACK / 'recovery-freeze.json')['sha256']
    require(sources == fingerprints(), 'recovery preflight differs')
    tasks = plan(pilot.read(PACK / 'public.json'))
    env = local.environment_snapshot()
    run.mkdir(mode=0o700)
    pilot.write(run / 'manifest.json', {'sha256': sources, 'environment': env, 'calls': len(tasks),
                                       'utc': datetime.now(timezone.utc).isoformat()})
    backend = CpuBackend(env)
    for name, items in pilot.batches('recovery', tasks):
        pilot.write(run / f'{name}.attempt.json', items)
        rows, seconds = backend.generate(items)
        pilot.write(run / f'{name}.record.json', {'records': rows, 'seconds': seconds})
        print(name, [row['status'] for row in rows], round(seconds, 2), flush=True)
    pilot.write(run / 'seal.json', {path.name: local.hash_file(path) for path in sorted(run.iterdir())})


def archived(run, tasks):
    def read(name):
        return pilot.read(run / name)

    seal = read('seal.json')
    require(set(seal) | {'seal.json'} == {path.name for path in run.iterdir()}, 'recovery archive members differ')
    require(all(local.hash_file(run / name) == sha for name, sha in seal.items()), 'recovery seal differs')
    manifest = read('manifest.json')
    require(manifest['sha256'] == fingerprints() and manifest['calls'] == len(tasks), 'recovery manifest differs')
    eos = manifest['environment']['eos_token_ids']
    tokenizer = local.load_tokenizer()
    rows = []
    seconds = 0.0
    for name, items in pilot.batches('recovery', tasks):
        require(read(f'{name}.attempt.json') == items, 'recovery attempts differ')
        batch = read(f'{name}.record.json')
        seconds += batch['seconds']
        for item, row in zip(items, batch['records'], strict=True):
            require(all(row[key] == value for key, value in item.items()), 'record differs from recovery attempt')
            text, ids = local.tokenize(tokenizer, item['prompt'])
            require((text, ids) == (row['rendered_prompt'], row['input_token_ids']), 'recovery rendering differs')
            tokens = row['generated_token_ids']
            require(0 < len(tokens) <= LIMITS['direct'] and not any(token in eos for token in tokens[:-1])
                    and (tokens[-1] in eos or len(tokens) == LIMITS['direct']), 'invalid recovery token record')
            decoded = tokenizer.decode(tokens, skip_special_tokens=True)
            require(row['output'] == decoded and row['status'] == local.output_status(decoded, tokens, eos), 'decoded output differs')
            rows.append(row)
    return rows, seconds


def score(run):
    public, reference = (pilot.read(PACK / f'{name}.json') for name in ('public', 'reference'))
    rows, seconds = archived(run, plan(public))
    review = pilot.read(PACK / 'recovery-direct-review.json')
    cases = {case['id']: case for case in public['cases']}
    results = {method: {} for method in study.METHODS}
    for row in rows:
        case_id, method = row['case'], row['method']
        expected = study.reference_answer(cases[case_id], reference)
        extracted = None
        issue = None if row['status'] == 'complete' else row['status']
        if method == 'direct':
            annotation = review[case_id]
            require(local.sha(row['output'].encode()) == annotation['output_sha256'], 'direct review binds different text')
            outcome = annotation['observed']
        else:
            try:
                require(issue is None, issue)
                extracted = parse(row['output'])
                outcome = study.solve(extracted)
            except (ValueError, TypeError) as error:
                issue = str(error)
                outcome = {'tag': None}
        checks = study.grade(outcome, expected)
        checks['strict'] = checks['strict'] and issue is None
        result = results[method][case_id] = {'status': row['status'], 'issue': issue, 'expected': expected,
                                            'outcome': outcome, 'checks': checks}
        if extracted is not None:
            truth = study.reference_fields(cases[case_id], reference)
            result['field_exact'] = {key: value == truth[key] for key, value in extracted.items()}
            result['rule_component_exact'] = {key: actual == desired for key, actual, desired in zip(
                ('comparison', 'operative_event', 'rule_evidence'), extracted['rule'], truth['rule'], strict=True)}
            result['extracted'] = extracted
    summary = {method: {key: sum(row['checks'][key] for row in subset.values())
                        for key in ('strict', 'action_exact', 'wrong_unique_on_varying')}
               | {'invalid': sum(row['issue'] is not None for row in subset.values())}
               for method, subset in results.items()}
    return {'rows': results, 'summary': summary, 'calls': len(rows), 'seconds': round(seconds, 2),
            'status': dict(Counter(row['status'] for row in rows)),
            'input_tokens': sum(len(row['input_token_ids']) for row in rows),
            'output_tokens': sum(len(row['generated_token_ids']) for row in rows),
            'seal_sha256': local.hash_file(run / 'seal.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'collect', 'score'))
    parser.add_argument('run', nargs='?', type=Path)
    args = parser.parse_args()
    if args.action == 'freeze':
        print(local.encode({'sha256': fingerprints()}).decode(), end='')
    elif args.run is None:
        parser.error('collect and score require a run directory')
    elif args.action == 'collect':
        collect(args.run)
    else:
        print(local.encode(score(args.run)).decode(), end='')
