import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import explanation_scope_transaction_prototype as proto


class TransactionPrototypeChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='kba-scope-journal-')
        self.root = Path(self.tmp.name)
        self.journal = proto.SyntheticJournal(self.root)
        with self.journal.locked():
            self.journal.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def commit(self, text='synthetic example', eos=True):
        self.journal.begin()
        return self.journal.commit_synthetic(text, [8, 9] if eos else [8] * 128, eos, 'a' * 64)

    def child(self, body):
        code = "import sys, os\nsys.path.insert(0, sys.argv[1])\nimport explanation_scope_transaction_prototype as p\n" + body
        return subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'scripts'), str(self.root)],
                              capture_output=True, text=True)

    def test_four_smoke_then_fifth_commits_and_stays_synthetic(self):
        with self.journal.locked():
            for _ in range(4):
                self.commit()
            self.assertEqual(self.journal.status()['state'], 'blocked_missing_smoke_receipt')
            with self.assertRaises(proto.JournalBlocked):
                self.journal.begin()
            self.assertTrue(self.journal.check_smoke()['passed'])
            self.commit()
            state = self.journal.status()
            self.assertEqual((state['declared_attempts'], state['declared_records']), (5, 5))
            self.assertFalse(state['collection_permitted'])
            self.assertFalse(state['gpu_launch_ready'])

    def test_full_48_synthetic_records_stop_at_fixed_limit(self):
        with self.journal.locked():
            for i in range(48):
                self.commit(text=f'synthetic-{i}')
                if i == 3:
                    self.assertTrue(self.journal.check_smoke()['passed'])
            result = self.journal.status()
            self.assertEqual(result['state'], 'synthetic_complete')
            self.assertEqual((result['declared_attempts'], result['declared_records']), (48, 48))
            self.assertFalse(result['collection_permitted'])
            with self.assertRaises(proto.JournalBlocked):
                self.journal.begin()

    def test_cross_process_lock_excludes_other_process(self):
        body = ("j=p.SyntheticJournal(sys.argv[2])\n"
                "try:\n with j.locked(): pass\n"
                "except p.JournalBlocked:\n sys.exit(23)\n"
                "sys.exit(0)\n")
        with self.journal.locked():
            result = self.child(body)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(self.child(body).returncode, 0)

    def test_process_exit_after_marker_blocks_another_attempt(self):
        body = "j=p.SyntheticJournal(sys.argv[2])\nwith j.locked():\n j.begin()\n os._exit(17)\n"
        result = self.child(body)
        self.assertEqual(result.returncode, 17, result.stderr)
        with self.journal.locked():
            self.assertEqual(self.journal.status()['state'], 'blocked_uncommitted_attempt')
            with self.assertRaises(proto.JournalBlocked):
                self.journal.begin()
            with self.assertRaises(proto.JournalBlocked):
                self.journal.commit_synthetic('new answer after exit', [7], True, 'a' * 64)
        self.assertTrue((self.root / 'attempts/0000.json').is_file())

    def test_releasing_lock_revokes_uncommitted_attempt_ownership(self):
        with self.journal.locked():
            self.journal.begin()
        with self.journal.locked():
            with self.assertRaises(proto.JournalBlocked):
                self.journal.commit_synthetic('not the original session', [7], True, 'a' * 64)
            self.assertEqual(self.journal.status()['state'], 'blocked_uncommitted_attempt')

    @unittest.skipUnless(hasattr(os, 'fork'), 'requires POSIX fork')
    def test_forked_child_cannot_inherit_commit_right(self):
        with self.journal.locked():
            self.journal.begin()
            pid = os.fork()
            if pid == 0:
                try:
                    self.journal.commit_synthetic('forked child', [7], True, 'a' * 64)
                except proto.JournalBlocked:
                    os._exit(0)
                os._exit(1)
            _, status = os.waitpid(pid, 0)
            self.assertEqual(os.waitstatus_to_exitcode(status), 0)
            self.assertEqual(self.journal.status()['state'], 'blocked_uncommitted_attempt')
            self.journal.commit_synthetic('original process', [7], True, 'a' * 64)
            self.assertEqual(self.journal.status()['declared_records'], 1)

    def test_process_exit_after_commit_preserves_prefix(self):
        body = ("j=p.SyntheticJournal(sys.argv[2])\nwith j.locked():\n j.begin()\n"
                " j.commit_synthetic('sample', [7,8], True, 'a'*64)\n os._exit(19)\n")
        result = self.child(body)
        self.assertEqual(result.returncode, 19, result.stderr)
        with self.journal.locked():
            self.assertEqual(self.journal.status()['declared_records'], 1)
            self.assertEqual(self.journal.begin()['index'], 1)

    def test_failed_atomic_replace_preserves_marker_and_pending_file(self):
        with self.journal.locked():
            self.journal.begin()
            original = (self.root / 'records.json').read_bytes()
            with patch.object(proto.os, 'replace', side_effect=OSError('synthetic interruption')):
                with self.assertRaises(OSError):
                    self.journal.commit_synthetic('example', [8], True, 'a' * 64)
            self.assertEqual((self.root / 'records.json').read_bytes(), original)
            self.assertTrue(list(self.root.glob('.pending-*.json')))
            self.assertTrue((self.root / 'attempts/0000.json').exists())
            with self.assertRaises(proto.JournalBlocked):
                self.journal.status()

    def test_process_exit_before_atomic_replace_preserves_pending_and_old_records(self):
        original = (self.root / 'records.json').read_bytes()
        body = ("j=p.SyntheticJournal(sys.argv[2])\nwith j.locked():\n j.begin()\n"
                " p.os.replace=lambda *args: os._exit(27)\n"
                " j.commit_synthetic('sample', [7], True, 'a'*64)\n")
        result = self.child(body)
        self.assertEqual(result.returncode, 27, result.stderr)
        self.assertEqual((self.root / 'records.json').read_bytes(), original)
        self.assertTrue(list(self.root.glob('.pending-*.json')))
        self.assertTrue((self.root / 'attempts/0000.json').exists())
        with self.journal.locked():
            with self.assertRaises(proto.JournalBlocked):
                self.journal.status()

    def test_process_exit_after_replace_before_directory_sync_keeps_visible_record(self):
        body = ("j=p.SyntheticJournal(sys.argv[2])\nwith j.locked():\n j.begin()\n"
                " real_replace=p.os.replace\n"
                " def replace_then_exit(*args):\n  real_replace(*args)\n  os._exit(28)\n"
                " p.os.replace=replace_then_exit\n"
                " j.commit_synthetic('sample', [7], True, 'a'*64)\n")
        result = self.child(body)
        self.assertEqual(result.returncode, 28, result.stderr)
        with self.journal.locked():
            self.assertEqual(self.journal.status()['declared_records'], 1)
            self.assertEqual(self.journal.begin()['index'], 1)

    def test_corrupt_marker_is_not_removed_or_retried(self):
        with self.journal.locked():
            self.journal.begin()
            marker = self.root / 'attempts/0000.json'
            marker.write_text('{', encoding='utf-8')
            with self.assertRaises(proto.JournalBlocked):
                self.journal.begin()
            self.assertEqual(marker.read_text(), '{')

    def test_tampered_synthetic_output_hash_stops(self):
        with self.journal.locked():
            self.commit()
            path = self.root / 'records.json'
            data = json.loads(path.read_text())
            data['records'][0]['synthetic_text'] = 'modified'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(proto.JournalBlocked):
                self.journal.status()

    def test_smoke_failure_cannot_be_skipped(self):
        with self.journal.locked():
            for i in range(4):
                self.commit(eos=i != 1)
            self.assertFalse(self.journal.check_smoke()['passed'])
            self.assertEqual(self.journal.status()['state'], 'blocked_failed_smoke')
            with self.assertRaises(proto.JournalBlocked):
                self.journal.begin()

    def test_empty_smoke_output_fails_even_with_eos(self):
        with self.journal.locked():
            for i in range(4):
                self.commit(text='' if i == 2 else 'synthetic')
            self.assertFalse(self.journal.check_smoke()['passed'])
            self.assertEqual(self.journal.status()['state'], 'blocked_failed_smoke')

    def test_external_fifth_marker_cannot_skip_smoke(self):
        with self.journal.locked():
            for _ in range(4):
                self.commit()
            i = 4
            marker = {'index': i, 'id': self.journal.plan['ordered_ids'][i], 'plan_sha256': self.journal.plan_sha}
            (self.root / 'attempts/0004.json').write_text(json.dumps(marker), encoding='utf-8')
            with self.assertRaises(proto.JournalBlocked):
                self.journal.commit_synthetic('sample', [3], True, 'a' * 64)
            self.assertEqual(len(json.loads((self.root / 'records.json').read_text())['records']), 4)

    def test_invalid_output_does_not_remove_attempt(self):
        with self.journal.locked():
            self.journal.begin()
            with self.assertRaises(proto.JournalBlocked):
                self.journal.commit_synthetic('sample', [3], False, 'a' * 64)
            self.assertEqual(self.journal.status()['state'], 'blocked_uncommitted_attempt')
            self.assertTrue((self.root / 'attempts/0000.json').exists())

    def test_recorded_failure_blocks(self):
        with self.journal.locked():
            (self.root / 'failure.json').write_text(json.dumps({'reason': 'simulated disk error'}), encoding='utf-8')
            self.assertEqual(self.journal.status()['state'], 'blocked_recorded_failure')
            with self.assertRaises(proto.JournalBlocked):
                self.journal.begin()

    def test_incomplete_init_refuses_to_overwrite_or_repair(self):
        with tempfile.TemporaryDirectory(prefix='kba-scope-incomplete-') as tmp:
            root = Path(tmp)
            (root / 'manifest.json').write_text('{', encoding='utf-8')
            journal = proto.SyntheticJournal(root)
            with journal.locked():
                with self.assertRaises(proto.JournalBlocked):
                    journal.initialize()
            self.assertEqual((root / 'manifest.json').read_text(), '{')

    def test_lock_required_and_non_tmp_root_rejected(self):
        with self.assertRaises(proto.JournalBlocked):
            self.journal.status()
        with self.assertRaises(proto.JournalBlocked):
            proto.SyntheticJournal(ROOT)

    def test_symlink_entry_is_rejected(self):
        with self.journal.locked():
            os.symlink('missing-target', self.root / 'smoke.json')
            with self.assertRaises(proto.JournalBlocked):
                self.journal.status()


if __name__ == '__main__':
    unittest.main()
