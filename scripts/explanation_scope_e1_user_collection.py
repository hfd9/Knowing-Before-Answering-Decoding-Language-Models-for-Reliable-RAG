"""User-operated E1 exploratory collection, guarded by a separate reviewed release."""
import argparse
from collections import Counter
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import tempfile
import subprocess

import explanation_scope_disk_cache as disk
import explanation_scope_ledger_simulator as ledger
import explanation_scope_metrics as metrics
import explanation_scope_production as production
import explanation_scope_runtime as scope
import explanation_scope_transaction_prototype as transaction
import explanation_scope_e1_intake as intake

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'docs/explanation_scope_e1_protocol_20261107.md'
PROTOCOL_SHA256 = 'd12926314f230203c0adb4dcbeab469bf441bb1d263350337dcdf2d3ee9305cd'
E1_RUN = ROOT / 'runs/qwen2.5-3b-explanation-scope-e1-user-v1'
IMPLEMENTATION_LOCK = ROOT / 'docs/review/2026-11-07-explanation-scope-e1/implementation-lock.json'
USER_PLAN = ROOT / 'docs/review/2026-11-07-explanation-scope-e1/user-collection-plan-v1.json'
USER_RELEASE = ROOT / 'docs/review/2026-11-07-explanation-scope-e1/user-collection-release-v1.json'
USER_TEST_EVIDENCE = ROOT / 'docs/review/2026-11-07-explanation-scope-e1/user-collection-test-evidence-v1.json'
USER_REVIEW = ROOT / 'docs/explanation_scope_e1_user_collection_gate_review_20261107.md'
USER_SOURCE_FILES = (
    'docs/explanation_scope_e1_user_collection_20261107.md',
    'docs/explanation_scope_e1_user_execution_addendum_20261107.md',
    'docs/review/2026-11-07-explanation-scope-e1/user-execution-binding-candidate.json',
    'docs/review/2026-11-07-explanation-scope-e1/gpu-preflight-user-report-20261107.json',
    'docs/review/2026-11-07-explanation-scope-e1/claim-intake-snapshot.json',
    'docs/review/2026-11-07-explanation-scope-e1/implementation-lock.json',
    'scripts/explanation_scope_e1_user_collection.py',
    'scripts/explanation_scope_e1_intake.py',
    'tests/test_explanation_scope_e1_user_collection.py',
)
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


def check_user_plan():
    """Validate the independently versioned, user-operated plan and all bound sources."""
    intake.check_lock()  # The original E1 gate and code remain closed and unchanged.
    plan = disk._read(USER_PLAN)
    source_plan, source_sha = ledger.load_plan()
    keys = {'status', 'operator', 'gpu_index', 'gpu_uuid', 'run_dir', 'ordered_ids', 'smoke_ids',
            'smoke_included_in_48', 'max_attempts', 'max_attempts_per_slot', 'output_limit',
            'primary', 'fit_budget', 'held_out_380_accessed', 'independent_approvals',
            'source_plan_sha256', 'source_sha256'}
    if not isinstance(plan, dict) or set(plan) != keys:
        raise PermissionError('user execution plan fields differ')
    if (plan['status'] != 'fixed_user_execution_plan_requires_release' or plan['operator'] != 'user'
            or type(plan['gpu_index']) is not int or plan['gpu_index'] != 0
            or plan['gpu_uuid'] != 'GPU-1652bafc-65ec-03e5-1c07-ccd400b237b5'
            or plan['run_dir'] != 'runs/qwen2.5-3b-explanation-scope-e1-user-v1'
            or plan['ordered_ids'] != source_plan['ordered_ids'] or plan['smoke_ids'] != source_plan['smoke_ids']
            or plan['smoke_included_in_48'] is not True or type(plan['max_attempts']) is not int or plan['max_attempts'] != 48
            or type(plan['max_attempts_per_slot']) is not int or plan['max_attempts_per_slot'] != 1
            or type(plan['output_limit']) is not int or plan['output_limit'] != 128
            or plan['primary'] != 'mean_J_IU_minus_J_I0_over_12_scenes'
            or type(plan['fit_budget']) is not int or plan['fit_budget'] != 0 or plan['held_out_380_accessed'] is not False
            or type(plan['independent_approvals']) is not int or plan['independent_approvals'] != 0
            or plan['source_plan_sha256'] != source_sha):
        raise PermissionError('user execution plan violates frozen design')
    if not isinstance(plan['source_sha256'], dict) or set(plan['source_sha256']) != set(USER_SOURCE_FILES):
        raise PermissionError('user execution source inventory differs')
    for name, expected in plan['source_sha256'].items():
        if sha((ROOT / name).read_bytes()) != expected:
            raise PermissionError('user execution source changed: ' + name)
    return plan, sha(USER_PLAN.read_bytes())


def expected_release(plan_sha):
    """Release is an explicit reviewed artifact, not a command-line override or old gate mutation."""
    evidence = disk._read(USER_TEST_EVIDENCE)
    if (not isinstance(evidence, dict) or evidence.get('status') != 'all_user_execution_cpu_tests_passed'
            or evidence.get('tests_passed') != 8 or type(evidence.get('tests_passed')) is not int
            or evidence.get('user_script_sha256') != sha(Path(__file__).read_bytes())
            or evidence.get('test_file_sha256') != sha((ROOT / 'tests/test_explanation_scope_e1_user_collection.py').read_bytes())
            or evidence.get('gpu_inference_performed') is not False):
        raise PermissionError('user execution CPU test evidence missing or mismatched')
    return {'status': 'authorized_user_operated_e1_exploration', 'operator': 'user',
            'basis': 'user_requested_run_after_preflight_and_cpu_review',
            'reviewer': 'history_exposed_coordinating_assistant',
            'plan_sha256': plan_sha, 'review_sha256': sha(USER_REVIEW.read_bytes()),
            'test_evidence_sha256': sha(USER_TEST_EVIDENCE.read_bytes()),
            'old_v1_gate': False, 'old_e1_gate': False, 'independent_approvals': 0,
            'user_version_formal_gate': True, 'gpu_ready_requires_live_preflight': True}


def assert_user_release():
    _, plan_sha = check_user_plan()
    if disk._read(USER_RELEASE) != expected_release(plan_sha):
        raise PermissionError('user execution release missing or does not match review')


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
    _, user_plan_sha = check_user_plan()
    if not synthetic:
        assert_user_release()
    return {'format': 'explanation-scope-e1-user-v1', 'synthetic_fixture': synthetic,
            'e1_protocol_sha256': PROTOCOL_SHA256, 'source_plan_sha256': plan_sha,
            'user_plan_sha256': user_plan_sha,
            'user_release_sha256': sha(USER_RELEASE.read_bytes()) if not synthetic else None,
            'operator': 'user',
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
            assert_user_release()
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
            assert_user_release()
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
            assert_user_release()
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
        'user_plan_sha256': check_user_plan()[1],
        'user_release_sha256': sha(USER_RELEASE.read_bytes()) if not writer.synthetic else None,
        'operator': 'user',
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


def verify_device(runtime):
    """Check the planned physical GPU and busy state before loading model weights."""
    plan, _ = check_user_plan()
    process = subprocess.run(['nvidia-smi', '-i', str(plan['gpu_index']), '--query-gpu=uuid',
                              '--format=csv,noheader,nounits'], capture_output=True, text=True, check=True)
    if process.stdout.strip() != plan['gpu_uuid']:
        raise RuntimeError('physical GPU UUID differs from user preflight')
    production._verify_model_files(runtime)
    production._verify_device()


def run_locked(writer, runtime, created, preflight_done):
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
        # Device preflight failure occurs before a new attempt and remains retryable.
        if not preflight_done:
            verify_device(runtime)
        try:
            assert_user_release()
            import evidence_experiment as renderer
            model = renderer.load_model(str(runtime.model_dir))
            try:
                while True:
                    assert_user_release()
                    state = writer.status()
                    if state['state'] == 'validated_complete_unreviewed':
                        return state
                    if state['state'] != 'validated_prefix':
                        raise transaction.JournalBlocked('E1 cache blocked: ' + state['state'])
                    production._generate_one(runtime, writer, model)
                    state = writer.status()
                    print(f"E1 user collection: {state['records']}/48 committed; state={state['state']}", flush=True)
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


def collect():
    """User-triggered only after the separate release validates; never changes the original E1 gate."""
    assert_user_release()
    visible = os.environ.get('CUDA_VISIBLE_DEVICES')
    if visible not in (None, '0'):
        raise RuntimeError('planned GPU requires CUDA_VISIBLE_DEVICES=0 or unset')
    os.environ['CUDA_VISIBLE_DEVICES'] = '0'
    runtime = scope.Runtime()
    production._verify_input_snapshot(runtime)
    if E1_RUN.parent.is_symlink() or not E1_RUN.parent.is_dir() or E1_RUN.is_symlink():
        raise transaction.JournalBlocked('invalid user-run path')
    if E1_RUN.exists():
        writer = Writer(E1_RUN, runtime, synthetic_fixture=False)
        return run_locked(writer, runtime, created=False, preflight_done=False)
    # Busy/unavailable GPU or mismatched weights do not create a real run directory.
    verify_device(runtime)
    assert_user_release()
    try:
        os.mkdir(E1_RUN, 0o700)
    except FileExistsError as error:
        raise transaction.JournalBlocked('run appeared during preflight; inspect before retry') from error
    transaction._fsync_dir(E1_RUN.parent)
    writer = Writer(E1_RUN, runtime, synthetic_fixture=False)
    return run_locked(writer, runtime, created=True, preflight_done=True)


def existing_writer():
    """Open only an existing run, without initializing a model or GPU."""
    assert_user_release()
    if E1_RUN.is_symlink() or not E1_RUN.is_dir():
        raise transaction.JournalBlocked('user run does not exist as a non-symlink directory')
    lock = E1_RUN / '.lock'
    if lock.is_symlink() or not lock.is_file():
        raise transaction.JournalBlocked('existing run lock required; no repair')
    runtime = scope.Runtime()
    production._verify_input_snapshot(runtime)
    return Writer(E1_RUN, runtime, synthetic_fixture=False)


def inspect_cache():
    writer = existing_writer()
    with writer.locked():
        cache = writer._load()
        return {'status': cache['state'], 'committed_records': len(cache['records']),
                'attempts': len(cache['attempts']), 'technical_counts': dict(Counter(cache['technical'])),
                'smoke_passed': cache['smoke'] is not None and cache['smoke']['passed'] is True,
                'failure_marker_present': cache['failure'] is not None,
                'planned_slots': 48, 'operator': 'user', 'gpu_checked': False,
                'model_loaded': False, 'semantic_scores': 0}


def package_cache():
    writer = existing_writer()
    with writer.locked():
        writer._load()  # Reject damaged source before creating any export directory.
        public = E1_RUN.parent / (E1_RUN.name + '.review-public')
        private = E1_RUN.parent / (E1_RUN.name + '.review-private')
        for path in (public, private):
            if path.is_symlink():
                raise transaction.JournalBlocked('export directory cannot be a symlink')
            try:
                os.mkdir(path, 0o700)
                transaction._fsync_dir(path.parent)
            except FileExistsError:
                pass
        packet, coordinator = export_review(writer, public, private)
        return {'status': 'review_packet_created_not_semantically_scored',
                'public_directory': str(public), 'coordinator_directory': str(private),
                'planned_slots': len(packet['items']), 'source_cache_state': coordinator['cache_state'],
                'packet_canonical_sha256': coordinator['public_packet_sha256'],
                'operator': 'user', 'gpu_checked': False, 'model_loaded': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('verify', 'collect', 'inspect', 'package'), required=True)
    args = parser.parse_args()
    if args.stage == 'verify':
        plan, digest = check_user_plan()
        print(json.dumps({'status': 'plan_sources_checked_not_collection_or_gpu_readiness',
                          'plan_sha256': digest, 'planned_slots': len(plan['ordered_ids']),
                          'original_e1_gate': False, 'operator': 'user',
                          'gpu_checked': False}, indent=2))
    elif args.stage == 'collect':
        state = collect()
        print(json.dumps(state, ensure_ascii=False, indent=2))
    elif args.stage == 'inspect':
        print(json.dumps(inspect_cache(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(package_cache(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
