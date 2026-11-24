"""Replay the date pilot and localize version, comparison, and evidence errors offline."""

import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import re
from zipfile import ZipFile

import query_determinacy_date_pilot as pilot


ARCHIVE = pilot.PROTOCOL.with_name('raw.zip')
OUT = ARCHIVE.parent.with_name('2026-11-24-date-diagnostic-v1')
RULE = ('[E1] 12 CFR § 1026.3(b)(1) and Supplement I, comment 3(b)-5.i (summary). '
        'For an unsecured closed-end consumer loan that is not a private education loan, the amount-based exemption '
        'applies if the lender extends credit at consummation in an amount exceeding the threshold then in effect, '
        'or makes an express written commitment at consummation to extend a total amount exceeding that threshold. '
        'Consummation is when the borrower becomes contractually bound to the loan.')
CASE_START = ('A lender offered a borrower two alternative amounts for a single unsecured, closed-end loan for '
              'household expenses. It was not a private education loan. The two options were ')
CASE_END = ('Under either option, the lender would disburse the entire amount when the borrower became contractually '
            'bound, with no commitment to extend any further credit. The loan could only have been consummated on '
            'one of the local calendar days from ')
REQUEST = ('The caseworker needs a single determination. If you can give one, state it and cite the applicable '
           'evidence by ID. If you need another fact to make that determination, ask for it.')
MONEY = r'(?:[1-9]\d{0,2}(?:,\d{3})+|\d{1,3})'
DAY = r'\d{4}-\d{2}-\d{2}'
SCENARIO = re.compile(re.escape(CASE_START) + rf'A \(\$({MONEY})\) and B \(\$({MONEY})\)\. '
                      + re.escape(CASE_END) + rf'({DAY}) through ({DAY}), inclusive\.'
                      + rf'(?:\nThe loan was consummated on ({DAY})\.)?')
VERSION = re.compile(r'\[(E(?:[2-9]|[1-9]\d+))\] Supplement I, comment 3\(b\)-3\.[a-z]+\. '
                     rf'“From January 1, (\d{{4}}), through December 31, \2, the threshold amount is \$({MONEY})\.”')
QUESTION = re.compile(r'Would option ([AB]) qualify for the amount-based exemption under § 1026\.3\(b\)\?\n'
                      + re.escape(REQUEST))
REPLY = re.compile(r'Conclusion:\s*(YES|NO)\s*\nEvidence:\s*([^\n]+)', re.I)
SUPPLIED = re.compile(rf'^The borrower became contractually bound to the loan on ({DAY})\. ')
MODES = ('original', 'evidence_only', 'answer_only', 'both')
require = pilot.require


def dollars(text):
    return int(text.replace(',', ''))


def unresolved(reason, branches=()):
    return {'action': 'unresolved', 'answer': None, 'evidence': [], 'reason': reason, 'branches': list(branches)}


def decide(branches):
    if not branches or any(branch['answer'] is None for branch in branches):
        return unresolved('incomplete_version_judgments', branches)
    answers = {branch['answer'] for branch in branches}
    evidence = sorted({label for branch in branches for label in branch['evidence']})
    result = {'action': 'answer', 'answer': branches[0]['answer'], 'evidence': evidence, 'branches': branches}
    if len(answers) > 1:
        left, right = (branch['date'] for branch in branches)
        result.update(action='ask_date', answer=None,
                      question=f'On which day did the borrower become contractually bound, {left} or {right}?')
    return result


def solve_public(text, supplied_day=None):
    """Return an auditable decision from the packet, with explicit reasons for unsupported cases."""
    paragraphs = text.split('\n\n')
    if len(paragraphs) != 3:
        return unresolved('unsupported_packet')
    rules, facts, question = paragraphs
    base_rule, *version_lines = rules.split('\n')
    scenario = SCENARIO.fullmatch(facts)
    ask = QUESTION.fullmatch(question)
    versions = [VERSION.fullmatch(line) for line in version_lines]
    if base_rule != RULE or not scenario or not ask or not versions or any(match is None for match in versions):
        return unresolved('unsupported_packet')
    amount_a, amount_b, start, end, stated = scenario.groups()
    try:
        first, last = map(date.fromisoformat, (start, end))
        require(last - first == timedelta(days=1), 'unsupported_range')
        require(stated is None or supplied_day is None or stated == supplied_day, 'conflicting_event_dates')
        event = stated if supplied_day is None else supplied_day
        require(event is None or event in (start, end), 'event_date_outside_range')
    except ValueError as error:
        return unresolved(str(error))
    amounts = {'A': dollars(amount_a), 'B': dollars(amount_b)}
    option = ask[1]
    branches = []
    labels = [version[1] for version in versions]
    if len(labels) != len(set(labels)):
        return unresolved('duplicate_evidence_identifier')
    for day in ([event] if event else [start, end]):
        operative_day = date.fromisoformat(day)
        applicable = [version for version in versions if int(version[2]) == operative_day.year]
        branch = {'date': day, 'option': option, 'amount': amounts[option], 'comparator': '>',
                  'matched_versions': [version[1] for version in applicable]}
        if len(applicable) != 1:
            branches.append(dict(branch, answer=None, evidence=[],
                                 reason='coverage_gap' if not applicable else 'overlapping_versions'))
            continue
        label, year, amount_text = applicable[0].groups()
        threshold = dollars(amount_text)
        branches.append(dict(branch, threshold=threshold, valid_from=f'{year}-01-01', valid_through=f'{year}-12-31',
                             answer=amounts[option] > threshold, evidence=['E1', label]))
    return decide(branches)


def archived_rows():
    contract, inputs = pilot.contract()
    replies = {}
    rows = []
    with ZipFile(ARCHIVE) as archive:
        seal = json.loads(archive.read('seal.json'))
        manifest = json.loads(archive.read('manifest.json'))
        names = archive.namelist()
        require(len(names) == len(seal) + 1 and set(names) == set(seal) | {'seal.json'}, 'archive entries differ')
        require(all(pilot.local.sha(archive.read(name)) == sha for name, sha in seal.items()), 'archive seal differs')
        require(all(manifest[key] == value for key, value in contract.items()), 'frozen pilot contract differs')
        for prefix in ('first', 'follow'):
            plan = pilot.initial_plan(inputs) if prefix == 'first' else pilot.follow_plan(inputs['R06'], replies['R06'])
            for name, tasks in pilot.batches(prefix, plan):
                require(json.loads(archive.read(f'{name}.attempt.json')) == tasks, 'archived messages differ')
                batch = json.loads(archive.read(f'{name}.record.json'))['records']
                for task, row in zip(tasks, batch, strict=True):
                    require(all(row[key] == value for key, value in task.items()), 'archived row differs from attempt')
                    require(row['status'] == 'complete', 'archived response incomplete')
                    rows.append(row)
            if prefix == 'first':
                replies = pilot.first_replies(inputs, rows)
                require(replies == json.loads(archive.read('first-replies.json')), 'archived first replies differ')
    return inputs, rows


def cited(text):
    return sorted(set(re.findall(r'\bE\d+\b', text.upper())))


def branch_record(row, expected):
    match = REPLY.fullmatch(row['output'].strip())
    require(match is not None, 'unparsed branch response')
    answer, citation_line = match.groups()
    evidence = cited(citation_line)
    answer = answer.upper() == 'YES'
    return {'answer': answer, 'evidence': evidence, 'date_bound_evidence': evidence == expected['evidence'],
            'answer_correct': answer == expected['answer'], 'accepted_by_frozen_aggregate': pilot.branch_value(row) is not None}


def replace_fields(row, expected, mode):
    match = REPLY.fullmatch(row['output'].strip())
    require(match is not None, 'unparsed branch response')
    answer, evidence = match.groups()
    if mode in ('answer_only', 'both'):
        answer = 'YES' if expected['answer'] else 'NO'
    if mode in ('evidence_only', 'both'):
        evidence = ', '.join(expected['evidence'])
    return dict(row, output=f'Conclusion: {answer}\nEvidence: {evidence}')


def frozen_decision(rows):
    output = pilot.aggregate(rows)
    # Include evidence from the displayed reply, including both conditions when it asks.
    if output.startswith(('YES.', 'NO.')):
        return {'action': 'answer', 'answer': output.startswith('YES.'), 'evidence': cited(output), 'output': output}
    return {'action': 'ask_date' if output.endswith(pilot.ASK) else 'unresolved',
            'answer': None, 'evidence': cited(output), 'output': output}


def grounded(response, gold):
    return all(response[key] == gold[key] for key in ('action', 'answer', 'evidence'))


def audit_group(rows, expected):
    branches = expected['branches']
    require([row['day'] for row in rows] == [branch['date'] for branch in branches], 'branch dates differ')
    variants = {}
    for mode in MODES:
        edited = [row if mode == 'original' else replace_fields(row, branch, mode)
                  for row, branch in zip(rows, branches, strict=True)]
        evaluated = [branch_record(row, branch) for row, branch in zip(edited, branches, strict=True)]
        decision = frozen_decision(edited)
        strict_branches = sum(record['date_bound_evidence'] and record['answer_correct'] for record in evaluated)
        variants[mode] = dict(decision, strict_pass=strict_branches == len(rows) and grounded(decision, expected),
                              branch_strict=strict_branches,
                              wrong_unique=expected['action'] == 'ask_date' and decision['action'] == 'answer',
                              branches=evaluated)
    return variants


def build():
    inputs, rows = archived_rows()
    first = {case: solve_public(text) for case, text in inputs.items()}
    calls = []
    branch_groups = {}
    for row in rows:
        day = None
        if row['turn'] == 2:
            supplied = SUPPLIED.match(row['messages'][-1]['content'])
            require(supplied and supplied[1] == row['day'], 'follow-up date not supported by user message')
            day = supplied[1]
        expected = first[row['case']] if day is None else solve_public(inputs[row['case']], day)
        details = {'turn': row['turn'], 'case': row['case'], 'method': row['method'], 'date': row['day'],
                   'actual_evidence': cited(row['output'])}
        if row['method'] == 'by_version':
            branch = next(branch for branch in expected['branches'] if branch['date'] == row['day'])
            details['observed_branch'] = branch_record(row, branch)
            group = row['case'] if day is None else f'R06-follow-{day}'
            branch_groups.setdefault(group, []).append(row)
        calls.append(details)

    # Load the author reference only after computing packet-based decisions.
    ref_path = pilot.MATERIAL / 'reference.json'
    reference = pilot.read(ref_path)['cases']
    require(all(grounded(first[case], reference[case]) for case in first), 'packet-based first turn disagrees with reference')
    ref_follow = {ref['event_date']: ref for ref in reference.values() if ref['option'] == 'B' and ref['event_date']}
    follow = {day: solve_public(inputs['R06'], day) for day in ref_follow}
    require(all(grounded(follow[day], ref_follow[day]) for day in follow), 'follow-up disagrees with dated B reference')
    groups = {case: audit_group(branch_groups[case], first[case]) for case in first}
    follow_groups = {day: audit_group(branch_groups[f'R06-follow-{day}'], follow[day]) for day in follow}
    summary = {name: {mode: {'branch_strict': sum(group[mode]['branch_strict'] for group in items.values()),
                             'strict_pass': sum(group[mode]['strict_pass'] for group in items.values()),
                             'wrong_unique': sum(group[mode]['wrong_unique'] for group in items.values())}
                      for mode in MODES} for name, items in [('first', groups), ('follow', follow_groups)]}
    fingerprints = {str(path.relative_to(pilot.local.ROOT)): pilot.local.hash_file(path)
                    for path in (ARCHIVE, pilot.MATERIAL / 'inputs.json', ref_path, Path(__file__).resolve(),
                                 Path(pilot.__file__).resolve())}
    return {'sha256': fingerprints, 'raw_call_count': len(calls), 'public_first': first, 'public_follow': follow,
            'raw_calls': calls, 'first_interventions': groups, 'follow_interventions': follow_groups, 'summary': summary}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='compare the rebuilt report to results.json')
    args = parser.parse_args()
    payload = pilot.local.encode(build())
    if args.verify:
        require(payload == (OUT / 'results.json').read_bytes(), 'diagnostic replay differs')
        print('Date diagnostic replay passed.')
    else:
        print(payload.decode(), end='')
