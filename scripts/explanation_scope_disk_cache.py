"""Read-only candidate cache inspection; never creates or repairs a run."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat

import explanation_scope_runtime as scope

ROOT = scope.ROOT
INPUT_FINGERPRINTS = ROOT / 'docs/review/2026-11-06-explanation-scope-runtime-preflight-v1/input-fingerprints.json'
DEFAULT_RUN = ROOT / 'runs/qwen2.5-3b-explanation-scope-v1'


def expected_manifest(runtime):
    return {'format': 'explanation-scope-cache-v1', 'plan_sha256': runtime.plan_sha,
            'input_fingerprints_sha256': hashlib.sha256(INPUT_FINGERPRINTS.read_bytes()).hexdigest()}


def _read(path):
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 8 * 1024 * 1024:
            raise ValueError('cache file is not a bounded regular file: ' + path.name)
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('cache file missing or unreadable: ' + path.name) from error


def inspect_cache(directory, runtime):
    root = Path(directory)
    if root.is_symlink():
        raise ValueError('cache root must not be a symlink')
    if not root.exists():
        return {'state': 'not_created', 'records': 0, 'collection_allowed': False,
                'gpu_launch_ready': False, 'writes_performed': False}
    if not root.is_dir():
        raise ValueError('cache root must be a directory')
    allowed = {'.lock', 'manifest.json', 'records.json', 'attempts', 'smoke.json', 'failure.json'}
    lock = root / '.lock'
    try:
        lock_info = lock.lstat()
        if not stat.S_ISREG(lock_info.st_mode):
            raise ValueError('cache lock must be a regular file')
        fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        raise ValueError('existing cache lock required; no file was created') from error
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('cache is locked by another process') from error
        opened_lock = os.fstat(fd)
        if (opened_lock.st_dev, opened_lock.st_ino) != (lock_info.st_dev, lock_info.st_ino):
            raise ValueError('cache lock changed while opening')
        entries = list(root.iterdir())
        if any(p.name not in allowed or p.is_symlink() for p in entries):
            raise ValueError('unknown, pending or symlink cache entry; preserve for inspection')
        if _read(root / 'manifest.json') != expected_manifest(runtime):
            raise ValueError('cache manifest differs from input and plan fingerprints')
        data = _read(root / 'records.json')
        if not isinstance(data, dict) or set(data) != {'plan_sha256', 'records'} or data['plan_sha256'] != runtime.plan_sha:
            raise ValueError('cache records header differs')
        directory_path = root / 'attempts'
        if directory_path.is_symlink() or not directory_path.is_dir():
            raise ValueError('attempt directory missing or invalid')
        markers = sorted(directory_path.iterdir())
        if any(path.name != f'{i:04d}.json' for i, path in enumerate(markers)):
            raise ValueError('attempt markers must be a strict ordered prefix')
        attempts = [_read(path) for path in markers]
        smoke = _read(root / 'smoke.json') if (root / 'smoke.json').exists() else None
        failure = _read(root / 'failure.json') if (root / 'failure.json').exists() else None
        result = runtime.validate_cache(attempts, data['records'], smoke, failure)
        result.update({'writes_performed': False, 'output_origin_verified': False,
                       'note': 'Read-only cache format; no production writer or collection authorization.'})
        return result
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def main():
    runtime = scope.Runtime()
    print(json.dumps(inspect_cache(DEFAULT_RUN, runtime), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
