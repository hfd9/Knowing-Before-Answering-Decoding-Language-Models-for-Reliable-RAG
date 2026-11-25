"""Replay the earlier version-shape baseline against the same recorded model choices."""
from pathlib import Path
import json
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_typed_holdout as old

pilot = old.pilot
frozen = old.frozen
prior = old.prior
local = old.local
require = old.require


def run():
    public, reference, new = (pilot.read(HERE / f'{name}.json') for name in ('public', 'reference', 'results'))
    with ZipFile(HERE / 'raw.zip') as z:
        def rows(prefix):
            return [row for name in sorted(z.namelist()) if name.startswith(prefix) and name.endswith('.record.json')
                    for row in json.loads(z.read(name))['records']]
        located, failures = old.pick_per_rule(public, rows('locate'))
        saved = rows('extract')
    require(all(new['locations'].get(name) == value for name, value in located.items()),
            'old and new select different roles; saved range scores cannot be reused')
    tasks, groups = old.plan(public, located)
    selected = {row['id']: row for row in saved}
    matched = []
    for task in tasks:
        row = selected[task['id']]
        require(all(row[key] == value for key, value in task.items()), 'range prompt differs')
        matched.append(row)
    picks, _ = frozen.extraction_picks(matched, groups)
    subset = {'profiles': {name: public['profiles'][name] for name in located},
              'cases': [case for case in public['cases'] if case['profile'] in located]}
    scored = frozen.judge(subset, reference, located, picks)
    cases = {}
    for item in public['cases']:
        identity, name = item['id'], item['profile']
        gold = reference['cases'][identity]
        if name in failures:
            outcome = {'tag': 'UNRESOLVED', 'branches': [], 'ask_event': None, 'reason': 'version_shape_ambiguous'}
        else:
            outcome = scored[identity]['outcome']
        tag = (outcome or {}).get('tag')
        cases[identity] = {'profile': name, 'category': gold['category'], 'outcome': outcome, 'tag': tag,
                           'checks': prior.outcome_checks(outcome, tag, gold['outcome'])}
    total = prior.summarize([(row['category'], row) for row in cases.values()])
    by_profile = {name: prior.summarize([(row['category'], row) for row in cases.values() if row['profile'] == name])
                  for name in public['profiles']}
    return {'main_archive_sha256': local.hash_file(HERE / 'raw.zip'), 'sources': {
        str(Path(__file__).relative_to(ROOT)): local.hash_file(Path(__file__)),
        str(Path(old.__file__).relative_to(ROOT)): local.hash_file(Path(old.__file__))},
        'locations': located, 'failures': failures, 'reused_choices': len(matched), 'summary': total,
        'by_profile': by_profile, 'cases': cases}


if __name__ == '__main__':
    encoded = local.encode(run())
    if '--verify' in sys.argv:
        assert encoded == (HERE / 'old-baseline.json').read_bytes(), 'comparison differs'
        print('Old baseline replay passed.')
    else:
        print(encoded.decode(), end='')
