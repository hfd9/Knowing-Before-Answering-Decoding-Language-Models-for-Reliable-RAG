"""Real local tokenizer, fabricated token sequences only; no model weights or GPU."""
import fcntl
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import explanation_scope_metrics as metrics
import explanation_scope_disk_cache as disk_cache
import explanation_scope_runtime as scope
import explanation_scope_transaction_prototype as transaction
import explanation_scope_verified_fixture_journal as verified


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = scope.Runtime()
        cls.fake_tokens = cls.runtime.tokenizer.encode('synthetic response', add_special_tokens=False) + [cls.runtime.eos_ids[0]]
        cls.when = '2026-11-06T08:00:00+00:00'

    def record(self, i=0, tokens=None):
        return self.runtime.make_record(i, self.fake_tokens if tokens is None else tokens, 0.01, self.when)

    def attempts(self, n):
        return [{'index': i, 'id': self.runtime.plan['ordered_ids'][i], 'plan_sha256': self.runtime.plan_sha}
                for i in range(n)]

    def cache_fixture(self, directory, n):
        root = Path(directory)
        (root / '.lock').touch()
        (root / 'attempts').mkdir()
        (root / 'manifest.json').write_text(json.dumps(disk_cache.expected_manifest(self.runtime)), encoding='utf-8')
        records = [self.record(i) for i in range(n)]
        (root / 'records.json').write_text(json.dumps({'plan_sha256': self.runtime.plan_sha, 'records': records}), encoding='utf-8')
        for i, marker in enumerate(self.attempts(n)):
            (root / 'attempts' / f'{i:04d}.json').write_text(json.dumps(marker), encoding='utf-8')
        if n >= 4:
            (root / 'smoke.json').write_text(json.dumps(self.runtime.make_smoke_receipt(records)), encoding='utf-8')
        return records

    def test_actual_rendering_all_48_bound(self):
        summary = self.runtime.input_summary()
        self.assertEqual((summary['input_tokens_min'], summary['input_tokens_max'], summary['input_tokens_total']),
                         (287, 287, 13776))
        self.assertEqual(len({r['id'] for r in summary['items']}), 48)
        self.assertFalse(summary['weights_loaded'])
        self.assertFalse(summary['inference'])

    def test_decoding_and_original_input_binding(self):
        r = self.record()
        self.assertEqual(self.runtime.validate_record(r, 0), r)
        self.assertEqual(r['raw_output'], self.runtime.tokenizer.decode(self.fake_tokens, skip_special_tokens=True))
        self.assertTrue(r['ended_with_eos'])
        self.assertFalse(r['hit_output_limit'])

    def test_modified_prompt_or_input_token_hash_is_rejected(self):
        for key in ('input_sha256', 'prompt_sha256', 'input_token_ids_sha256'):
            r = self.record()
            r[key] = '0' * 64
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.runtime.validate_record(r, 0)

    def test_modified_text_and_token_sequence_are_rejected(self):
        r = self.record()
        r['raw_output'] += ' changed'
        with self.assertRaises(ValueError):
            self.runtime.validate_record(r, 0)
        r = self.record()
        r['generated_token_ids'] = [self.runtime.eos_ids[0]]
        with self.assertRaises(ValueError):
            self.runtime.validate_record(r, 0)

    def test_alternate_eos_with_same_decoded_text_changes_output_token_hash(self):
        self.assertGreaterEqual(len(self.runtime.eos_ids), 2)
        r = self.record(tokens=[self.runtime.eos_ids[0]])
        self.assertEqual(self.runtime.tokenizer.decode([self.runtime.eos_ids[1]], skip_special_tokens=True), r['raw_output'])
        r['generated_token_ids'] = [self.runtime.eos_ids[1]]
        with self.assertRaises(ValueError):
            self.runtime.validate_record(r, 0)

    def test_eos_early_stop_and_token_ids_checked(self):
        for tokens in ([self.runtime.eos_ids[0], 1], [1], [-1], [self.runtime.vocab_size], [True]):
            with self.subTest(tokens=tokens), self.assertRaises(ValueError):
                self.record(tokens=tokens)

    def test_exact_limit_without_eos_is_truncated(self):
        token = next(t for t in self.fake_tokens if t not in self.runtime.eos_ids)
        r = self.record(tokens=[token] * 128)
        self.assertFalse(r['ended_with_eos'])
        self.assertTrue(r['hit_output_limit'])
        self.runtime.validate_record(r, 0)

    def test_record_types_and_time_checked(self):
        r = self.record(1)
        r['index'] = True
        with self.assertRaises(ValueError):
            self.runtime.validate_record(r, 1)
        r = self.record()
        r['ended_with_eos'] = 1
        with self.assertRaises(ValueError):
            self.runtime.validate_record(r, 0)
        with self.assertRaises(ValueError):
            self.runtime.make_record(0, self.fake_tokens, float('nan'), self.when)
        with self.assertRaises(ValueError):
            self.runtime.make_record(0, self.fake_tokens, 0.1, '2026-11-06T08:00:00')

    def test_uncommitted_attempt_and_temp_files_stop(self):
        with self.assertRaises(ValueError):
            self.runtime.validate_cache(self.attempts(1), [])
        with self.assertRaises(ValueError):
            self.runtime.validate_cache([], [], pending_files=['pending'])
        with self.assertRaises(ValueError):
            self.runtime.validate_cache([], [], failure={'reason': 'synthetic'})

    def test_bad_attempt_order_is_rejected(self):
        attempts = self.attempts(1)
        attempts[0]['id'] = self.runtime.plan['ordered_ids'][1]
        with self.assertRaises(ValueError):
            self.runtime.validate_cache(attempts, [self.record()])

    def test_smoke_receipt_binds_actual_token_decoded_records(self):
        records = [self.record(i) for i in range(4)]
        self.assertEqual(self.runtime.validate_cache(self.attempts(4), records)['state'], 'awaiting_technical_smoke')
        smoke = self.runtime.make_smoke_receipt(records)
        self.assertTrue(smoke['passed'])
        self.assertEqual(self.runtime.validate_cache(self.attempts(4), records, smoke)['state'], 'validated_prefix')
        smoke['records_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.runtime.validate_cache(self.attempts(4), records, smoke)

    def test_empty_or_truncated_smoke_never_passes(self):
        for bad in ([self.runtime.eos_ids[0]], [self.fake_tokens[0]] * 128):
            records = [self.record(i) for i in range(4)]
            records[1] = self.record(1, bad)
            smoke = self.runtime.make_smoke_receipt(records)
            self.assertFalse(smoke['passed'])
            self.assertEqual(self.runtime.validate_cache(self.attempts(4), records, smoke)['state'], 'blocked_failed_smoke')
            records.append(self.record(4))
            with self.assertRaises(ValueError):
                self.runtime.validate_cache(self.attempts(5), records, smoke)

    def test_full_synthetic_token_packet_and_unreviewed_scoring_template(self):
        records = [self.record(i) for i in range(48)]
        smoke = self.runtime.make_smoke_receipt(records)
        result = self.runtime.review_artifacts(self.attempts(48), records, smoke)
        self.assertEqual(len(result['packet']['items']), 48)
        self.assertEqual(len(result['coordinator_mapping']), 48)
        self.assertTrue(all(set(item) == {'item_id', 'question', 'documents', 'answer'}
                            for item in result['packet']['items']))
        self.assertEqual(result['artifact_sha256']['packet'], scope.json_sha(result['packet']))
        self.assertEqual(result['artifact_sha256']['coordinator_mapping'], scope.json_sha(result['coordinator_mapping']))
        self.assertEqual(result['artifact_sha256']['endpoint_template'], scope.json_sha(result['endpoint_template']))
        review = result['endpoint_template']
        summary = metrics.summarize(review)
        self.assertEqual(summary['reviewed_slots'], 0)
        self.assertEqual(summary['technical_complete'], 48)
        self.assertIsNone(summary['primary']['point'])
        self.assertFalse(summary['formal_gate'])

    def test_partial_cache_cannot_become_review_packet(self):
        records = [self.record(i) for i in range(4)]
        with self.assertRaises(ValueError):
            self.runtime.review_artifacts(self.attempts(4), records, self.runtime.make_smoke_receipt(records))

    def test_collection_gate_is_unconditionally_disabled(self):
        with self.assertRaises(PermissionError):
            self.runtime.assert_collection_disabled()

    def test_missing_disk_cache_is_readonly_and_not_created(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-readonly-') as directory:
            root = Path(directory) / 'missing'
            result = disk_cache.inspect_cache(root, self.runtime)
            self.assertEqual(result['state'], 'not_created')
            self.assertFalse(root.exists())
            self.assertFalse(result['gpu_launch_ready'])

    def test_readonly_disk_cache_checks_real_tokenizer_records(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-readonly-') as directory:
            self.cache_fixture(directory, 4)
            before = {str(p.relative_to(directory)): p.read_bytes() for p in Path(directory).rglob('*') if p.is_file()}
            result = disk_cache.inspect_cache(directory, self.runtime)
            after = {str(p.relative_to(directory)): p.read_bytes() for p in Path(directory).rglob('*') if p.is_file()}
            self.assertEqual(result['state'], 'validated_prefix')
            self.assertEqual(result['records'], 4)
            self.assertFalse(result['output_origin_verified'])
            self.assertEqual(before, after)

    def test_disk_cache_pending_and_tampered_records_block_without_changes(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-readonly-') as directory:
            self.cache_fixture(directory, 1)
            pending = Path(directory) / '.pending-test.json'
            pending.write_text('{}')
            with self.assertRaises(ValueError):
                disk_cache.inspect_cache(directory, self.runtime)
            self.assertTrue(pending.exists())
            pending.unlink()
            path = Path(directory) / 'records.json'
            value = json.loads(path.read_text())
            value['records'][0]['generated_token_ids_sha256'] = '0' * 64
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                disk_cache.inspect_cache(directory, self.runtime)

    def test_disk_cache_reader_refuses_active_exclusive_lock(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-readonly-') as directory:
            self.cache_fixture(directory, 0)
            with (Path(directory) / '.lock').open('rb+') as stream:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    with self.assertRaises(ValueError):
                        disk_cache.inspect_cache(directory, self.runtime)
                finally:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def test_real_tokenizer_bound_through_synthetic_filesystem_journal(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-verified-') as directory:
            journal = verified.VerifiedFixtureJournal(directory, self.runtime)
            with journal.locked():
                journal.initialize()
                for i in range(4):
                    journal.begin()
                    record = journal.commit_fixture_tokens(self.fake_tokens, 0.01, self.when)
                    self.assertEqual(record['input_token_ids_sha256'], self.runtime.inputs[record['id']]['input_token_ids_sha256'])
                self.assertEqual(journal.status()['state'], 'blocked_missing_smoke_receipt')
                self.assertTrue(journal.check_smoke()['passed'])
                journal.begin()
                journal.commit_fixture_tokens(self.fake_tokens, 0.01, self.when)
                self.assertEqual(journal.status()['declared_records'], 5)
                self.assertFalse(journal.status()['collection_permitted'])

    def test_persisted_token_binding_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-verified-') as directory:
            journal = verified.VerifiedFixtureJournal(directory, self.runtime)
            with journal.locked():
                journal.initialize()
                journal.begin()
                journal.commit_fixture_tokens(self.fake_tokens, 0.01, self.when)
                path = Path(directory) / 'records.json'
                value = json.loads(path.read_text())
                value['records'][0]['runtime_record']['input_token_ids_sha256'] = '0' * 64
                path.write_text(json.dumps(value), encoding='utf-8')
                with self.assertRaises(transaction.JournalBlocked):
                    journal.status()

    def test_new_process_revalidates_and_continues_committed_prefix(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-verified-') as directory:
            journal = verified.VerifiedFixtureJournal(directory, self.runtime)
            with journal.locked():
                journal.initialize()
                journal.begin()
                journal.commit_fixture_tokens(self.fake_tokens, 0.01, self.when)
            code = (
                "import sys,json\nsys.path.insert(0,sys.argv[1])\n"
                "import explanation_scope_runtime as r\n"
                "import explanation_scope_verified_fixture_journal as j\n"
                "rt=r.Runtime()\nx=j.VerifiedFixtureJournal(sys.argv[2],rt)\n"
                "with x.locked():\n"
                " assert x.status()['declared_records']==1\n"
                " x.begin()\n"
                " ids=rt.tokenizer.encode('synthetic response',add_special_tokens=False)+[rt.eos_ids[0]]\n"
                " x.commit_fixture_tokens(ids,0.01,'2026-11-06T08:00:00+00:00')\n"
                " print(json.dumps(x.status()))\n"
            )
            result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'scripts'), directory],
                                    capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads(result.stdout)
            self.assertEqual(state['declared_records'], 2)
            self.assertFalse(state['collection_permitted'])
            with journal.locked():
                self.assertEqual(journal.status()['declared_records'], 2)

    def test_reopened_uncommitted_fixture_marker_cannot_be_filled(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-verified-') as directory:
            journal = verified.VerifiedFixtureJournal(directory, self.runtime)
            with journal.locked():
                journal.initialize()
                journal.begin()
            with journal.locked():
                with self.assertRaises(transaction.JournalBlocked):
                    journal.commit_fixture_tokens(self.fake_tokens, 0.01, self.when)
                self.assertEqual(journal.status()['state'], 'blocked_uncommitted_attempt')

    def test_new_process_exit_after_real_tokenizer_marker_blocks_reanswer(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-verified-') as directory:
            journal = verified.VerifiedFixtureJournal(directory, self.runtime)
            with journal.locked():
                journal.initialize()
            code = (
                "import sys,os\nsys.path.insert(0,sys.argv[1])\n"
                "import explanation_scope_runtime as r\n"
                "import explanation_scope_verified_fixture_journal as j\n"
                "rt=r.Runtime()\nx=j.VerifiedFixtureJournal(sys.argv[2],rt)\n"
                "with x.locked():\n x.begin()\n os._exit(37)\n"
            )
            result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'scripts'), directory],
                                    capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 37, result.stderr)
            with journal.locked():
                self.assertEqual(journal.status()['state'], 'blocked_uncommitted_attempt')
                with self.assertRaises(transaction.JournalBlocked):
                    journal.commit_fixture_tokens(self.fake_tokens, 0.01, self.when)

    def test_integrated_failed_replace_preserves_uncommitted_marker(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-verified-') as directory:
            journal = verified.VerifiedFixtureJournal(directory, self.runtime)
            with journal.locked():
                journal.initialize()
                journal.begin()
                with patch.object(transaction.os, 'replace', side_effect=OSError('synthetic failure')):
                    with self.assertRaises(OSError):
                        journal.commit_fixture_tokens(self.fake_tokens, 0.01, self.when)
                self.assertTrue((Path(directory) / 'attempts/0000.json').exists())
                self.assertTrue(list(Path(directory).glob('.pending-*.json')))
                with self.assertRaises(transaction.JournalBlocked):
                    journal.status()

    def test_full_48_real_tokenizer_synthetic_journal_review_connection(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-verified-') as directory:
            journal = verified.VerifiedFixtureJournal(directory, self.runtime)
            with journal.locked():
                journal.initialize()
                for i in range(48):
                    journal.begin()
                    tokens = ([self.fake_tokens[0]] * 128) if i == 17 else self.fake_tokens
                    journal.commit_fixture_tokens(tokens, 0.01, self.when)
                    if i == 3:
                        self.assertTrue(journal.check_smoke()['passed'])
                self.assertEqual(journal.status()['state'], 'synthetic_complete')
                result = journal.complete_fixture_review()
                self.assertTrue(result['synthetic_fixture_only'])
                self.assertEqual(len(result['packet']['items']), 48)
                summary = metrics.summarize(result['endpoint_template'])
                self.assertEqual(summary['reviewed_slots'], 0)
                self.assertEqual(summary['technical_complete'], 47)
                self.assertIsNone(summary['primary']['point'])
                self.assertFalse(summary['gpu_launch_ready'])


if __name__ == '__main__':
    unittest.main()
