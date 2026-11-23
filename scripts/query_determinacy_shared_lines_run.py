#!/usr/bin/env python3
"""Run the fixed two-case line-output rerun under the user GPU release."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import query_determinacy_shared_live as base
import query_determinacy_shared_lines as lines

ROOT = base.ROOT
FOLDER = ROOT / 'docs/review/2026-11-23-shared-lines-release-v1'
RELEASE = FOLDER / 'release.json'
RUN = ROOT / 'runs/qwen2.5-3b-query-determinacy-shared-lines-pilot-v1'
CONTRACT = ROOT / 'docs/review/2026-11-23-shared-pilot-results-v1/simplified-output-contract.md'
SCORER = ROOT / 'scripts/query_determinacy_shared_lines_score.py'
MODE = 'two_case_shared_lines_pilot_v1'
TECHNICAL = {'technical_failure', 'empty', 'truncated'}


def release_files():
    files = (Path(__file__), Path(lines.__file__), Path(base.__file__), Path(base.extract.__file__),
             base.SCORER, base.CONTRACT, SCORER, CONTRACT, base.PILOT_PUBLIC, base.MODEL_REFERENCE,
             ROOT / 'shared_lines_pilot.sh')
    return {str(p.resolve().relative_to(ROOT)): base.hash_file(p) for p in files}


def release_config():
    raw = RELEASE.read_bytes()
    release = json.loads(raw)
    if (release.get('schema') != MODE or release.get('executor') != 'user'
            or release.get('collection_allowed') is not True or release.get('slots') != base.PILOT_SLOTS
            or release.get('case_ids') != base.PILOT_CASES or release.get('files_sha256') != release_files()):
        raise ValueError('line-output release or its bound files changed')
    public = json.loads(base.PILOT_PUBLIC.read_bytes())
    cases = base.validate_public(public)
    if [case['id'] for case in cases] != base.PILOT_CASES or len(base.slots(public)) != base.PILOT_SLOTS:
        raise ValueError('unexpected public schedule')
    extra = {'mode': MODE, 'release_sha256': base.sha(raw), 'environment': release['environment'],
             'evidence_map': {case['id']: lines.evidence_map(case) for case in cases}}
    return release, public, extra


def validate_path(run):
    if run != RUN or run.is_symlink() or run.parent.resolve() != RUN.parent:
        raise ValueError('expected the fixed line-output run directory')


def prepare(run):
    validate_path(run)
    _, public, extra = release_config()
    return base.init_run(run, public, extra)


def new_record(attempt_path, expected, backend):
    base.write_new(attempt_path, base.encode(expected))
    started = time.monotonic()
    text = expected['prompt']
    if text is None:
        result = {'status': 'skipped_extract', 'output': '', 'input_tokens': None, 'output_tokens': None}
    else:
        try:
            result = backend(text, expected)
            if result['status'] not in TECHNICAL | {'complete'} or not isinstance(result['output'], str):
                raise ValueError('invalid generation envelope')
        except Exception as error:
            result = {'status': 'technical_failure', 'output': '', 'input_tokens': None,
                      'output_tokens': None, 'error': f'{type(error).__name__}: {error}'}
    result.update(index=expected['index'], attempt_sha256=base.hash_file(attempt_path),
                  elapsed_seconds=time.monotonic() - started, completed_at=datetime.now(timezone.utc).isoformat(),
                  output_sha256=base.sha(result['output'].encode()))
    for field in ('input_token_ids', 'generated_token_ids'):
        if field in result:
            result[field + '_sha256'] = base.sha(base.encode(result[field]))
    return result


def check_record(record, attempt_path, expected, tokenizer, environment):
    raw = record.get('output')
    seconds = record.get('elapsed_seconds')
    status = record.get('status')
    if (record.get('index') != expected['index'] or record.get('attempt_sha256') != base.hash_file(attempt_path)
            or not isinstance(raw, str) or record.get('output_sha256') != base.sha(raw.encode())
            or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0):
        raise ValueError('record identity, output digest or duration mismatch')
    if expected['prompt'] is None:
        if status != 'skipped_extract' or raw or any(record.get(key) is not None for key in ('input_tokens', 'output_tokens')):
            raise ValueError('invalid skipped record')
        return
    if status not in TECHNICAL | {'complete'}:
        raise ValueError('invalid backend status')
    if status != 'technical_failure':
        for field in ('input_token_ids', 'generated_token_ids'):
            if record.get(field + '_sha256') != base.sha(base.encode(record.get(field))):
                raise ValueError('token digest mismatch')
        base.verify_tokens(tokenizer, expected['prompt'], record, environment)


def collect_backend(run, environment, manifest_hash, count):
    if base.environment_snapshot() != environment:
        raise ValueError('runtime environment differs from release')
    device = base.verify_device()
    index = base.check_preflights(run, manifest_hash, count)
    base.write_new(run / 'preflights' / f'{index:04d}.json', base.encode(
        {'device': device, 'starting_slot': count, 'checked_at': datetime.now(timezone.utc).isoformat(),
         'manifest_sha256': manifest_hash}))
    return base.QwenBackend()


def process(run, *, collect=False):
    """Rebuild the prefix and optionally emit remaining slots, all under one lock."""
    validate_path(run)
    release, frozen_public, extra = release_config()
    with base.locked(run):
        manifest, public = base.load_run(run)
        if public != frozen_public or manifest['extra'] != extra:
            raise ValueError('manifest does not match the line-output release')
        sequence = base.slots(public)
        attempts = sorted((run / 'attempts').iterdir())
        records = sorted((run / 'records').iterdir())
        if len(attempts) != len(records) or len(records) > len(sequence):
            raise ValueError('unfinished or extra attempt. Preserve the journal')
        manifest_hash = base.hash_file(run / 'manifest.json')
        base.check_preflights(run, manifest_hash, len(records))
        environment = release['environment']
        tokenizer = base.load_tokenizer() if records else None
        entries, extracted = [], {}
        backend = None
        blocked = False

        for index, (case, question, kind, branch) in enumerate(sequence):
            if blocked and index < len(records):
                raise ValueError('record follows a terminal technical failure')
            if index >= len(records) and (not collect or blocked):
                break
            name = f'{index:04d}.json'
            attempt_path = run / 'attempts' / name
            record_path = run / 'records' / name
            values = extracted.get(case['id'], {}).get('values')
            skip = kind in ('joint', 'branch') and values is None
            prompt = None if skip else lines.prompt(kind, case, question, values, branch)
            expected = {'index': index, 'case': case['id'], 'question': question['id'] if question else None,
                        'kind': kind, 'branch': branch, 'prompt': prompt,
                        'prompt_sha256': base.sha(prompt.encode()) if prompt is not None else None,
                        'manifest_sha256': manifest_hash}
            if index < len(records):
                if (attempts[index] != attempt_path or records[index] != record_path
                        or attempt_path.is_symlink() or record_path.is_symlink()
                        or json.loads(attempt_path.read_bytes()) != expected):
                    raise ValueError('journal attempt differs from the scheduled prompt')
                record = json.loads(record_path.read_bytes())
                check_record(record, attempt_path, expected, tokenizer, environment)
            else:
                if backend is None:
                    backend = collect_backend(run, environment, manifest_hash, index)
                    tokenizer = backend.tok
                record = new_record(attempt_path, expected, backend)
                base.write_new(record_path, base.encode(record))
                check_record(record, attempt_path, expected, tokenizer, environment)
                print(f'{index + 1}/{len(sequence)} {case["id"]} {kind}: {record["status"]}', flush=True)

            if kind == 'extract':
                extracted[case['id']] = base.extract.parse(record['output'], case['domain'], record['status'] == 'complete')
            blocked = record['status'] in TECHNICAL
            entries.append({'attempt': expected, 'record': record})

        state = {'manifest': manifest, 'public': public, 'entries': entries, 'blocked': blocked,
                 'count': len(entries), 'total': len(sequence),
                 'device_preflights': [json.loads(p.read_bytes()) for p in sorted((run/'preflights').iterdir())]}
        if collect and blocked:
            raise ValueError('technical failure preserved. Report the error for CPU review')
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('prepare', 'inspect', 'collect'))
    parser.add_argument('--user-executed', action='store_true')
    args = parser.parse_args()
    try:
        if args.stage != 'inspect' and not args.user_executed:
            raise ValueError('GPU pilot requires --user-executed')
        if args.stage == 'prepare':
            prepare(RUN)
            print(f'Prepared {base.PILOT_SLOTS} slots.')
            return
        state = process(RUN, collect=args.stage == 'collect')
        print(json.dumps({key: state[key] for key in ('count', 'total', 'blocked')}))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f'STOP: {error}. Keep the run directory and report the error.', file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == '__main__':
    main()
