"""Collect and replay the two delegation routes with the pinned local CPU model."""
import argparse
from pathlib import Path
import time

import query_determinacy_delegation_paired as contract
import query_determinacy_shared_live as local


PACK = contract.PACK
REQUIRE = contract.require
THREADS = 16
BATCH_SIZE = 4
LIMITS = {'direct': 256, 'extract': 160}
GENERATION = {'device': 'cpu', 'dtype': 'float32', 'attention': 'sdpa', 'do_sample': False, 'num_beams': 1,
              'threads': THREADS, 'batch_size': BATCH_SIZE, 'max_new_tokens': LIMITS}


def digest(path):
    return local.hash_file(path)


def write(path, value):
    local.write_new(path, local.encode(value))


def public_plan(split):
    development_lock = PACK / 'development-freeze.json'
    material_lock = PACK / 'material-freeze.json'
    sources = contract.read(material_lock)
    REQUIRE(digest(development_lock) == sources[str(development_lock.relative_to(contract.ROOT))],
            'development lock changed')
    bindings = contract.read(development_lock) | sources
    case_path = PACK / f'{split}-cases.json'
    reference = PACK / f'{split}-reference.json'
    files = (case_path, PACK / 'prompts.json', PACK / 'decision.json', Path(contract.__file__),
             contract.ROOT / 'scripts/query_determinacy_delegation.py',
             contract.ROOT / 'scripts/query_determinacy_rule_applicability.py')
    for path in files:
        REQUIRE(digest(path) == bindings[str(path.relative_to(contract.ROOT))], f'frozen file changed: {path.name}')
    cases = contract.read(case_path)
    instructions = contract.read(PACK / 'prompts.json')
    policy = contract.read(PACK / 'decision.json')
    size = policy['development_roots' if split == 'dev' else 'heldout_roots'] * policy['variants_per_root']
    REQUIRE(len(cases) == size, 'public case count changed')
    sequence = [{'case': i, 'route': route, 'prompt': contract.prompt(cases[i], instructions, route)}
                for route in contract.ROUTES for i in sorted(cases)]
    manifest = {'split': split, 'generation': GENERATION, 'call_count': len(sequence),
                'public_sha256': digest(case_path), 'material_lock_sha256': digest(material_lock),
                'reference_sha256': bindings[str(reference.relative_to(contract.ROOT))],
                'code_sha256': {Path(p).name: digest(Path(p)) for p in (__file__, local.__file__, contract.__file__)}}
    return manifest, cases, policy, sequence


class CpuBackend:
    def __init__(self, environment):
        import torch
        from transformers import AutoModelForCausalLM, GenerationConfig

        torch.set_num_threads(THREADS)
        torch.set_num_interop_threads(1)
        self.torch = torch
        self.config = GenerationConfig
        self.eos = environment['eos_token_ids']
        self.context = environment['context_tokens']
        self.tokenizer = local.load_tokenizer()
        self.model = AutoModelForCausalLM.from_pretrained(
            str(local.MODEL), local_files_only=True, dtype=torch.float32,
            device_map={'': 'cpu'}, attn_implementation='sdpa').eval()
        self.model.requires_grad_(False)

    def generate(self, tasks):
        torch = self.torch
        rendered = [local.tokenize(self.tokenizer, task['prompt']) for task in tasks]
        width = max(len(ids) for _, ids in rendered)
        limit = LIMITS[tasks[0]['route']]
        REQUIRE(width + limit <= self.context and all(LIMITS[t['route']] == limit for t in tasks),
                'batch exceeds context or mixes route limits')
        pad = self.tokenizer.pad_token_id
        padded = [[pad] * (width - len(ids)) + ids for _, ids in rendered]
        masks = [[0] * (width - len(ids)) + [1] * len(ids) for _, ids in rendered]
        x = torch.tensor(padded, dtype=torch.long, device='cpu')
        cfg = self.config(max_new_tokens=limit, do_sample=False, num_beams=1, use_cache=True,
                          eos_token_id=self.eos, pad_token_id=pad,
                          bos_token_id=self.model.generation_config.bos_token_id)
        started = time.monotonic()
        with torch.inference_mode():
            sequence = self.model.generate(input_ids=x, attention_mask=torch.tensor(masks, device='cpu'),
                                           generation_config=cfg, logits_to_keep=1)
        elapsed = time.monotonic() - started
        REQUIRE(sequence[:, :width].tolist() == padded, 'model changed padded input prefix')
        records = []
        for task, (text, ids), suffix in zip(tasks, rendered, sequence[:, width:].tolist(), strict=True):
            stop = next((i + 1 for i, token in enumerate(suffix) if token in self.eos), len(suffix))
            REQUIRE(all(token == pad for token in suffix[stop:]), 'non-padding after first EOS')
            generated = suffix[:stop]
            output = self.tokenizer.decode(generated, skip_special_tokens=True)
            records.append(dict(task, rendered_prompt=text, input_token_ids=ids, generated_token_ids=generated,
                                output=output, status=local.output_status(output, generated, self.eos)))
        return records, elapsed


def collect(path, split, dev_run, backend_class=CpuBackend):
    frozen, _, _, plan = public_plan(split)
    dev_seal = None
    if split == 'heldout':
        REQUIRE(dev_run is not None, 'heldout requires a completed development run')
        result = score(dev_run, expected_split='dev')
        REQUIRE(result['interface_ready'], 'development interface check did not pass')
        dev_seal = result['seal_sha256']
    environment = local.environment_snapshot()
    if split == 'heldout':
        dev_manifest = contract.read(dev_run / 'manifest.json')
        REQUIRE(dev_manifest['environment'] == environment, 'model or runtime differs from development')
    path.mkdir(mode=0o700, parents=False)
    write(path / 'manifest.json', dict(frozen, environment=environment, development_seal_sha256=dev_seal))
    backend = backend_class(environment)
    for index in range(0, len(plan), BATCH_SIZE):
        tasks = plan[index:index + BATCH_SIZE]
        write(path / f'{index:04d}.attempt.json', tasks)
        records, seconds = backend.generate(tasks)
        REQUIRE(len(records) == len(tasks), 'unexpected number of model records')
        write(path / f'{index:04d}.record.json', {'seconds': seconds, 'records': records})
        print(f'{index + len(tasks)}/{len(plan)} {tasks[0]["route"]} '
              f'{"/".join(row["status"] for row in records)} {seconds:.2f}s', flush=True)
    paths = (path / 'manifest.json', *sorted(path.glob('*.attempt.json')), *sorted(path.glob('*.record.json')))
    write(path / 'seal.json', {file.name: digest(file) for file in paths})
    return digest(path / 'seal.json')


def verify(path, tokenizer=None):
    seal = contract.read(path / 'seal.json')
    run = contract.read(path / 'manifest.json')
    split = run['split']
    REQUIRE(split in ('dev', 'heldout'), 'invalid split in manifest')
    frozen, cases, policy, sequence = public_plan(split)
    REQUIRE(all(run[key] == value for key, value in frozen.items()), 'run contract differs')
    REQUIRE((split == 'heldout') == bool(run['development_seal_sha256']), 'missing development binding')
    offsets = range(0, len(sequence), BATCH_SIZE)
    expected = {'manifest.json', *(f'{i:04d}.{kind}.json' for i in offsets for kind in ('attempt', 'record'))}
    actual = {file.name for file in path.glob('*.attempt.json')} | {file.name for file in path.glob('*.record.json')}
    REQUIRE(set(seal) == actual | {'manifest.json'} == expected, 'incomplete or extra attempts/records')
    for name, value in seal.items():
        REQUIRE(digest(path / name) == value, f'sealed file changed: {name}')
    tokenizer = local.load_tokenizer() if tokenizer is None else tokenizer
    eos = run['environment']['eos_token_ids']
    rows = []
    for i in offsets:
        tasks = sequence[i:i + BATCH_SIZE]
        REQUIRE(contract.read(path / f'{i:04d}.attempt.json') == tasks, 'attempt order or prompts changed')
        batch = contract.read(path / f'{i:04d}.record.json')['records']
        for task, row in zip(tasks, batch, strict=True):
            REQUIRE(all(row[k] == v for k, v in task.items()), 'record identity or prompt changed')
            rendered, ids = local.tokenize(tokenizer, task['prompt'])
            REQUIRE(row['rendered_prompt'] == rendered and row['input_token_ids'] == ids, 'tokenized input differs')
            tokens = row['generated_token_ids']
            limit = LIMITS[task['route']]
            REQUIRE(0 < len(tokens) <= limit and not any(t in eos for t in tokens[:-1])
                    and (tokens[-1] in eos or len(tokens) == limit), 'invalid EOS or output token count')
            output = tokenizer.decode(tokens, skip_special_tokens=True)
            REQUIRE(row['output'] == output and row['status'] == local.output_status(output, tokens, eos),
                    'raw output or generation status differs')
            rows.append(row)
    return run, cases, policy, rows


def score(path, expected_split=None):
    run, cases, policy, records = verify(path)
    split = run['split']
    REQUIRE(expected_split in (None, split), 'wrong development split')
    path_to_ref = PACK / f'{split}-reference.json'
    REQUIRE(digest(path_to_ref) == run['reference_sha256'], 'reference changed since collection')
    refs = contract.read(path_to_ref)
    groups = contract.inspect_split(cases, refs, policy['development_roots' if split == 'dev' else 'heldout_roots'])
    rows = {route: {} for route in ('parser', *contract.ROUTES)}
    for row in records:
        case, route = row['case'], row['route']
        result = contract.judge(cases[case], refs[case], route, row['output'])
        if row['status'] != 'complete':
            result.update(status='invalid', correct_grounded=False, generation_status=row['status'])
        rows[route][case] = result
    rows['parser'] = {i: contract.judge(case, refs[i], 'parser') for i, case in cases.items()}
    summary = {route: contract.summarize(items, groups, refs) for route, items in rows.items()}
    result = {'split': split, 'seal_sha256': digest(path / 'seal.json'), 'summary': summary, 'rows': rows}
    if split == 'dev':
        result['interface_ready'] = all(not summary[r]['invalid'] for r in contract.ROUTES)
    else:
        result['comparison'] = {r: contract.compare(summary[r], summary['parser'], policy) for r in contract.ROUTES}
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('collect', 'verify', 'score'))
    cli.add_argument('--run', type=Path, required=True)
    cli.add_argument('--split', choices=('dev', 'heldout'), default='dev')
    cli.add_argument('--dev-run', type=Path)
    args = cli.parse_args()
    if args.action == 'collect':
        print(collect(args.run, args.split, args.dev_run))
    elif args.action == 'verify':
        run, _, _, rows = verify(args.run)
        print(local.encode({'split': run['split'], 'records': len(rows), 'seal_sha256': digest(args.run / 'seal.json')}).decode(),
              end='')
    else:
        print(local.encode(score(args.run)).decode(), end='')


if __name__ == '__main__':
    main()
