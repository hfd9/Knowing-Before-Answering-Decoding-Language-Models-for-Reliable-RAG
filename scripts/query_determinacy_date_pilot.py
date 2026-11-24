"""Collect and replay the fixed six-input CPU date clarification pilot."""

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import time

from query_determinacy_delegation_collect import CpuBackend
import query_determinacy_shared_live as local


MATERIAL = local.ROOT / 'docs/review/2026-11-24-date-material-acceptance-v1'
PROTOCOL = local.ROOT / 'docs/review/2026-11-24-date-clarification-pilot-v1/protocol.md'
METHODS = ('direct', 'ask_if_missing', 'by_version')
BATCH = 4
LIMIT = 160
SYSTEM = ('Use only the supplied excerpts and facts. Check which evidence applies and whether the facts '
          'support a single conclusion. Avoid unsupported assumptions. Be concise and use evidence IDs.')
ASK = 'On which day did the borrower become contractually bound to the loan: December 31, 2024 or January 1, 2025?'


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    local.write_new(path, local.encode(value))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def present_dates(text):
    scenario = text.split('\n\n')[1]
    window = re.search(r'from (\d{4}-\d{2}-\d{2}) through (\d{4}-\d{2}-\d{2}), inclusive\.', scenario)
    start, end = map(date.fromisoformat, window.groups())
    days = [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]
    stated = re.search(r'^The loan was consummated on (\d{4}-\d{2}-\d{2})\.$', scenario, re.MULTILINE)
    known = stated.group(1) if stated else None
    require(len(days) == 2 and (known is None or known in days), 'unexpected material date window')
    return known, days


def message(role, content):
    return {'role': role, 'content': content}


def branch_instruction(day):
    return (f'\n\nFor this calculation only, evaluate the requested option at consummation on {day}. '
            'Use the amount-based exemption rule and the applicable annual threshold. Return exactly two lines. '
            'On the first line write Conclusion: YES, Conclusion: NO, or Conclusion: UNKNOWN. '
            'On the second line write Evidence: followed by the relevant evidence IDs, separated by commas.')


def task(case, method, original, day=None, previous=None):
    turns = [message('system', SYSTEM), message('user', original)]
    if previous is not None:
        turns.extend([message('assistant', previous), message(
            'user', f'The borrower became contractually bound to the loan on {day}. '
                    'Please give the single determination now and cite the applicable evidence by ID.')])
    if method == 'by_version':
        turns[-1]['content'] += branch_instruction(day)
    return {'case': case, 'method': method, 'day': day, 'turn': 1 if previous is None else 2, 'messages': turns}


def initial_plan(inputs):
    direct = [task(case, 'direct', text) for case, text in inputs.items()]
    branch = []
    for case, text in inputs.items():
        stated, days = present_dates(text)
        branch.extend(task(case, 'by_version', text, day) for day in ([stated] if stated else days))
    require(len(direct) == 6 and len(branch) == 8, 'unexpected first turn count')
    return direct + branch


def branch_value(row):
    if row['status'] != 'complete':
        return None
    match = re.fullmatch(r'Conclusion:\s*(YES|NO)\s*\nEvidence:\s*([^\n]+)', row['output'].strip(), re.I)
    if not match:
        return None
    answer, citations = match.groups()
    ids = set(re.findall(r'\bE\d+\b', citations.upper()))
    if ids not in ({'E1', 'E2'}, {'E1', 'E3'}):
        return None
    return answer.upper(), ids


def aggregate(rows):
    values = [branch_value(row) for row in rows]
    if any(value is None for value in values):
        return 'Unresolved: a version-specific conclusion and its evidence could not be established.'
    answers = {answer for answer, _ in values}
    if len(answers) == 1:
        ids = ', '.join(sorted(set.union(*(ids for _, ids in values))))
        return f'{values[0][0]}. Evidence: {ids}.'
    branches = [f"{row['day']}: {answer} ({', '.join(sorted(ids))})."
                for row, (answer, ids) in zip(rows, values, strict=True)]
    return ' '.join([*branches, ASK])


def first_replies(inputs, rows):
    replies = {}
    for case, text in inputs.items():
        direct = next(row['output'].strip() for row in rows if row['method'] == 'direct' and row['case'] == case)
        branches = [row for row in rows if row['method'] == 'by_version' and row['case'] == case]
        stated, _ = present_dates(text)
        replies[case] = {'direct': direct, 'ask_if_missing': direct if stated else ASK,
                         'by_version': aggregate(branches)}
    return replies


def follow_plan(text, replies):
    stated, days = present_dates(text)
    require(stated is None, 'follow-up requires omitted date')
    return [task('R06', method, text, day, replies[method]) for method in METHODS for day in days]


def render(tokenizer, turns):
    text = tokenizer.apply_chat_template(turns, tokenize=False, add_generation_prompt=True)
    return text, tokenizer(text, add_special_tokens=False)['input_ids']


def generate(backend, tasks):
    torch = backend.torch
    rendered = [render(backend.tokenizer, item['messages']) for item in tasks]
    width = max(len(ids) for _, ids in rendered)
    require(width + LIMIT <= backend.context, 'context limit exceeded')
    pad = backend.tokenizer.pad_token_id
    padded = [[pad] * (width - len(ids)) + ids for _, ids in rendered]
    masks = [[0] * (width - len(ids)) + [1] * len(ids) for _, ids in rendered]
    config = backend.config(max_new_tokens=LIMIT, do_sample=False, num_beams=1, use_cache=True,
                            eos_token_id=backend.eos, pad_token_id=pad,
                            bos_token_id=backend.model.generation_config.bos_token_id)
    started = time.monotonic()
    with torch.inference_mode():
        outputs = backend.model.generate(input_ids=torch.tensor(padded, dtype=torch.long, device='cpu'),
                                         attention_mask=torch.tensor(masks, device='cpu'),
                                         generation_config=config, logits_to_keep=1)
    seconds = time.monotonic() - started
    require(outputs[:, :width].tolist() == padded, 'generation input prefix mismatch')
    records = []
    for item, (text, ids), suffix in zip(tasks, rendered, outputs[:, width:].tolist(), strict=True):
        length = next((index + 1 for index, token in enumerate(suffix) if token in backend.eos), len(suffix))
        require(all(token == pad for token in suffix[length:]), 'non-padding token after EOS')
        tokens = suffix[:length]
        output = backend.tokenizer.decode(tokens, skip_special_tokens=True)
        records.append(dict(item, rendered_prompt=text, input_token_ids=ids, generated_token_ids=tokens,
                            output=output, status=local.output_status(output, tokens, backend.eos)))
    return {'seconds': seconds, 'records': records}


def contract():
    paths = [MATERIAL / 'inputs.json', MATERIAL / 'reference.json', MATERIAL / 'check.py', PROTOCOL,
             Path(__file__).resolve(), Path(local.__file__),
             local.ROOT / 'scripts/query_determinacy_delegation_collect.py']
    hashes = {str(path.relative_to(local.ROOT)): local.hash_file(path) for path in paths}
    rows = read(MATERIAL / 'inputs.json')
    require([row['id'] for row in rows] == [f'R{i:02d}' for i in range(1, 7)], 'unexpected input IDs')
    return {'fixed_sha256': hashes, 'batch_size': BATCH, 'max_new_tokens': LIMIT, 'device': 'cpu',
            'dtype': 'float32', 'attention': 'sdpa', 'sampling': False, 'threads': 16}, {
                row['id']: row['input'] for row in rows}


def batches(prefix, plan):
    return [(f'{prefix}-{offset:02d}', plan[offset:offset + BATCH]) for offset in range(0, len(plan), BATCH)]


def collect(run):
    manifest, inputs = contract()
    environment = local.environment_snapshot()
    run.mkdir(mode=0o700)
    write(run / 'manifest.json', dict(manifest, environment=environment, utc=datetime.now(timezone.utc).isoformat()))
    backend = CpuBackend(environment)

    def execute(prefix, plan):
        rows = []
        for name, items in batches(prefix, plan):
            write(run / f'{name}.attempt.json', items)
            result = generate(backend, items)
            write(run / f'{name}.record.json', result)
            rows.extend(result['records'])
            print(name, ', '.join(row['status'] for row in result['records']), round(result['seconds'], 2), flush=True)
        return rows

    first = execute('first', initial_plan(inputs))
    replies = first_replies(inputs, first)
    write(run / 'first-replies.json', replies)
    execute('follow', follow_plan(inputs['R06'], replies['R06']))
    write(run / 'seal.json', {path.name: local.hash_file(path) for path in sorted(run.iterdir())})


def verify(run):
    seal = read(run / 'seal.json')
    require(set(seal) | {'seal.json'} == {path.name for path in run.iterdir()}, 'sealed file set differs')
    require(all(local.hash_file(run / name) == sha for name, sha in seal.items()), 'sealed file bytes differ')
    rules, inputs = contract()
    manifest = read(run / 'manifest.json')
    require(all(manifest[key] == value for key, value in rules.items()), 'run contract differs')
    eos = manifest['environment']['eos_token_ids']
    tokenizer = local.load_tokenizer()
    seen = {'manifest.json', 'first-replies.json'}

    def replay(prefix, plan):
        rows = []
        for name, items in batches(prefix, plan):
            attempt, record = (f'{name}.{kind}.json' for kind in ('attempt', 'record'))
            seen.update((attempt, record))
            require(read(run / attempt) == items, 'attempt order or prompts differ')
            for item, row in zip(items, read(run / record)['records'], strict=True):
                require(all(row[key] == value for key, value in item.items()), 'record differs from attempt')
                text, ids = render(tokenizer, item['messages'])
                require((text, ids) == (row['rendered_prompt'], row['input_token_ids']), 'rendered input or IDs differ')
                tokens = row['generated_token_ids']
                require(0 < len(tokens) <= LIMIT and all(type(t) is int and 0 <= t < len(tokenizer) for t in tokens)
                        and not any(t in eos for t in tokens[:-1]) and (tokens[-1] in eos or len(tokens) == LIMIT),
                        'output IDs or EOS invalid')
                output = tokenizer.decode(tokens, skip_special_tokens=True)
                require(row['output'] == output and row['status'] == local.output_status(output, tokens, eos),
                        'decoded output or status differs')
                rows.append(row)
        return rows

    first = replay('first', initial_plan(inputs))
    replies = first_replies(inputs, first)
    require(replies == read(run / 'first-replies.json'), 'first replies differ')
    follow = replay('follow', follow_plan(inputs['R06'], replies['R06']))
    require(seen == set(seal), 'unexpected archive files')
    print(json.dumps({'first_records': len(first), 'follow_records': len(follow),
                      'input_tokens': sum(len(row['input_token_ids']) for row in first + follow),
                      'output_tokens': sum(len(row['generated_token_ids']) for row in first + follow),
                      'seal_sha256': local.hash_file(run / 'seal.json')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('collect', 'verify'))
    parser.add_argument('run', type=Path)
    options = parser.parse_args()
    {'collect': collect, 'verify': verify}[options.action](options.run)
