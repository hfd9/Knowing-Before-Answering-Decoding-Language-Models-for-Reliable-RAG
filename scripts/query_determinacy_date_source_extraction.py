"""Run and score a fixed CPU comparison of direct answers and source extraction."""

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re

import query_determinacy_date_pilot as pilot
from query_determinacy_delegation_collect import CpuBackend
import query_determinacy_threshold_versions as kernel


PACK = pilot.PROTOCOL.parent.with_name('2026-11-24-date-source-extraction-v1')
METHODS = ('direct', 'extract')
TAGS = ('ANSWER_Y', 'ANSWER_N', 'ASK_DATE', 'UNRESOLVED')
LABELS = {'E1', 'E2', 'E3', 'E4', 'F1'}
SYSTEM = ('Use only the supplied excerpts and facts. Dates are inclusive. Do not infer a missing fact. '
          'For an unresolved prerequisite use the unknown output. Use the requested pipe-delimited format without prose.')
DIRECT = ('Check the law and scope, evaluate each possible event date, and then decide whether a unique answer is '
          'supported. Acknowledge the given date if it is known. Being equal to a threshold can matter. '
          'Write A|ACTION first, replacing ACTION with ANSWER_Y, ANSWER_N, ASK_DATE or UNRESOLVED. For every '
          'applicable date write D|YYYY-MM-DD|Y or N|evidence IDs. Each D row should cite the comparison rule, '
          'the applicable annual threshold, scope and case facts, using comma-separated IDs. '
          'If you ask, add Q|event_name with the event whose date you need, such as application or consummation.')
EXTRACT = ('Extract fields only, without answering the exemption question. Use these rows, with no column headers. '
           'R|comparison_symbol|operative_event|comparison_evidence_ID. Use > or <= for comparison_symbol, '
           'and a single event name such as application or consummation. '
           'S|TRUE or FALSE or UNKNOWN|comma-separated_scope_evidence_IDs. Check both the scope rule and case facts. '
           'F|amount_in_whole_dollars|first_possible_date|last_possible_date|known_date_or_NONE|fact_evidence_ID. '
           'V|valid_from|valid_through|threshold_in_whole_dollars|version_evidence_ID, one row per threshold '
           'version in the excerpts. Use YYYY-MM-DD for all dates and digits without commas for dollar amounts. '
           'Use UNKNOWN for unknown required values and NONE for an unstated event date.')
require = pilot.require


def source_packet(profile, facts):
    evidence = '\n'.join(f'[{key}] {value}' for key, value in sorted(profile['evidence'].items()))
    return f'{evidence}\n\n[F1] {facts}\n\n{profile["question"]} The caseworker needs one determination if supported.'


def task_plan(public):
    return [{'case': row['id'], 'method': method, 'messages': [pilot.message('system', SYSTEM), pilot.message(
        'user', source_packet(public['profiles'][row['profile']], row['facts']) + '\n\n' + guidance)]}
            for method, guidance in zip(METHODS, (DIRECT, EXTRACT), strict=True) for row in public['cases']]


def fields(text):
    text = text.strip()
    fence = re.fullmatch(r'```[a-zA-Z]*\n(.*?)\n```', text, re.S)
    text = fence[1] if fence else text
    return [[part.strip() for part in line.split('|')] for line in text.splitlines() if line.strip()]


def evidence_ids(text):
    refs = [part.strip() for part in text.split(',')]
    require(set(refs) <= LABELS and len(refs) == len(set(refs)), 'invalid evidence IDs')
    return sorted(refs)


def iso(text):
    value = date.fromisoformat(text)
    require(value.isoformat() == text, 'date not ISO')
    return value


def integer(text):
    require(re.fullmatch(r'\d+', text) is not None, 'amount is not a whole number')
    return int(text)


def parse_direct(rows):
    require(rows and rows[0][0] == 'A' and len(rows[0]) == 2 and rows[0][1] in TAGS, 'invalid action')
    tag = rows[0][1]
    branch_rows = []
    question = None
    for row in rows[1:]:
        if len(row) == 2 and row[0] == 'Q':
            require(question is None, 'duplicate clarification')
            question = row[1]
        else:
            require(len(row) == 4 and row[0] == 'D' and row[2] in ('Y', 'N'), 'invalid direct branch')
            _, day, answer, refs = row
            branch_rows.append([iso(day).isoformat(), answer == 'Y', evidence_ids(refs)])
    return {'tag': tag, 'branches': sorted(branch_rows), 'ask_event': question}


def parse_extract(rows):
    require(len(rows) >= 4 and [row[0] for row in rows[:3]] == ['R', 'S', 'F']
            and [len(row) for row in rows[:3]] == [4, 3, 6], 'invalid extracted field rows')
    _, comparison, event, rule_ref = rows[0]
    _, scope, scope_refs = rows[1]
    _, amount, start, end, known, fact_ref = rows[2]
    require(comparison in kernel.COMPARISONS and event in ('application', 'consummation'), 'unknown rule fields')
    require(scope in ('TRUE', 'FALSE', 'UNKNOWN'), 'invalid scope')
    versions = []
    for row in rows[3:]:
        require(len(row) == 5 and row[0] == 'V', 'invalid version row')
        _, valid_from, valid_through, threshold, ref = row
        version_ids = evidence_ids(ref)
        require(len(version_ids) == 1, 'version has multiple evidence IDs')
        versions.append([iso(valid_from).isoformat(), iso(valid_through).isoformat(), integer(threshold), version_ids[0]])
    rule_ids, fact_ids = evidence_ids(rule_ref), evidence_ids(fact_ref)
    require(len(rule_ids) == len(fact_ids) == 1, 'rule or facts have multiple evidence IDs')
    return {'rule': [comparison, event, rule_ids[0]], 'scope': {'TRUE': True, 'FALSE': False, 'UNKNOWN': None}[scope],
            'scope_evidence': evidence_ids(scope_refs), 'amount': integer(amount),
            'range': [iso(start).isoformat(), iso(end).isoformat()], 'date': None if known == 'NONE' else iso(known).isoformat(),
            'fact_evidence': fact_ids[0], 'versions': sorted(versions)}


def solve(extracted):
    comparator, event, source = extracted['rule']
    rule = kernel.ThresholdRule(comparator, event, source, tuple(
        kernel.ThresholdVersion(iso(start), iso(end), threshold, ref)
        for start, end, threshold, ref in extracted['versions']))
    first, last = map(iso, extracted['range'])
    known = iso(extracted['date']) if extracted['date'] else None
    result = kernel.evaluate(rule, extracted['amount'], first, last, scope_established=extracted['scope'], event_date=known)
    if result['action'] == 'unresolved':
        return {'tag': 'UNRESOLVED', 'branches': [], 'ask_event': None, 'reason': result['reason']}
    extra = {*extracted['scope_evidence'], extracted['fact_evidence']}
    require(all(branch['from'] == branch['through'] for branch in result['branches']), 'branch exceeds fixture day')
    tag = ('ANSWER_Y' if result['answer'] else 'ANSWER_N') if result['action'] == 'answer' else 'ASK_DATE'
    return {'tag': tag, 'branches': [[branch['from'], branch['answer'], sorted(set(branch['evidence']) | extra)]
                                     for branch in result['branches']], 'ask_event': result.get('ask_event')}


def reference_fields(case, reference):
    rule = reference['profiles'][case['profile']]
    facts = reference['cases'][case['id']]
    return {**{key: rule[key] for key in ('rule', 'versions')}, **{key: facts[key] for key in ('scope', 'amount', 'date')},
            'range': reference['range'], 'scope_evidence': reference['scope_evidence'], 'fact_evidence': 'F1'}


def reference_answer(case, reference):
    truth = reference['cases'][case['id']]
    answers = truth['answers']
    dates = [truth['date']] if truth['date'] else reference['range']
    evidence_by_day = dict(zip(reference['range'], ('E2', 'E3'), strict=True))
    same = len(set(answers)) == 1
    return {'tag': ('ANSWER_Y' if answers[0] else 'ANSWER_N') if same else 'ASK_DATE',
            'branches': [[day, answer, ['E1', evidence_by_day[day], 'E4', 'F1']]
                         for day, answer in zip(dates, answers, strict=True)],
            'ask_event': None if same else 'consummation'}


def grade(outcome, expected):
    return {'strict': all(outcome.get(key) == expected[key] for key in ('tag', 'branches', 'ask_event')),
            'action_exact': outcome.get('tag') == expected['tag'],
            'wrong_unique_on_varying': expected['tag'] == 'ASK_DATE' and outcome.get('tag') in ('ANSWER_Y', 'ANSWER_N'),
            'selected_action': outcome.get('tag')}


def preflight(public, reference):
    controls = []
    for case in public['cases']:
        data = reference_fields(case, reference)
        gold = reference_answer(case, reference)
        require(grade(solve(data), gold)['strict'], 'author fields did not match expected date answers')
        if case['profile'] == 'appraisal':
            wrong = solve(dict(data, rule=['>', *data['rule'][1:]]))
            require(wrong['tag'].startswith('ANSWER_') == gold['tag'].startswith('ANSWER_') and
                    not grade(wrong, gold)['strict'], 'wrong comparator passed strict score')
            require(all(model[1] is not ref[1] for model, ref in zip(wrong['branches'], gold['branches'], strict=True)),
                    'negative comparator did not invert conclusions')
            controls.append(case['id'])
    varied = next(case for case in public['cases'] if case['id'] == 'A2')
    data = reference_fields(varied, reference)
    overlap = ['2024-12-31', *data['versions'][1][1:]]
    probes = {'scope_not_established': dict(data, scope=None),
              'coverage_gap': dict(data, versions=data['versions'][:1]),
              'overlapping_versions': dict(data, versions=[data['versions'][0], overlap])}
    for reason, probe in probes.items():
        result = solve(probe)
        require(result['tag'] == 'UNRESOLVED' and result['reason'] == reason, 'boundary produced an answer')
    # Exercise this scorer on all four amounts in the prior HPML comparison.
    cross = pilot.read(PACK.with_name('2026-11-24-date-cross-rule-v1') / 'results.json')['cross_rule']
    same_routes = 0
    rejected = 0
    for row in cross:
        baseline = solve(dict(data, amount=row['amount']))
        require([branch[1] for branch in baseline['branches']] == [branch['answer'] for branch in row['merged']['branches']],
                'prior HPML result differs')
        wrong = solve(dict(data, amount=row['amount'], rule=['>', *data['rule'][1:]]))
        same_routes += wrong['tag'].startswith('ANSWER_') == baseline['tag'].startswith('ANSWER_')
        rejected += not grade(wrong, baseline)['strict']
    require(same_routes == rejected == 4, 'wrong comparison did not preserve route and fail strict score')
    return {'author_field_matches': len(public['cases']), 'comparator_rejections': controls,
            'unresolved_controls': list(probes), 'prior_comparator_action_only': same_routes,
            'prior_wrong_comparator_strict_rejections': rejected}


def contract():
    paths = [PACK / name for name in ('public.json', 'reference.json', 'protocol.md')]
    paths.extend([Path(__file__), Path(pilot.__file__), Path(pilot.local.__file__), Path(kernel.__file__),
                  pilot.local.ROOT / 'scripts/query_determinacy_delegation_collect.py',
                  PACK.with_name('2026-11-24-date-cross-rule-v1') / 'results.json'])
    return {str(path.resolve().relative_to(pilot.local.ROOT)): pilot.local.hash_file(path) for path in paths}


def collect(run):
    frozen = pilot.read(PACK / 'freeze.json')
    require(frozen['sha256'] == contract(), 'preflight hashes differ')
    plan = task_plan(pilot.read(PACK / 'public.json'))
    env = pilot.local.environment_snapshot()
    run.mkdir(mode=0o700)
    pilot.write(run / 'manifest.json', {'sha256': frozen['sha256'], 'environment': env,
                                       'utc': datetime.now(timezone.utc).isoformat(), 'calls': len(plan)})
    backend = CpuBackend(env)
    for name, batch in pilot.batches('source', plan):
        pilot.write(run / f'{name}.attempt.json', batch)
        result = pilot.generate(backend, batch)
        pilot.write(run / f'{name}.record.json', result)
        print(name, [row['status'] for row in result['records']], round(result['seconds'], 2), flush=True)
    pilot.write(run / 'seal.json', {path.name: pilot.local.hash_file(path) for path in sorted(run.iterdir())})


def archived(run, plan):
    def read(name):
        return pilot.read(run / name)

    seal = read('seal.json')
    require(set(seal) | {'seal.json'} == {path.name for path in run.iterdir()}, 'archive members differ')
    require(all(pilot.local.hash_file(run / name) == digest for name, digest in seal.items()), 'archive seal differs')
    manifest = read('manifest.json')
    require(manifest['sha256'] == contract() and manifest['calls'] == len(plan), 'run manifest differs')
    eos = manifest['environment']['eos_token_ids']
    tokenizer = pilot.local.load_tokenizer()
    records = []
    seconds = 0.0
    for name, batch in pilot.batches('source', plan):
        require(read(f'{name}.attempt.json') == batch, 'archived tasks differ')
        data = read(f'{name}.record.json')
        seconds += data['seconds']
        for item, row in zip(batch, data['records'], strict=True):
            require(all(row[key] == value for key, value in item.items()), 'record differs from attempt')
            text, ids = pilot.render(tokenizer, item['messages'])
            require((text, ids) == (row['rendered_prompt'], row['input_token_ids']), 'rendered input differs')
            tokens = row['generated_token_ids']
            require(0 < len(tokens) <= pilot.LIMIT and not any(token in eos for token in tokens[:-1])
                    and (tokens[-1] in eos or len(tokens) == pilot.LIMIT), 'invalid output token journal')
            decoded = tokenizer.decode(tokens, skip_special_tokens=True)
            require(row['output'] == decoded and row['status'] == pilot.local.output_status(decoded, tokens, eos),
                    'decoded output or status differs')
            records.append(row)
    return records, seconds


def score(run):
    public, reference = (pilot.read(PACK / f'{name}.json') for name in ('public', 'reference'))
    records, seconds = archived(run, task_plan(public))
    cases = {case['id']: case for case in public['cases']}
    results = {method: {} for method in METHODS}
    for row in records:
        method, case_id = row['method'], row['case']
        expected = reference_answer(cases[case_id], reference)
        parsed = fields(row['output'])
        extracted = None
        try:
            require(row['status'] == 'complete', f'output {row["status"]}')
            if method == 'direct':
                outcome = parse_direct(parsed)
            else:
                extracted = parse_extract(parsed)
                outcome = solve(extracted)
            issue = None
        except (ValueError, IndexError) as error:
            action = parsed[0][1] if parsed and len(parsed[0]) >= 2 and parsed[0][0] == 'A' else None
            outcome = {'tag': action if action in TAGS else None}
            issue = str(error)
        checks = grade(outcome, expected)
        checks['strict'] = checks['strict'] and issue is None
        result = results[method][case_id] = {'status': row['status'], 'issue': issue, 'expected': expected,
                                            'outcome': outcome, 'checks': checks}
        if extracted is not None:
            truth = reference_fields(cases[case_id], reference)
            result['field_exact'] = {key: value == truth[key] for key, value in extracted.items()}
            result['rule_component_exact'] = dict(zip(('comparison', 'operative_event', 'rule_evidence'),
                (got == want for got, want in zip(extracted['rule'], truth['rule'], strict=True)), strict=True))
            result['extracted'] = extracted
    summary = {}
    for method, rows in results.items():
        summary[method] = {metric: sum(row['checks'][metric] for row in rows.values())
                           for metric in ('strict', 'action_exact', 'wrong_unique_on_varying')}
        summary[method]['invalid'] = sum(row['issue'] is not None for row in rows.values())
        summary[method]['unresolved'] = sum(row['outcome']['tag'] == 'UNRESOLVED' for row in rows.values())
    return {'rows': results, 'summary': summary, 'calls': len(records), 'seconds': round(seconds, 2),
            'status': dict(Counter(row['status'] for row in records)),
            'input_tokens': sum(len(row['input_token_ids']) for row in records),
            'output_tokens': sum(len(row['generated_token_ids']) for row in records),
            'seal_sha256': pilot.local.hash_file(run / 'seal.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'collect', 'score'))
    parser.add_argument('run', nargs='?', type=Path)
    args = parser.parse_args()
    if args.action == 'preflight':
        gate = preflight(*(pilot.read(PACK / f'{name}.json') for name in ('public', 'reference')))
        print(pilot.local.encode({'sha256': contract(), 'preflight': gate}).decode(), end='')
    elif args.run is None:
        parser.error('collect and score require a run directory')
    elif args.action == 'collect':
        collect(args.run)
    else:
        print(pilot.local.encode(score(args.run)).decode(), end='')
