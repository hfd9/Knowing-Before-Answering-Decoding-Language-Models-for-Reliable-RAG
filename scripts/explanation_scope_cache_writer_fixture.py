"""Temporary synthetic writer for the candidate disk-cache format; no model collection."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import tempfile

import explanation_scope_disk_cache as disk
import explanation_scope_ledger_simulator as plan_loader
import explanation_scope_transaction_prototype as transaction


class FixtureCacheWriter:
    """Real file transactions, but only under a temporary directory and with fixture data."""

    def __init__(self, directory, runtime):
        root = Path(directory)
        if root.is_symlink() or not root.is_dir():
            raise transaction.JournalBlocked('fixture root must be an existing non-symlink directory')
        self.root = root.resolve(strict=True)
        temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
        if self.root == temp_root or not self.root.is_relative_to(temp_root):
            raise transaction.JournalBlocked('fixture writer restricted to a temporary subdirectory')
        self.runtime = runtime
        _, plan_sha = plan_loader.load_plan()
        if runtime.plan_sha != plan_sha:
            raise transaction.JournalBlocked('runtime plan changed')
        self._locked = False
        self._pid = None
        self._owned = None
        self._lock_fd = None
        self._poisoned = False

    @classmethod
    def production(cls, runtime):
        # The frozen plan has no collection authority; no path or file is touched.
        runtime.assert_collection_disabled()
        raise AssertionError('unreachable under the frozen no-collection plan')

    @contextmanager
    def locked(self):
        if self._locked:
            raise transaction.JournalBlocked('lock already held')
        fd = os.open(self.root / '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise transaction.JournalBlocked('lock must be a regular file')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise transaction.JournalBlocked('cache is locked') from error
            self._locked, self._pid, self._owned = True, os.getpid(), None
            self._lock_fd, self._poisoned = fd, False
            self._require_lock()
            yield self
        finally:
            if self._locked and self._pid == os.getpid():
                self._locked, self._pid, self._owned = False, None, None
                self._lock_fd = None
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _require_lock(self):
        if not self._locked or self._pid != os.getpid():
            raise transaction.JournalBlocked('current-process lock required')
        if self._poisoned:
            raise transaction.JournalBlocked('transaction error; close lock and inspect cache')
        try:
            opened = os.fstat(self._lock_fd)
            current = (self.root / '.lock').lstat()
            if not stat.S_ISREG(current.st_mode) or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise transaction.JournalBlocked('lock file changed during lock session')
        except OSError as error:
            raise transaction.JournalBlocked('lock file missing or invalid') from error
        _, plan_sha = plan_loader.load_plan()
        if plan_sha != self.runtime.plan_sha:
            raise transaction.JournalBlocked('bound plan changed')

    def initialize(self):
        self._require_lock()
        if {p.name for p in self.root.iterdir()} != {'.lock'}:
            raise transaction.JournalBlocked('fixture directory is not empty')
        try:
            (self.root / 'attempts').mkdir(mode=0o700)
            transaction._fsync_dir(self.root)
            transaction._exclusive(self.root / 'manifest.json', disk.expected_manifest(self.runtime, synthetic_fixture=True))
            transaction._exclusive(self.root / 'records.json', {'plan_sha256': self.runtime.plan_sha, 'records': []})
        except BaseException:
            self._poisoned = True
            raise

    def _load(self):
        self._require_lock()
        allowed = {'.lock', 'manifest.json', 'records.json', 'attempts', 'smoke.json', 'failure.json'}
        entries = list(self.root.iterdir())
        if any(p.name not in allowed or p.is_symlink() for p in entries):
            raise transaction.JournalBlocked('unknown, pending or symlink entry')
        try:
            manifest = disk._read(self.root / 'manifest.json')
            if (not isinstance(manifest, dict) or manifest.get('synthetic_fixture_only') is not True
                    or manifest != disk.expected_manifest(self.runtime, synthetic_fixture=True)):
                raise ValueError('manifest differs')
            data = disk._read(self.root / 'records.json')
            if not isinstance(data, dict) or set(data) != {'plan_sha256', 'records'} or data['plan_sha256'] != self.runtime.plan_sha:
                raise ValueError('records header differs')
            attempt_dir = self.root / 'attempts'
            if attempt_dir.is_symlink() or not attempt_dir.is_dir():
                raise ValueError('attempt directory differs')
            paths = sorted(attempt_dir.iterdir())
            if any(p.name != f'{i:04d}.json' for i, p in enumerate(paths)):
                raise ValueError('attempt order differs')
            attempts = [disk._read(p) for p in paths]
            records = data['records']
            if not isinstance(records, list) or len(attempts) not in (len(records), len(records) + 1):
                raise ValueError('attempt/record counts differ')
            smoke = disk._read(self.root / 'smoke.json') if (self.root / 'smoke.json').exists() else None
            failure = disk._read(self.root / 'failure.json') if (self.root / 'failure.json').exists() else None
            check = self.runtime.validate_cache(attempts[:len(records)], records, smoke, failure)
            if len(attempts) > len(records):
                i = len(records)
                if i >= 48 or not isinstance(attempts[-1], dict) or type(attempts[-1].get('index')) is not int or attempts[-1] != {'index': i, 'id': self.runtime.plan['ordered_ids'][i],
                                                 'plan_sha256': self.runtime.plan_sha}:
                    raise ValueError('uncommitted marker differs')
                check['state'] = 'blocked_uncommitted_attempt'
            return attempts, records, smoke, check
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            raise transaction.JournalBlocked('fixture cache validation failed') from error

    def status(self):
        return self._load()[3]

    def begin(self):
        attempts, records, _, check = self._load()
        if check['state'] != 'validated_prefix':
            raise transaction.JournalBlocked('cannot start: ' + check['state'])
        index = len(records)
        marker = {'index': index, 'id': self.runtime.plan['ordered_ids'][index], 'plan_sha256': self.runtime.plan_sha}
        try:
            transaction._exclusive(self.root / 'attempts' / f'{index:04d}.json', marker)
        except BaseException:
            self._poisoned = True
            raise
        self._owned = marker
        return marker

    def commit_fixture_tokens(self, token_ids, elapsed_seconds, completed_at):
        attempts, records, smoke, check = self._load()
        if check['state'] != 'blocked_uncommitted_attempt' or self._owned is None or self._owned != attempts[-1]:
            raise transaction.JournalBlocked('current-session uncommitted attempt required')
        if len(records) >= 4 and (smoke is None or not smoke['passed']):
            raise transaction.JournalBlocked('smoke must pass before the fifth record')
        record = self.runtime.make_record(len(records), token_ids, elapsed_seconds, completed_at)
        if self._owned != {k: record[k] for k in ('index', 'id', 'plan_sha256')}:
            raise transaction.JournalBlocked('record does not match current marker')
        try:
            transaction._atomic_replace(self.root / 'records.json',
                                        {'plan_sha256': self.runtime.plan_sha, 'records': records + [record]})
        except BaseException:
            self._poisoned = True
            raise
        self._owned = None
        return record

    def check_smoke(self):
        attempts, records, smoke, check = self._load()
        if len(records) != 4 or smoke is not None or check['state'] != 'awaiting_technical_smoke':
            raise transaction.JournalBlocked('exactly four records without receipt required')
        result = self.runtime.make_smoke_receipt(records)
        try:
            transaction._exclusive(self.root / 'smoke.json', result)
        except BaseException:
            self._poisoned = True
            raise
        return result

    def review_artifacts(self):
        attempts, records, smoke, check = self._load()
        if check['state'] != 'validated_complete_unreviewed':
            raise transaction.JournalBlocked('full valid cache required')
        result = self.runtime.review_artifacts(attempts, records, smoke)
        result['synthetic_fixture_only'] = True
        return result
