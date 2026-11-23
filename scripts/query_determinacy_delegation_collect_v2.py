"""Replay the direct-format revision, keeping the first development seal intact."""
import argparse
from pathlib import Path

import query_determinacy_delegation_collect as first


contract = first.contract
local = first.local
revision_path = contract.ROOT / 'docs/review/2026-11-23-rule-applicability-live-v1/direct-format-v2.json'


def plan(split):
    base, cases, policy, tasks = first.public_plan(split)
    revision = contract.read(revision_path)
    selected = [dict(task, prompt=task['prompt'] + '\n' + revision['direct_suffix']) if task['route'] == 'direct' else task
                for task in tasks if split != 'dev' or task['route'] == 'direct']
    manifest = dict(base, call_count=len(selected), revision_sha256=first.digest(revision_path),
                    revision_code_sha256=first.digest(Path(__file__)))
    return manifest, cases, policy, selected


def verify(run):
    manifest = contract.read(run / 'manifest.json')
    split = manifest['split']
    first.REQUIRE(split in ('dev', 'heldout'), 'invalid revision split')
    frozen, cases, policy, tasks = plan(split)
    first.REQUIRE(all(manifest[k] == v for k, v in frozen.items()), 'revision manifest differs')
    offsets = range(0, len(tasks), first.BATCH_SIZE)
    seal = contract.read(run / 'seal.json')
    expected = {'manifest.json', *(f'{i:04d}.{kind}.json' for i in offsets for kind in ('attempt', 'record'))}
    current = {f.name for f in run.glob('*.attempt.json')} | {f.name for f in run.glob('*.record.json')}
    first.REQUIRE(set(seal) == current | {'manifest.json'} == expected, 'incomplete or extra attempts/records')
    for name, digest in seal.items():
        first.REQUIRE(first.digest(run / name) == digest, f'sealed file changed: {name}')
    tokenizer = local.load_tokenizer()
    eos = manifest['environment']['eos_token_ids']
    records = []
    for i in offsets:
        batch = tasks[i:i + first.BATCH_SIZE]
        first.REQUIRE(contract.read(run / f'{i:04d}.attempt.json') == batch, 'prompt or order changed')
        rows = contract.read(run / f'{i:04d}.record.json')['records']
        for task, row in zip(batch, rows, strict=True):
            first.REQUIRE(all(row[k] == v for k, v in task.items()), 'attempt and record differ')
            rendered, ids = local.tokenize(tokenizer, task['prompt'])
            first.REQUIRE((row['rendered_prompt'], row['input_token_ids']) == (rendered, ids), 'input token mismatch')
            tokens = row['generated_token_ids']
            limit = first.LIMITS[task['route']]
            first.REQUIRE(0 < len(tokens) <= limit and not any(t in eos for t in tokens[:-1])
                          and (tokens[-1] in eos or len(tokens) == limit), 'bad EOS or output length')
            decoded = tokenizer.decode(tokens, skip_special_tokens=True)
            first.REQUIRE(decoded == row['output'] and local.output_status(decoded, tokens, eos) == row['status'],
                          'output or completion status mismatch')
        records.extend(rows)
    return manifest, cases, policy, records


def initial_dev_result(path):
    result = first.score(path, expected_split='dev')
    revision = contract.read(revision_path)
    first.REQUIRE(result['seal_sha256'] == revision['dev_v1_seal_sha256'], 'wrong original development seal')
    first.REQUIRE(not result['summary']['extract']['invalid'], 'original extract interface failed')
    return result


def score(run, original_dev=None):
    manifest, cases, policy, records = verify(run)
    split = manifest['split']
    reference = contract.PACK / f'{split}-reference.json'
    first.REQUIRE(first.digest(reference) == manifest['reference_sha256'], 'reference changed after collection')
    refs = contract.read(reference)
    groups = contract.inspect_split(cases, refs, policy['development_roots' if split == 'dev' else 'heldout_roots'])
    rows = {r: {} for r in ('parser', *contract.ROUTES)}
    for row in records:
        case, route = row['case'], row['route']
        scored = contract.judge(cases[case], refs[case], route, row['output'])
        if row['status'] != 'complete':
            scored.update(status='invalid', correct_grounded=False, generation_status=row['status'])
        rows[route][case] = scored
    rows['parser'] = {i: contract.judge(case, refs[i], 'parser') for i, case in cases.items()}
    if split == 'dev':
        initial = initial_dev_result(original_dev)
        first.REQUIRE(manifest['original_dev_seal_sha256'] == initial['seal_sha256'], 'original cohort was replaced')
        rows['extract'] = initial['rows']['extract']
    summary = {r: contract.summarize(selected, groups, refs) for r, selected in rows.items()}
    result = {'split': split, 'seal_sha256': first.digest(run / 'seal.json'), 'rows': rows, 'summary': summary}
    if split == 'dev':
        result['interface_ready'] = all(not summary[r]['invalid'] for r in contract.ROUTES)
    else:
        result['comparison'] = {r: contract.compare(summary[r], summary['parser'], policy) for r in contract.ROUTES}
    return result


def collect(run, split, original_dev, revised_dev):
    initial = initial_dev_result(original_dev)
    dev_seal = None
    if split == 'heldout':
        first.REQUIRE(revised_dev is not None, 'heldout requires revised development check')
        check = score(revised_dev, original_dev)
        first.REQUIRE(check['split'] == 'dev' and check['interface_ready'], 'revised development interface failed')
        dev_seal = check['seal_sha256']
    manifest, _, _, tasks = plan(split)
    environment = local.environment_snapshot()
    passed = [original_dev] + ([revised_dev] if split == 'heldout' else [])
    first.REQUIRE(all(contract.read(p / 'manifest.json')['environment'] == environment for p in passed),
                  'model or runtime differs across development and heldout')
    run.mkdir(mode=0o700)
    first.write(run / 'manifest.json', dict(manifest, environment=environment,
                                          original_dev_seal_sha256=initial['seal_sha256'],
                                          revised_dev_seal_sha256=dev_seal))
    backend = first.CpuBackend(environment)
    for index in range(0, len(tasks), first.BATCH_SIZE):
        batch = tasks[index:index + first.BATCH_SIZE]
        first.write(run / f'{index:04d}.attempt.json', batch)
        rows, seconds = backend.generate(batch)
        first.REQUIRE(len(rows) == len(batch), 'unexpected number of model records')
        first.write(run / f'{index:04d}.record.json', {'seconds': seconds, 'records': rows})
        print(f'{index + len(rows)}/{len(tasks)} {batch[0]["route"]} '
              f'{"/".join(row["status"] for row in rows)} {seconds:.2f}s', flush=True)
    sources = (run / 'manifest.json', *sorted(run.glob('*.attempt.json')), *sorted(run.glob('*.record.json')))
    first.write(run / 'seal.json', {p.name: first.digest(p) for p in sources})
    return first.digest(run / 'seal.json')


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('collect', 'verify', 'score'))
    cli.add_argument('--run', type=Path, required=True)
    cli.add_argument('--split', choices=('dev', 'heldout'), default='dev')
    cli.add_argument('--original-dev', type=Path)
    cli.add_argument('--revised-dev', type=Path)
    args = cli.parse_args()
    if args.action == 'collect':
        print(collect(args.run, args.split, args.original_dev, args.revised_dev))
    elif args.action == 'verify':
        manifest, _, _, rows = verify(args.run)
        print(local.encode({'split': manifest['split'], 'records': len(rows),
                            'seal_sha256': first.digest(args.run / 'seal.json')}).decode(), end='')
    else:
        print(local.encode(score(args.run, args.original_dev)).decode(), end='')


if __name__ == '__main__':
    main()
