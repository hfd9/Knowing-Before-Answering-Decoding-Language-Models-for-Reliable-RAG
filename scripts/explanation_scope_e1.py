"""E1 guarded execution and partial review packaging. Real collection is disabled."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import tempfile

import explanation_scope_disk_cache as disk
import explanation_scope_ledger_simulator as ledger
import explanation_scope_metrics as metrics
import explanation_scope_production as production
import explanation_scope_runtime as scope
import explanation_scope_transaction_prototype as transaction

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'docs/explanation_scope_e1_protocol_20261107.md'
PROTOCOL_SHA256 = 'd12926314f230203c0adb4dcbeab469bf441bb1d263350337dcdf2d3ee9305cd'
E1_RUN = ROOT / 'runs/qwen2.5-3b-explanation-scope-e1-r1'
IMPLEMENTATION_LOCK = ROOT / 'docs/review/2026-11-07-explanation-scope-e1/implementation-lock.json'
IMPLEMENTATION = ('scripts/explanation_scope_e1.py', 'scripts/explanation_scope_runtime.py',
                  'scripts/explanation_scope_production.py', 'scripts/explanation_scope_generation_fixture.py',
                  'scripts/explanation_scope_disk_cache.py', 'scripts/explanation_scope_transaction_prototype.py',
                  'scripts/explanation_scope_ledger_simulator.py', 'scripts/explanation_scope_metrics.py',
                  'scripts/explanation_scope_cache_writer_fixture.py', 'scripts/evidence_experiment.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def check_protocol():
    if sha(PROTOCOL.read_bytes()) != PROTOCOL_SHA256:
        raise transaction.JournalBlocked('E1 protocol differs from frozen hash')


def assert_collection_disabled():
    raise PermissionError('E1 collection is disabled pending formal gate review')


def manifest(runtime, synthetic):
    check_protocol()
    _, plan_sha = ledger.load_plan()
    if runtime.plan_sha != plan_sha:
        raise transaction.JournalBlocked('source plan changed')
    implementations = {name: sha((ROOT / name).read_bytes()) for name in IMPLEMENTATION}
    expected = {'e1_protocol_sha256': PROTOCOL_SHA256, 'source_plan_sha256': plan_sha,
                'implementation_sha256': implementations, 'formal_gate': False,
                'gpu_launch_ready': False}
    if disk._read(IMPLEMENTATION_LOCK) != expected:
        raise transaction.JournalBlocked('E1 implementation lock changed')
    return {'format': 'explanation-scope-e1-r1', 'synthetic_fixture': synthetic,
            'e1_protocol_sha256': PROTOCOL_SHA256, 'source_plan_sha256': plan_sha,
            'input_fingerprints_sha256': sha(disk.INPUT_FINGERPRINTS.read_bytes()),
            'model_reference_sha256': scope.json_sha(runtime.reference),
            'implementation_lock_sha256': sha(IMPLEMENTATION_LOCK.read_bytes()),
            'implementation_sha256': implementations}


def technical(record):
    if not record['raw_output'].strip():
        return 'empty'
    if record['hit_output_limit']:
        return 'truncated'
    if not record['ended_with_eos']:
        raise ValueError('unexpected non-EOS output')
    return 'complete'


class Writer:
    """Real path is gated; synthetic mode is confined to an existing temporary subdirectory."""

    def __init__(self, directory, runtime, *, synthetic_fixture):
        if type(synthetic_fixture) is not bool:
            raise ValueError('explicit fixture status required')
        if not synthetic_fixture:
            assert_collection_disabled()
            if Path(directory) != E1_RUN:
                raise transaction.JournalBlocked('wrong E1 run path')
        root = Path(directory)
        if root.is_symlink() or not root.is_dir():
            raise transaction.JournalBlocked('existing non-symlink directory required')
        self.root = root.resolve(strict=True)
        temp = Path(tempfile.gettempdir()).resolve(strict=True)
        if synthetic_fixture and (self.root == temp or not self.root.is_relative_to(temp)):
            raise transaction.JournalBlocked('fixtures restricted to temporary subdirectories')
        self.synthetic = synthetic_fixture
        self.runtime = runtime
        self.lock_fd = None
        self.pid = None
        self.owned = None
        self.poisoned = False

    @contextmanager
    def locked(self):
        if not self.synthetic:
            assert_collection_disabled()
        if self.lock_fd is not None:
            raise transaction.JournalBlocked('lock already held')
        fd = os.open(self.root / '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise transaction.JournalBlocked('lock must be a regular file')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise transaction.JournalBlocked('run locked') from error
            self.lock_fd, self.pid, self.owned, self.poisoned = fd, os.getpid(), None, False
            self._require()
            yield self
        finally:
            if self.pid == os.getpid():
                self.lock_fd, self.pid, self.owned = None, None, None
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _require(self):
        if not self.synthetic:
            assert_collection_disabled()
        if self.lock_fd is None or self.pid != os.getpid() or self.poisoned:
            raise transaction.JournalBlocked('active unpoisoned process lock required')
        opened, current = os.fstat(self.lock_fd), (self.root / '.lock').lstat()
        if not stat.S_ISREG(current.st_mode) or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise transaction.JournalBlocked('lock changed')
        check_protocol()

    def initialize(self):
        self._require()
        if {p.name for p in self.root.iterdir()} != {'.lock'}:
            raise transaction.JournalBlocked('new empty run required')
        try:
            (self.root / 'attempts').mkdir(mode=0o700)
            transaction._fsync_dir(self.root)
            transaction._exclusive(self.root / 'manifest.json', manifest(self.runtime, self.synthetic))
            transaction._exclusive(self.root / 'records.json',
                                   {'plan_sha256': self.runtime.plan_sha, 'records': []})
        except BaseException:
            self.poisoned = True
            raise

    def _load(self):
        self._require()
        try:
            allowed = {'.lock', 'manifest.json', 'records.json', 'attempts', 'smoke.json', 'failure.json'}
            if any(p.name not in allowed or p.is_symlink() for p in self.root.iterdir()):
                raise ValueError('unexpected or symlink entry')
            if disk._read(self.root / 'manifest.json') != manifest(self.runtime, self.synthetic):
                raise ValueError('manifest or code fingerprint changed')
            data = disk._read(self.root / 'records.json')
            if not isinstance(data, dict) or set(data) != {'plan_sha256', 'records'} or data['plan_sha256'] != self.runtime.plan_sha:
                raise ValueError('records header changed')
            records = data['records']
            attempt_dir = self.root / 'attempts'
            if attempt_dir.is_symlink() or not attempt_dir.is_dir():
                raise ValueError('attempt directory invalid')
            paths = sorted(attempt_dir.iterdir())
            if any(p.name != f'{i:04d}.json' for i, p in enumerate(paths)):
                raise ValueError('attempt order changed')
            attempts = [disk._read(p) for p in paths]
            if not isinstance(records, list) or len(records) > 48 or len(attempts) not in (len(records), len(records) + 1) or len(attempts) > 48:
                raise ValueError('invalid record/attempt count')
            for i, attempt in enumerate(attempts):
                if attempt != {'index': i, 'id': self.runtime.plan['ordered_ids'][i], 'plan_sha256': self.runtime.plan_sha,
                               'e1_protocol_sha256': PROTOCOL_SHA256} or type(attempt.get('index')) is not int:
                    raise ValueError('attempt binding changed')
            states = []
            for i, record in enumerate(records):
                self.runtime.validate_record(record, i)
                states.append(technical(record))
            bad = [i for i, state in enumerate(states) if state != 'complete']
            if bad and (len(bad) != 1 or bad[0] != len(records) - 1 or len(attempts) != len(records)):
                raise ValueError('records continue after invalid output')
            smoke_path = self.root / 'smoke.json'
            smoke = disk._read(smoke_path) if smoke_path.exists() else None
            if smoke is not None:
                if len(records) < 4 or any(x != 'complete' for x in states[:4]) or smoke != self.runtime.make_smoke_receipt(records) or smoke['passed'] is not True:
                    raise ValueError('invalid smoke receipt')
            if len(records) > 4 and smoke is None:
                raise ValueError('records after missing smoke')
            if len(attempts) > len(records) and len(records) >= 4 and smoke is None:
                raise ValueError('attempt after missing smoke')
            failure_path = self.root / 'failure.json'
            failure = disk._read(failure_path) if failure_path.exists() else None
            if failure is not None and (not isinstance(failure, dict) or not isinstance(failure.get('reason'), str) or not failure['reason'].strip()):
                raise ValueError('invalid failure marker')
            if failure is not None:
                state = 'blocked_failure'
            elif bad:
                state = 'blocked_' + states[-1]
            elif len(attempts) > len(records):
                state = 'blocked_uncommitted_attempt'
            elif len(records) == 4 and smoke is None:
                state = 'awaiting_technical_smoke'
            elif len(records) == 48:
                state = 'validated_complete_unreviewed'
            else:
                state = 'validated_prefix'
            return {'state': state, 'records': records, 'attempts': attempts, 'attempt_paths': paths,
                    'technical': states, 'smoke': smoke, 'failure': failure}
        except (OSError, KeyError, TypeError, ValueError, IndexError) as error:
            raise transaction.JournalBlocked('invalid E1 cache; preserve for inspection') from error

    def status(self):
        cache = self._load()
        return {'state': cache['state'], 'records': len(cache['records'])}

    def begin(self):
        cache = self._load()
        if cache['state'] != 'validated_prefix':
            raise transaction.JournalBlocked('cannot begin: ' + cache['state'])
        i = len(cache['records'])
        marker = {'index': i, 'id': self.runtime.plan['ordered_ids'][i], 'plan_sha256': self.runtime.plan_sha,
                  'e1_protocol_sha256': PROTOCOL_SHA256}
        try:
            transaction._exclusive(self.root / 'attempts' / f'{i:04d}.json', marker)
        except BaseException:
            self.poisoned = True
            raise
        self.owned = marker
        return marker

    def commit_tokens(self, tokens, elapsed_seconds, completed_at):
        cache = self._load()
        if cache['state'] != 'blocked_uncommitted_attempt' or self.owned is None or self.owned != cache['attempts'][-1]:
            raise transaction.JournalBlocked('current lock session must own the attempt')
        record = self.runtime.make_record(len(cache['records']), tokens, elapsed_seconds, completed_at)
        if {k: record[k] for k in ('index', 'id', 'plan_sha256')} != {k: self.owned[k] for k in ('index', 'id', 'plan_sha256')}:
            raise transaction.JournalBlocked('record binding mismatch')
        try:
            transaction._atomic_replace(self.root / 'records.json',
                {'plan_sha256': self.runtime.plan_sha, 'records': cache['records'] + [record]})
        except BaseException:
            self.poisoned = True
            raise
        self.owned = None
        return record

    def check_smoke(self):
        cache = self._load()
        if cache['state'] != 'awaiting_technical_smoke':
            raise transaction.JournalBlocked('four complete smoke records required')
        receipt = self.runtime.make_smoke_receipt(cache['records'])
        if not receipt['passed']:
            raise transaction.JournalBlocked('invalid smoke')
        try:
            transaction._exclusive(self.root / 'smoke.json', receipt)
        except BaseException:
            self.poisoned = True
            raise
        return receipt


def export_review(writer, public_dir, private_dir):
    """Export a snapshot with a persistent run-level secret mapping, while holding the run lock."""
    cache = writer._load()
    public, private = Path(public_dir), Path(private_dir)
    for directory in (public, private):
        if directory.is_symlink() or not directory.is_dir():
            raise transaction.JournalBlocked('existing non-symlink export directories required')
    public, private = public.resolve(strict=True), private.resolve(strict=True)
    if public != writer.root.parent / (writer.root.name + '.review-public') or private != writer.root.parent / (writer.root.name + '.review-private'):
        raise transaction.JournalBlocked('fixed separate sibling export directories required')
    if any(stat.S_IMODE(p.stat().st_mode) & 0o077 for p in (public, private)):
        raise transaction.JournalBlocked('export directories must be private to the owner')
    if writer.synthetic:
        temp = Path(tempfile.gettempdir()).resolve(strict=True)
        if any(p == temp or not p.is_relative_to(temp) for p in (public, private)):
            raise transaction.JournalBlocked('fixture exports restricted to temporary directories')
    # Verify the entire input set against its bound rendering before disclosure.
    production._verify_input_snapshot(writer.runtime)
    for item_id in writer.runtime.plan['ordered_ids']:
        writer.runtime.generation_input(item_id)
    pub_entries, priv_entries = list(public.iterdir()), list(private.iterdir())
    if any(p.is_symlink() or not p.is_file() for p in pub_entries + priv_entries):
        raise transaction.JournalBlocked('invalid export entry')
    mapping_path = private / 'mapping.json'
    if not mapping_path.exists():
        if pub_entries or priv_entries:
            raise transaction.JournalBlocked('incomplete export; preserve for inspection')
        ids = list(writer.runtime.plan['ordered_ids'])
        secrets.SystemRandom().shuffle(ids)
        mapping = {f'R{i:03d}': item_id for i, item_id in enumerate(ids, 1)}
        transaction._exclusive(mapping_path, {'protocol_sha256': PROTOCOL_SHA256,
            'manifest_sha256': sha((writer.root / 'manifest.json').read_bytes()), 'mapping': mapping})
    else:
        stored = disk._read(mapping_path)
        mapping = stored.get('mapping') if isinstance(stored, dict) else None
        if (not isinstance(stored, dict) or set(stored) != {'protocol_sha256', 'manifest_sha256', 'mapping'}
                or stored['protocol_sha256'] != PROTOCOL_SHA256
                or stored['manifest_sha256'] != sha((writer.root / 'manifest.json').read_bytes())
                or not isinstance(mapping, dict) or set(mapping) != {f'R{i:03d}' for i in range(1, 49)}
                or set(mapping.values()) != set(writer.runtime.plan['ordered_ids'])):
            raise transaction.JournalBlocked('mapping or run binding changed')
        # Every prior snapshot must have all three files and still match its seal.
        seal_names = {p.name[len('seal-'):-len('.json')] for p in priv_entries
                      if p.name.startswith('seal-') and p.name.endswith('.json')}
        expected_private = {'mapping.json'} | {f'{kind}-{name}.json' for name in seal_names for kind in ('begin', 'seal', 'coordinator')}
        expected_public = {f'packet-{name}.json' for name in seal_names}
        if {p.name for p in priv_entries} != expected_private or {p.name for p in pub_entries} != expected_public:
            raise transaction.JournalBlocked('incomplete or unexpected export; preserve for inspection')
        for name in seal_names:
            seal = disk._read(private / f'seal-{name}.json')
            packet = disk._read(public / f'packet-{name}.json')
            coordinator = disk._read(private / f'coordinator-{name}.json')
            begin = disk._read(private / f'begin-{name}.json')
            if (begin != {'snapshot_id': name, 'protocol_sha256': PROTOCOL_SHA256}
                    or seal != {'packet_sha256': scope.json_sha(packet), 'coordinator_sha256': scope.json_sha(coordinator)}
                    or coordinator.get('public_packet_sha256') != scope.json_sha(packet)
                    or {key: value.get('source_item_id') for key, value in coordinator.get('mapping_and_sources', {}).items()} != mapping):
                raise transaction.JournalBlocked('prior exported snapshot changed')
    by_id = {record['id']: (i, record) for i, record in enumerate(cache['records'])}
    pending = cache['attempts'][-1]['id'] if len(cache['attempts']) > len(cache['records']) else None
    packet, sources = [], {}
    for review_id, item_id in mapping.items():
        row = writer.runtime.rows[item_id]
        status = 'not_collected'
        record = None
        if item_id in by_id:
            i, record = by_id[item_id]
            status = cache['technical'][i]
        elif item_id == pending:
            status = 'failed'
        item = {'item_id': review_id, 'question': row['question'], 'documents': row['documents'],
                'technical_status': status}
        if status == 'complete':
            item['answer'] = record['raw_output']
        packet.append(item)
        sources[review_id] = {'source_item_id': item_id,
            'input_sha256': writer.runtime.inputs[item_id]['input_sha256'],
            'technical_status': status,
            'output_sha256': record['raw_output_sha256'] if record is not None else None,
            'record_sha256': scope.json_sha(record) if record is not None else None,
            'empty_output': not bool(record['raw_output'].strip()) if record is not None else None,
            'hit_output_limit': record['hit_output_limit'] if record is not None else None,
            'attempt_sha256': sha(cache['attempt_paths'][writer.runtime.plan['ordered_ids'].index(item_id)].read_bytes())
                if item_id in by_id or item_id == pending else None}
    public_payload = {'format': 'e1-review-packet-v1', 'items': packet,
                      'note': 'Pseudonyms omit explicit conditions; text and status may reveal structure. '
                              'Matching question and documents to the public materials can identify conditions.'}
    template = metrics.blank_review()
    template['e1_protocol_sha256'] = PROTOCOL_SHA256
    reverse = {item_id: review_id for review_id, item_id in mapping.items()}
    for row in template['rows']:
        item_id = f"exs{row['scene']:02d}_{row['condition']}"
        review_id = reverse[item_id]
        source = sources[review_id]
        row.update({'source_item_id': review_id, 'input_sha256': source['input_sha256'],
                    'output_sha256': source['output_sha256'], 'technical_status': source['technical_status']})
    metrics.validate(template)
    private_payload = {'format': 'e1-review-coordinator-v1', 'protocol_sha256': PROTOCOL_SHA256,
        'synthetic_fixture': writer.synthetic, 'cache_state': cache['state'],
        'records_file_sha256': sha((writer.root / 'records.json').read_bytes()),
        'manifest_sha256': sha((writer.root / 'manifest.json').read_bytes()),
        'smoke_sha256': sha((writer.root / 'smoke.json').read_bytes()) if cache['smoke'] is not None else None,
        'failure_sha256': sha((writer.root / 'failure.json').read_bytes()) if cache['failure'] is not None else None,
        'public_packet_sha256': scope.json_sha(public_payload), 'mapping_and_sources': sources,
        'endpoint_template': template}
    # Each file is exclusive and durable. Incomplete exports remain visible and block re-export to these dirs.
    snapshot_id = secrets.token_hex(16)
    transaction._exclusive(private / f'begin-{snapshot_id}.json', {'snapshot_id': snapshot_id,
                                                                  'protocol_sha256': PROTOCOL_SHA256})
    transaction._exclusive(private / f'coordinator-{snapshot_id}.json', private_payload)
    transaction._exclusive(public / f'packet-{snapshot_id}.json', public_payload)
    transaction._exclusive(private / f'seal-{snapshot_id}.json', {'packet_sha256': scope.json_sha(public_payload),
                                                   'coordinator_sha256': scope.json_sha(private_payload)})
    return public_payload, private_payload


def collect():
    """Real execution remains denied before runtime, directory, device or model access."""
    assert_collection_disabled()
    runtime = scope.Runtime()
    production._verify_input_snapshot(runtime)
    if E1_RUN.parent.is_symlink() or not E1_RUN.parent.is_dir() or E1_RUN.is_symlink():
        raise transaction.JournalBlocked('invalid E1 run path')
    try:
        os.mkdir(E1_RUN, 0o700)
        created = True
        transaction._fsync_dir(E1_RUN.parent)
    except FileExistsError:
        created = False
    writer = Writer(E1_RUN, runtime, synthetic_fixture=False)
    with writer.locked():
        if created:
            writer.initialize()
        state = writer.status()
        if state['state'] == 'awaiting_technical_smoke':
            writer.check_smoke()
            state = writer.status()
        if state['state'] == 'validated_complete_unreviewed':
            return state
        if state['state'] != 'validated_prefix':
            raise transaction.JournalBlocked('E1 cache blocked: ' + state['state'])
        try:
            production._verify_model_files(runtime)
            production._verify_device()
            assert_collection_disabled()
            import evidence_experiment as renderer
            model = renderer.load_model(str(runtime.model_dir))
            try:
                while True:
                    assert_collection_disabled()
                    state = writer.status()
                    if state['state'] == 'validated_complete_unreviewed':
                        return state
                    if state['state'] != 'validated_prefix':
                        raise transaction.JournalBlocked('E1 cache blocked: ' + state['state'])
                    production._generate_one(runtime, writer, model)
                    state = writer.status()
                    if state['state'] == 'awaiting_technical_smoke':
                        writer.check_smoke()
            finally:
                del model
        except BaseException as error:
            # Uncommitted attempts and invalid records already block resume. Persist other
            # execution errors when the cache is still verifiable; never erase evidence.
            if not isinstance(error, (KeyboardInterrupt, transaction.JournalBlocked)):
                try:
                    if writer.status()['state'] in ('validated_prefix', 'awaiting_technical_smoke', 'blocked_uncommitted_attempt'):
                        transaction._exclusive(writer.root / 'failure.json',
                                               {'reason': 'execution_exception:' + type(error).__name__})
                except BaseException:
                    pass  # Preserve the original failure and any partial marker.
            raise
