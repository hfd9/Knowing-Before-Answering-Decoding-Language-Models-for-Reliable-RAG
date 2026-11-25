"""Run role assignment on model rescoring after evidence label permutations."""
from pathlib import Path
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_role_assign as candidate

base = candidate.base
prior = base.prior
frozen = base.frozen
pilot = base.pilot
local = base.local
require = base.require


def fingerprints():
    paths = (Path(__file__), ROOT / 'scripts/query_determinacy_role_assign.py', ROOT / 'scripts/query_determinacy_typed_holdout.py',
             ROOT / 'scripts/query_determinacy_date_evidence_first.py', ROOT / 'scripts/query_determinacy_date_multi_pilot.py',
             ROOT / 'scripts/query_determinacy_date_pilot.py', ROOT / 'scripts/query_determinacy_shared_live.py',
             ROOT / 'scripts/query_determinacy_delegation_collect.py', ROOT / 'scripts/query_determinacy_threshold_versions.py',
             HERE / 'protocol.md', HERE / 'public.json', HERE / 'reference.json')
    return {str(path.relative_to(ROOT)): local.hash_file(path) for path in paths}


def collect(path):
    public = pilot.read(HERE / 'public.json')
    env = local.environment_snapshot()
    require(env == pilot.read(frozen.PACK / 'freeze.json')['environment'], 'model environment changed')
    path.mkdir(mode=0o700)
    pilot.write(path / 'manifest.json', {'sources': fingerprints(), 'environment': env})
    model = frozen.ChoiceBackend(env)

    def execute(phase, tasks):
        result = []
        for name, batch in prior.batches(phase, tasks):
            pilot.write(path / f'{name}.attempt.json', batch)
            rows, seconds = model.rank(batch)
            pilot.write(path / f'{name}.record.json', {'records': rows, 'seconds': seconds})
            result.extend(rows)
            print(name, len(result), '/', len(tasks), round(seconds, 2), flush=True)
        return result

    locations, failures = candidate.assign(public, execute('locate', frozen.locate_plan(public)))
    subset = {'profiles': {name: public['profiles'][name] for name in locations},
              'cases': [case for case in public['cases'] if case['profile'] in locations]}
    plan, _ = frozen.extract_plan(subset, locations)
    execute('extract', plan)
    pilot.write(path / 'seal.json', {f.name: local.hash_file(f) for f in sorted(path.iterdir())})
    print('Unresolved profiles:', failures, flush=True)


def verify(path):
    manifest, seal = (pilot.read(path / name) for name in ('manifest.json', 'seal.json'))
    require(manifest['sources'] == fingerprints(), 'source mismatch')
    require(set(seal) | {'seal.json'} == {file.name for file in path.iterdir()} and
            all(local.hash_file(path / name) == digest for name, digest in seal.items()), 'seal mismatch')
    public, reference = (pilot.read(HERE / f'{name}.json') for name in ('public', 'reference'))
    tokenizer = local.load_tokenizer()
    seen, costs = {'manifest.json'}, {}

    def phase(name, tasks):
        out, seconds = [], 0.0
        for prefix, batch in prior.batches(name, tasks):
            attempt, record = f'{prefix}.attempt.json', f'{prefix}.record.json'
            seen.update((attempt, record))
            require(pilot.read(path / attempt) == batch, 'attempt mismatch')
            data = pilot.read(path / record)
            seconds += data['seconds']
            for task, row in zip(batch, data['records'], strict=True):
                require(all(row[key] == val for key, val in task.items()) and
                        local.tokenize(tokenizer, row['prompt'])[1] == row['input_token_ids'], 'record mismatch')
                frozen.choice_scores(row)
                out.append(row)
        costs[name] = {'calls': len(out), 'seconds': round(seconds, 2),
                       'input_tokens': sum(len(row['input_token_ids']) for row in out)}
        return out

    locations, failures = candidate.assign(public, phase('locate', frozen.locate_plan(public)))
    subset = {'profiles': {name: public['profiles'][name] for name in locations},
              'cases': [case for case in public['cases'] if case['profile'] in locations]}
    tasks, groups = frozen.extract_plan(subset, locations)
    picks, conditions = frozen.extraction_picks(phase('extract', tasks), groups)
    require(seen == set(seal), 'extra run files')
    scored = frozen.judge(subset, reference, locations, picks)
    return {'costs': costs, 'locations': locations, 'failures': failures, 'conditions': conditions,
            'case_count': len(public['cases']), 'strict': sum(row['checks']['strict'] for row in scored.values()),
            'rows': scored, 'seal_sha256': local.hash_file(path / 'seal.json')}


if __name__ == '__main__':
    action = sys.argv[1]
    if action == 'collect':
        collect(Path(sys.argv[2]))
    elif action == 'archive':
        path = Path(sys.argv[2])
        result = verify(path)
        with ZipFile(HERE / 'live-raw.zip', 'x', ZIP_DEFLATED) as archive:
            for file in sorted(path.iterdir()):
                archive.write(file, file.name)
        pilot.write(HERE / 'live-results.json', result)
        print(local.encode({k: v for k, v in result.items() if k not in ('rows', 'conditions')}).decode(), end='')
    elif action == 'check':
        with tempfile.TemporaryDirectory(prefix='role-permutation-') as directory:
            with ZipFile(HERE / 'live-raw.zip') as archive:
                archive.extractall(directory)
            result = verify(Path(directory))
        require(result == pilot.read(HERE / 'live-results.json'), 'replay changed')
        print('Live model permutation replay passed.')
