"""Evaluate the frozen version-shape candidate and direct baseline on new rules."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

import query_determinacy_date_multi_pilot as prior


ROOT = prior.local.ROOT
PACK = ROOT / 'docs/review/2026-11-25-typed-holdout-v1'
sys.path.insert(0, str((ROOT / 'docs/review/2026-11-25-date-multi-rule-pilot-v1').resolve()))
from importlib.machinery import SourceFileLoader

diagnostic = SourceFileLoader('prior_version_diagnostic', str(
    ROOT / 'docs/review/2026-11-25-date-multi-rule-pilot-v1/version-diagnostic.py')).load_module()
frozen = prior.frozen
pilot = prior.pilot
local = prior.local
require = prior.require


def pick_per_rule(public, rows):
    locations, failures = {}, {}
    for name, profile in public['profiles'].items():
        subset = [row for row in rows if row['id'].startswith(name + '/')]
        try:
            locations.update(diagnostic.typed_locations({'profiles': {name: profile}}, subset))
        except ValueError as error:
            failures[name] = str(error)
    return locations, failures


def plan(public, locations):
    subset = {'profiles': {name: public['profiles'][name] for name in locations},
              'cases': [case for case in public['cases'] if case['profile'] in locations]}
    return frozen.extract_plan(subset, locations)


def contract():
    paths = [Path(__file__), Path(prior.__file__), Path(diagnostic.__file__), Path(frozen.__file__),
             ROOT / 'scripts/query_determinacy_threshold_versions.py',
             ROOT / 'scripts/query_determinacy_date_pilot.py', ROOT / 'scripts/query_determinacy_shared_live.py',
             ROOT / 'scripts/query_determinacy_delegation_collect.py', PACK / 'protocol.md']
    return {str(path.relative_to(ROOT)): local.hash_file(path) for path in paths}


def collect(run):
    lock = pilot.read(PACK / 'freeze.json')
    require(lock['contract'] == contract(), 'candidate changed after freeze')
    public, reference = (pilot.read(PACK / f'{name}.json') for name in ('public', 'reference'))
    material_hashes = {name: local.hash_file(PACK / name) for name in ('public.json', 'reference.json', 'sources.md')}
    environment = local.environment_snapshot()
    require(environment == pilot.read(frozen.PACK / 'freeze.json')['environment'], 'model environment differs')
    run.mkdir(mode=0o700)
    pilot.write(run / 'manifest.json', {'contract': lock['contract'], 'freeze': local.hash_file(PACK / 'freeze.json'),
                                       'materials': material_hashes, 'environment': environment,
                                       'utc': datetime.now(timezone.utc).isoformat()})
    backend = frozen.ChoiceBackend(environment)

    def execute(phase, tasks):
        rows = []
        for name, batch in prior.batches(phase, tasks):
            pilot.write(run / f'{name}.attempt.json', batch)
            if phase == 'direct':
                result = pilot.generate(backend, batch)
            else:
                recorded, seconds = backend.rank(batch)
                result = {'records': recorded, 'seconds': seconds}
            pilot.write(run / f'{name}.record.json', result)
            rows.extend(result['records'])
            print(name, len(rows), '/', len(tasks), round(result['seconds'], 2), flush=True)
        return rows

    located, _ = pick_per_rule(public, execute('locate', frozen.locate_plan(public)))
    tasks, _ = plan(public, located)
    execute('extract', tasks)
    execute('direct', prior.direct_plan(public, include_ablation=False))
    pilot.write(run / 'seal.json', {file.name: local.hash_file(file) for file in sorted(run.iterdir())})


def replay(run):
    lock = pilot.read(PACK / 'freeze.json')
    manifest = pilot.read(run / 'manifest.json')
    require(lock['contract'] == contract() == manifest['contract'], 'candidate source mismatch')
    require(manifest['freeze'] == local.hash_file(PACK / 'freeze.json'), 'candidate freeze mismatch')
    require(all(local.hash_file(PACK / name) == digest for name, digest in manifest['materials'].items()),
            'materials changed')
    seal = pilot.read(run / 'seal.json')
    require(set(seal) | {'seal.json'} == {file.name for file in run.iterdir()} and
            all(local.hash_file(run / name) == digest for name, digest in seal.items()), 'archive mismatch')
    public, reference = (pilot.read(PACK / f'{name}.json') for name in ('public', 'reference'))
    tokenizer = local.load_tokenizer()
    costs, seen = {}, {'manifest.json'}

    def verify(phase, tasks):
        rows, seconds = [], 0.0
        for name, batch in prior.batches(phase, tasks):
            attempt, record = f'{name}.attempt.json', f'{name}.record.json'
            seen.update((attempt, record))
            require(pilot.read(run / attempt) == batch, 'attempt differs')
            data = pilot.read(run / record)
            seconds += data['seconds']
            for task, row in zip(batch, data['records'], strict=True):
                require(all(row[key] == value for key, value in task.items()), 'task mismatch')
                if phase == 'direct':
                    text, ids = pilot.render(tokenizer, task['messages'])
                    tokens = row['generated_token_ids']
                    eos = manifest['environment']['eos_token_ids']
                    require(text == row['rendered_prompt'] and 0 < len(tokens) <= pilot.LIMIT and
                            not any(token in eos for token in tokens[:-1]) and
                            (tokens[-1] in eos or len(tokens) == pilot.LIMIT), 'invalid completion')
                    output = tokenizer.decode(tokens, skip_special_tokens=True)
                    require(output == row['output'] and row['status'] == local.output_status(output, tokens, eos),
                            'decoded answer mismatch')
                else:
                    ids = local.tokenize(tokenizer, task['prompt'])[1]
                    frozen.choice_scores(row)
                require(ids == row['input_token_ids'], 'input token mismatch')
                rows.append(row)
        costs[phase] = {'calls': len(rows), 'seconds': round(seconds, 2),
                        'input_tokens': sum(len(row['input_token_ids']) for row in rows),
                        'output_tokens': sum(len(row.get('generated_token_ids', [])) for row in rows)}
        return rows

    located, failures = pick_per_rule(public, verify('locate', frozen.locate_plan(public)))
    tasks, groups = plan(public, located)
    picks, conditions = frozen.extraction_picks(verify('extract', tasks), groups)
    direct = verify('direct', prior.direct_plan(public, include_ablation=False))
    require(seen == set(seal), 'unplanned run files')
    subset = {'profiles': {name: public['profiles'][name] for name in located},
              'cases': [case for case in public['cases'] if case['profile'] in located]}
    computed = frozen.judge(subset, reference, located, picks)
    outputs = {(row['case']): prior.direct_row(row, reference['cases'][row['case']]['outcome']) for row in direct}
    cases = {}
    for case in public['cases']:
        identity, name = case['id'], case['profile']
        gold = reference['cases'][identity]
        if name in failures:
            result = {'tag': 'UNRESOLVED', 'branches': [], 'ask_event': None, 'reason': 'version_shape_ambiguous'}
            errors, fields = failures[name], None
        else:
            result, errors, fields = (computed[identity][key] for key in ('outcome', 'error', 'fields'))
        tag = (result or {}).get('tag')
        candidate = {'tag': tag, 'outcome': result, 'error': errors, 'fields': fields,
                     'checks': prior.outcome_checks(result, tag, gold['outcome'])}
        cases[identity] = {'category': gold['category'], 'rule': name, 'reference': gold['outcome'],
                           'direct': outputs[identity], 'candidate': candidate}
    summaries = {route: prior.summarize([(row['category'], row[route]) for row in cases.values()])
                 for route in ('direct', 'candidate')}
    by_rule = {name: {route: prior.summarize([(row['category'], row[route]) for row in cases.values()
                                               if row['rule'] == name]) for route in summaries}
               for name in public['profiles']}
    return {'seal_sha256': local.hash_file(run / 'seal.json'), 'locations': located, 'failures': failures,
            'scope_conditions': conditions, 'costs': costs, 'summaries': summaries, 'by_rule': by_rule, 'cases': cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'collect', 'archive', 'check'))
    parser.add_argument('run', type=Path, nargs='?')
    args = parser.parse_args()
    if args.action == 'freeze':
        frozen.verify_freeze()
        pilot.write(PACK / 'freeze.json', {'contract': contract(), 'utc': datetime.now(timezone.utc).isoformat()})
    elif args.action == 'collect':
        collect(args.run)
    elif args.action == 'archive':
        result = replay(args.run)
        with ZipFile(PACK / 'raw.zip', 'x', ZIP_DEFLATED) as archive:
            for path in sorted(args.run.iterdir()):
                archive.write(path, path.name)
        pilot.write(PACK / 'results.json', result)
        print(local.encode({'summaries': result['summaries'], 'failures': result['failures'],
                            'costs': result['costs']}).decode(), end='')
    else:
        with tempfile.TemporaryDirectory(prefix='typed-holdout-') as temp:
            with ZipFile(PACK / 'raw.zip') as archive:
                archive.extractall(temp)
            require(replay(Path(temp)) == pilot.read(PACK / 'results.json'), 'replay differs')
        print('Heldout archive replayed successfully.')


if __name__ == '__main__':
    main()
