"""Post-pilot diagnostic that constrains version roles before using saved scores."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'scripts'))

import query_determinacy_date_multi_pilot as main


frozen = main.frozen
pilot = main.pilot
local = main.local


def typed_locations(public, saved):
    """A version candidate must carry two coverage dates and one whole-dollar amount."""
    scores = {row['id']: frozen.choice_scores(row) for row in saved}
    located = {}
    for name, profile in public['profiles'].items():
        versions = []
        for tag, text in profile['evidence'].items():
            days = frozen.parse_days(text)
            if len(days) == 2 and days[0] <= days[1]:
                try:
                    frozen.amount(text)
                except ValueError:
                    continue
                versions.append((days, tag))
        versions.sort()
        main.require(len(versions) == 2 and versions[0][0][-1] < versions[1][0][0], 'version shape ambiguous')
        earlier, later = [tag for _, tag in versions]
        first, second = sorted(set(profile['evidence']) - {earlier, later})
        compare, scope = (scores[f'{name}/{role}'] for role in ('rule', 'scope'))
        forward, reverse = compare[first] + scope[second], compare[second] + scope[first]
        main.require(forward != reverse, 'comparison and scope candidates tie')
        rule_id, scope_id = (first, second) if forward > reverse else (second, first)
        located[name] = {'earlier': earlier, 'later': later, 'rule': rule_id, 'scope': scope_id}
    return located


def input_plan(primary):
    public, reference, lock = main.package()
    manifest = pilot.read(primary / 'manifest.json')
    main.require(manifest['hashes'] == lock['hashes'], 'wrong upstream study')
    origin = {}

    def phase_rows(phase):
        rows = []
        for path in sorted(primary.glob(f'{phase}-*.record.json')):
            origin[path.name] = local.hash_file(path)
            rows.extend(pilot.read(path)['records'])
        return rows

    locations = phase_rows('locate')
    primary_located = frozen.selections(public, locations)
    primary_tasks, primary_groups = frozen.extract_plan(public, primary_located)
    observed = phase_rows('extract')
    main.require(all(all(row[key] == value for key, value in task.items())
                     for row, task in zip(observed, primary_tasks, strict=True)), 'wrong upstream prompt sequence')
    primary_picks, _ = frozen.extraction_picks(observed, primary_groups)
    candidate = typed_locations(public, locations)
    tasks, groups = frozen.extract_plan(public, candidate)
    old = {row['id']: row for row in observed}
    reused, needed = {}, []
    for task in tasks:
        row = old.get(task['id'])
        if row is not None and all(row[key] == value for key, value in task.items()):
            reused[task['id']] = row
        else:
            needed.append(task)
    return public, reference, origin, primary_located, primary_picks, candidate, groups, reused, needed


def score(primary, supplemental):
    public, reference, origin, old, old_picks, candidate, groups, reused, needed = input_plan(primary)
    expected = pilot.read(supplemental / 'manifest.json')
    main.require(expected['origin'] == origin and expected['plan'] == needed and
                 expected['diagnostic_sha256'] == local.hash_file(Path(__file__)), 'diagnostic inputs changed')
    seal = pilot.read(supplemental / 'seal.json')
    main.require(set(seal) | {'seal.json'} == {path.name for path in supplemental.iterdir()} and
                 all(local.hash_file(supplemental / name) == sha for name, sha in seal.items()), 'archive bytes changed')
    tokenizer = local.load_tokenizer()
    model_rows = []
    seconds = 0.0
    for name, tasks in main.batches('extract', needed):
        batch = pilot.read(supplemental / f'{name}.record.json')
        seconds += batch['seconds']
        for task, row in zip(tasks, batch['records'], strict=True):
            main.require(all(row[key] == value for key, value in task.items()) and
                         row['input_token_ids'] == local.tokenize(tokenizer, row['prompt'])[1], 'diagnostic prompt changed')
            frozen.choice_scores(row)
            model_rows.append(row)
    picks, conditions = frozen.extraction_picks([*reused.values(), *model_rows], groups)
    original = frozen.judge(public, reference, old, old_picks)
    relocalized_only = frozen.judge(public, reference, candidate, old_picks)
    repaired = frozen.judge(public, reference, candidate, picks)
    results = {case: {'original_error': original[case]['error'], 'original': original[case]['checks']['strict'],
                      'with_only_new_location': relocalized_only[case]['checks']['strict'],
                      'after': row['checks']['strict'], 'field_checks': row['field_checks'],
                      'outcome': row['outcome'], 'expected': row['expected'], 'error': row['error']}
               for case, row in repaired.items()}
    return {'phase': 'posthoc_on_exposed_rules', 'origin': origin, 'original_locations': old, 'locations': candidate,
            'scope_conditions': conditions, 'cases': results, 'reused_choices': len(reused),
            'new_choices': len(model_rows), 'input_tokens': sum(len(row['input_token_ids']) for row in model_rows),
            'seconds': round(seconds, 2), 'strict': sum(row['after'] for row in results.values())}


def main_cli():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('collect', 'archive', 'check-archive'))
    cli.add_argument('primary', type=Path)
    cli.add_argument('supplemental', nargs='?', type=Path)
    args = cli.parse_args()
    if args.action == 'collect':
        _, _, origin, _, _, _, _, _, needed = input_plan(args.primary)
        environment = local.environment_snapshot()
        main.require(environment == pilot.read(frozen.PACK / 'freeze.json')['environment'], 'runtime changed')
        run = args.supplemental
        run.mkdir(mode=0o700)
        pilot.write(run / 'manifest.json', {'origin': origin, 'plan': needed, 'environment': environment,
                                            'diagnostic_sha256': local.hash_file(Path(__file__)),
                                            'utc': datetime.now(timezone.utc).isoformat()})
        backend = frozen.ChoiceBackend(environment)
        for name, tasks in main.batches('extract', needed):
            rows, elapsed = backend.rank(tasks)
            pilot.write(run / f'{name}.record.json', {'records': rows, 'seconds': elapsed})
            print(name, len(rows), round(elapsed, 2), flush=True)
        pilot.write(run / 'seal.json', {path.name: local.hash_file(path) for path in sorted(run.iterdir())})
    elif args.action == 'archive':
        result = score(args.primary, args.supplemental)
        with ZipFile(HERE / 'version-diagnostic-raw.zip', 'x', ZIP_DEFLATED) as zipped:
            for path in sorted(args.supplemental.iterdir()):
                zipped.write(path, path.name)
        pilot.write(HERE / 'version-diagnostic.json', result)
        print(result['strict'], '/', len(result['cases']))
    else:
        with tempfile.TemporaryDirectory(prefix='kba-date-version-replay-') as work:
            with ZipFile(HERE / 'version-diagnostic-raw.zip') as zipped:
                zipped.extractall(work)
            result = score(args.primary, Path(work))
        main.require(result == pilot.read(HERE / 'version-diagnostic.json'), 'diagnostic scores changed')
        print('Version diagnostic replayed.')


if __name__ == '__main__':
    main_cli()
