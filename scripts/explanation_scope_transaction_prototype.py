"""Synthetic, /tmp-only file transaction prototype. No model or collection entry point."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import tempfile

import explanation_scope_ledger_simulator as ledger


class JournalBlocked(RuntimeError):
    pass


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _regular(path):
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode):
        raise JournalBlocked(f'not a regular file: {path.name}')


def _read(path):
    try:
        _regular(path)
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise JournalBlocked(f'unreadable journal file: {path.name}') from error


def _exclusive(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Preserve any partially written file as evidence; never auto-delete.
        raise
    _fsync_dir(path.parent)


def _atomic_replace(path, value):
    pending = path.parent / ('.pending-' + secrets.token_hex(12) + '.json')
    _exclusive(pending, value)
    os.replace(pending, path)
    _fsync_dir(path.parent)


class SyntheticJournal:
    """Requires an existing temporary directory, explicit init and an exclusive lock."""

    def __init__(self, directory):
        root = Path(directory)
        if root.is_symlink() or not root.is_dir():
            raise JournalBlocked('journal root must be an existing non-symlink directory')
        self.root = root.resolve(strict=True)
        temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
        if self.root == temp_root or not self.root.is_relative_to(temp_root):
            raise JournalBlocked('prototype is restricted to a subdirectory of the system temp directory')
        self.plan, self.plan_sha = ledger.load_plan()
        self._locked = False
        self._lock_pid = None
        self._owned_attempt = None

    @contextmanager
    def locked(self):
        if self._locked:
            raise JournalBlocked('journal lock is already held by this instance')
        path = self.root / '.lock'
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise JournalBlocked('journal is locked by another process') from error
            self._locked = True
            self._lock_pid = os.getpid()
            self._owned_attempt = None
            yield self
        finally:
            if self._locked and self._lock_pid == os.getpid():
                self._owned_attempt = None
                self._locked = False
                self._lock_pid = None
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _require_lock(self):
        if not self._locked or self._lock_pid != os.getpid():
            raise JournalBlocked('exclusive journal lock required')
        _, current = ledger.load_plan()
        if current != self.plan_sha:
            raise JournalBlocked('bound draft plan changed')

    def initialize(self):
        self._require_lock()
        if {p.name for p in self.root.iterdir()} != {'.lock'}:
            raise JournalBlocked('journal directory must be empty; no automatic repair')
        attempts = self.root / 'attempts'
        attempts.mkdir(mode=0o700)
        _fsync_dir(self.root)
        _exclusive(self.root / 'manifest.json', {'format': 'synthetic-scope-journal-v1',
                                                 'synthetic': True, 'plan_sha256': self.plan_sha})
        _exclusive(self.root / 'records.json', {'synthetic': True, 'plan_sha256': self.plan_sha,
                                                'records': []})

    def _load(self):
        self._require_lock()
        allowed = {'.lock', 'attempts', 'manifest.json', 'records.json', 'smoke.json', 'failure.json'}
        extras = {p.name for p in self.root.iterdir()} - allowed
        if extras:
            raise JournalBlocked('unexpected or pending files: ' + ', '.join(sorted(extras)))
        if any(p.is_symlink() for p in self.root.iterdir()):
            raise JournalBlocked('symlinks are not valid journal entries')
        if _read(self.root / 'manifest.json') != {'format': 'synthetic-scope-journal-v1',
                                                   'synthetic': True, 'plan_sha256': self.plan_sha}:
            raise JournalBlocked('synthetic manifest differs')
        data = _read(self.root / 'records.json')
        if not isinstance(data, dict) or set(data) != {'synthetic', 'plan_sha256', 'records'} or data['synthetic'] is not True or data['plan_sha256'] != self.plan_sha:
            raise JournalBlocked('records header differs')
        attempts_dir = self.root / 'attempts'
        if attempts_dir.is_symlink() or not attempts_dir.is_dir():
            raise JournalBlocked('attempts directory missing or invalid')
        paths = sorted(attempts_dir.iterdir())
        if any(p.name != f'{i:04d}.json' for i, p in enumerate(paths)):
            raise JournalBlocked('attempt markers are not an ordered prefix')
        attempts = [_read(p) for p in paths]
        records = data['records']
        if not isinstance(records, list):
            raise JournalBlocked('records must be a list')
        for r in records:
            if not isinstance(r, dict) or not isinstance(r.get('synthetic_text'), str):
                raise JournalBlocked('invalid synthetic text')
            tokens = r.get('synthetic_token_ids')
            if not isinstance(tokens, list) or not all(type(t) is int and t >= 0 for t in tokens):
                raise JournalBlocked('invalid synthetic token list')
            if len(tokens) != r.get('output_tokens') or bool(r['synthetic_text'].strip()) is not r.get('nonempty_output'):
                raise JournalBlocked('synthetic output metadata differs')
            if hashlib.sha256(r['synthetic_text'].encode()).hexdigest() != r.get('output_sha256'):
                raise JournalBlocked('synthetic text hash differs')
        smoke = _read(self.root / 'smoke.json') if (self.root / 'smoke.json').exists() else None
        failure = _read(self.root / 'failure.json') if (self.root / 'failure.json').exists() else None
        payload = {'synthetic': True, 'plan_sha256': self.plan_sha, 'attempts': attempts,
                   'records': records, 'smoke': smoke, 'failure': failure}
        try:
            status = ledger.evaluate(payload, self.plan, self.plan_sha)
        except (ValueError, KeyError, TypeError, IndexError) as error:
            raise JournalBlocked('journal validation failed') from error
        return payload, status

    def status(self):
        return self._load()[1]

    def begin(self):
        payload, status = self._load()
        if status['state'] != 'synthetic_clean_prefix':
            raise JournalBlocked('cannot start: ' + status['state'])
        index = len(payload['records'])
        marker = {'index': index, 'id': self.plan['ordered_ids'][index], 'plan_sha256': self.plan_sha}
        _exclusive(self.root / 'attempts' / f'{index:04d}.json', marker)
        self._owned_attempt = marker
        return marker

    def commit_synthetic(self, text, token_ids, ended_with_eos, prompt_sha256):
        payload, status = self._load()
        if status['state'] != 'blocked_uncommitted_attempt':
            raise JournalBlocked('commit requires exactly one uncommitted attempt')
        if self._owned_attempt is None or self._owned_attempt != payload['attempts'][-1]:
            raise JournalBlocked('attempt was not created in this lock session; no automatic recovery')
        if len(payload['records']) >= 4 and (payload['smoke'] is None or not payload['smoke']['passed']):
            raise JournalBlocked('cannot commit after four records without passed smoke')
        if not isinstance(text, str) or not isinstance(token_ids, list) or not token_ids or len(token_ids) > 128:
            raise JournalBlocked('invalid synthetic output')
        if any(type(t) is not int or t < 0 for t in token_ids) or type(ended_with_eos) is not bool:
            raise JournalBlocked('invalid synthetic token metadata')
        if not isinstance(prompt_sha256, str) or ledger.HEX.fullmatch(prompt_sha256) is None:
            raise JournalBlocked('invalid synthetic prompt hash')
        if not ended_with_eos and len(token_ids) != 128:
            raise JournalBlocked('invalid synthetic stopping reason')
        marker = payload['attempts'][-1]
        record = dict(marker, prompt_sha256=prompt_sha256,
                      output_sha256=hashlib.sha256(text.encode()).hexdigest(),
                      output_tokens=len(token_ids), ended_with_eos=ended_with_eos,
                      hit_output_limit=len(token_ids) == 128 and not ended_with_eos,
                      nonempty_output=bool(text.strip()), synthetic_text=text,
                      synthetic_token_ids=token_ids)
        new_records = payload['records'] + [record]
        _atomic_replace(self.root / 'records.json', {'synthetic': True, 'plan_sha256': self.plan_sha,
                                                     'records': new_records})
        self._owned_attempt = None
        return record

    def check_smoke(self):
        payload, status = self._load()
        if status['state'] != 'blocked_missing_smoke_receipt' or len(payload['records']) != 4:
            raise JournalBlocked('smoke requires exactly four committed records and no prior receipt')
        passed = all(r['nonempty_output'] and r['ended_with_eos'] and not r['hit_output_limit']
                     for r in payload['records'])
        receipt = {'plan_sha256': self.plan_sha, 'records_sha256': ledger.smoke_digest(payload['records']),
                   'passed': passed}
        _exclusive(self.root / 'smoke.json', receipt)
        return receipt
