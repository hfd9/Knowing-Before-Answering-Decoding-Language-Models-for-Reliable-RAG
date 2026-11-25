"""Post-hoc replace the two reversed SSA role assignments and capture missing choices."""
from pathlib import Path
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_role_assign as candidate

base = candidate.base
prior, frozen, pilot, local = base.prior, base.frozen, base.pilot, base.local
require = base.require


def initial(run):
    public = pilot.read(HERE / 'public.json')
    locations = [row for path in sorted(run.glob('locate-*.record.json')) for row in pilot.read(path)['records']]
    saved = [row for path in sorted(run.glob('extract-*.record.json')) for row in pilot.read(path)['records']]
    actual, failures = candidate.assign(public, locations)
    require(not failures, 'unexpected missing profile')
    repaired = {key: value.copy() for key, value in actual.items()}
    for name in ('ssa', 'ssa_overlap'):
        roles = repaired[name]
        roles['rule'], roles['scope'] = roles['scope'], roles['rule']
    tasks, groups = frozen.extract_plan(public, repaired)
    available = {row['id']: row for row in saved}
    reused, needed = {}, []
    for task in tasks:
        row = available.get(task['id'])
        if row is not None and all(row.get(key) == value for key, value in task.items()):
            reused[task['id']] = row
        else:
            needed.append(task)
    source_hashes = {file.name: local.hash_file(file) for prefix in ('locate-', 'extract-')
                     for file in sorted(run.glob(prefix + '*.record.json'))}
    return public, actual, repaired, groups, reused, needed, source_hashes


def collect(original, run):
    _, actual, repaired, _, _, tasks, sources = initial(original)
    env = local.environment_snapshot()
    require(env == pilot.read(frozen.PACK / 'freeze.json')['environment'], 'model environment changed')
    run.mkdir(mode=0o700)
    pilot.write(run / 'manifest.json', {'code_sha256': local.hash_file(Path(__file__)), 'sources': sources,
                                      'actual': actual, 'repaired': repaired, 'tasks': tasks, 'environment': env})
    model = frozen.ChoiceBackend(env)
    for name, batch in prior.batches('extract', tasks):
        pilot.write(run / f'{name}.attempt.json', batch)
        rows, seconds = model.rank(batch)
        pilot.write(run / f'{name}.record.json', {'records': rows, 'seconds': seconds})
        print(name, len(rows), round(seconds, 2), flush=True)
    pilot.write(run / 'seal.json', {f.name: local.hash_file(f) for f in sorted(run.iterdir())})


def verify(original, run):
    public, actual, repaired, groups, reused, tasks, sources = initial(original)
    manifest, seal = (pilot.read(run / name) for name in ('manifest.json', 'seal.json'))
    require(manifest['code_sha256'] == local.hash_file(Path(__file__)) and manifest['sources'] == sources and
            manifest['actual'] == actual and manifest['repaired'] == repaired and manifest['tasks'] == tasks,
            'intervention sources changed')
    require(set(seal) | {'seal.json'} == {f.name for f in run.iterdir()} and
            all(local.hash_file(run / name) == sha for name, sha in seal.items()), 'intervention seal changed')
    tokenizer = local.load_tokenizer()
    additions, seconds, seen = [], 0.0, {'manifest.json'}
    for name, batch in prior.batches('extract', tasks):
        attempt, record = f'{name}.attempt.json', f'{name}.record.json'
        seen.update((attempt, record))
        require(pilot.read(run / attempt) == batch, 'attempt changed')
        data = pilot.read(run / record)
        seconds += data['seconds']
        for task, row in zip(batch, data['records'], strict=True):
            require(all(row[key] == val for key, val in task.items()) and
                    local.tokenize(tokenizer, row['prompt'])[1] == row['input_token_ids'], 'record changed')
            frozen.choice_scores(row)
            additions.append(row)
    require(seen == set(seal), 'unplanned files')
    picked, conditions = frozen.extraction_picks([*reused.values(), *additions], groups)
    reference = pilot.read(HERE / 'reference.json')
    scored = frozen.judge(public, reference, repaired, picked)
    return {'actual': actual, 'repaired': repaired, 'scope_conditions': conditions,
            'reused_choices': len(reused), 'new_choices': len(additions), 'seconds': round(seconds, 2),
            'input_tokens': sum(len(row['input_token_ids']) for row in additions),
            'strict': sum(row['checks']['strict'] for row in scored.values()), 'cases': len(scored), 'rows': scored}


if __name__ == '__main__':
    action, original = sys.argv[1], Path(sys.argv[2])
    if action == 'collect':
        collect(original, Path(sys.argv[3]))
    elif action == 'archive':
        run = Path(sys.argv[3])
        result = verify(original, run)
        with ZipFile(HERE / 'intervention-raw.zip', 'x', ZIP_DEFLATED) as archive:
            for file in sorted(run.iterdir()):
                archive.write(file, file.name)
        pilot.write(HERE / 'intervention-results.json', result)
        print('Strict', result['strict'], '/', result['cases'], 'new choices', result['new_choices'])
    elif action == 'check':
        with tempfile.TemporaryDirectory(prefix='role-intervention-') as directory:
            with ZipFile(HERE / 'intervention-raw.zip') as archive:
                archive.extractall(directory)
            result = verify(original, Path(directory))
        require(result == pilot.read(HERE / 'intervention-results.json'), 'intervention replay mismatch')
        print('Role intervention replay passed.')
