"""Production-path mechanics with temporary runs, mocked gates and synthetic CPU output."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import evidence_experiment as renderer
import explanation_scope_cache_writer_fixture as cache
import explanation_scope_disk_cache as disk
import explanation_scope_generation_fixture as generation
import explanation_scope_production as production
import explanation_scope_runtime as scope
import explanation_scope_transaction_prototype as transaction


class ProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = scope.Runtime()
        cls.tokens = cls.runtime.tokenizer.encode('synthetic output', add_special_tokens=False) + [cls.runtime.eos_ids[0]]

    def test_closed_gate_precedes_directory_device_and_model_access(self):
        with patch.object(production, '_open_run') as open_run, \
             patch.object(production, '_verify_device') as device, \
             patch.object(renderer, 'load_model') as load:
            with self.assertRaises(PermissionError):
                production.collect(self.runtime)
            open_run.assert_not_called()
            device.assert_not_called()
            load.assert_not_called()

    def test_closed_gate_also_blocks_direct_storage_entry_points(self):
        with patch.object(production.os, 'mkdir') as mkdir, patch.object(production.os, 'open') as open_file:
            with self.assertRaises(PermissionError):
                production._open_run(self.runtime)
            with self.assertRaises(PermissionError):
                production.ProductionCacheWriter(self.runtime)
            with self.assertRaises(PermissionError):
                cache._CacheWriterCore(disk.DEFAULT_RUN, self.runtime, synthetic_fixture=False)
            mkdir.assert_not_called()
            open_file.assert_not_called()

    def test_real_input_snapshot_detects_changed_input(self):
        production._verify_input_snapshot(self.runtime)
        item = self.runtime.plan['ordered_ids'][0]
        saved = self.runtime.inputs[item]['prompt_sha256']
        try:
            self.runtime.inputs[item]['prompt_sha256'] = '0' * 64
            with self.assertRaises(ValueError):
                production._verify_input_snapshot(self.runtime)
        finally:
            self.runtime.inputs[item]['prompt_sha256'] = saved

    def test_all_seven_model_file_hashes_checked_and_tampering_rejected(self):
        names = list(self.runtime.reference['model_files_sha256'])
        with tempfile.TemporaryDirectory(prefix='kba-production-model-fixture-') as directory:
            root = Path(directory)
            files = {}
            for name in names:
                data = ('fixture:' + name).encode()
                (root / name).write_bytes(data)
                files[name] = hashlib.sha256(data).hexdigest()
            fake = SimpleNamespace(model_dir=root, reference={'model_files_sha256': files})
            production._verify_model_files(fake)
            (root / 'model-00002-of-00002.safetensors').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                production._verify_model_files(fake)

    def test_device_check_rejects_busy_or_unsupported_device(self):
        with patch.object(torch.cuda, 'is_available', return_value=True), \
             patch.object(torch.cuda, 'device_count', return_value=1), \
             patch.object(torch.cuda, 'is_bf16_supported', return_value=True), \
             patch.object(subprocess, 'run', return_value=SimpleNamespace(stdout='')) as query:
            production._verify_device()
            query.return_value = SimpleNamespace(stdout='123, busy, 100 MiB')
            with self.assertRaises(RuntimeError):
                production._verify_device()
        with patch.object(torch.cuda, 'is_available', return_value=False), \
             patch.object(subprocess, 'run', return_value=SimpleNamespace(stdout='')):
            with self.assertRaises(RuntimeError):
                production._verify_device()

    def test_model_device_must_be_the_single_visible_cuda_device(self):
        for name in ('cpu', 'cuda:1'):
            with self.subTest(device=name), self.assertRaises(ValueError):
                production._model_device(SimpleNamespace(device=name))
        self.assertEqual(production._model_device(SimpleNamespace(device='cuda:0')).index, 0)

    def patches(self, directory):
        """Override only in this test process; all writes remain marked synthetic in temp."""
        stack = ExitStack()
        root = Path(directory)
        (root / 'runs').mkdir()
        stack.enter_context(patch.object(disk, 'ROOT', root))
        stack.enter_context(patch.object(disk, 'DEFAULT_RUN', root / 'runs' / 'fixture'))
        stack.enter_context(patch.object(self.runtime, 'assert_collection_disabled', return_value=None))
        return stack

    def synthetic_writer(self):
        writer, created = production._open_run(self.runtime)
        # Same production transaction methods, but test artifacts remain explicitly synthetic.
        writer.synthetic_fixture = True
        return writer, created

    def test_production_transaction_resumes_and_blocks_tampering_or_stale_attempt(self):
        with tempfile.TemporaryDirectory(prefix='kba-production-fixture-') as directory, self.patches(directory):
            writer, created = self.synthetic_writer()
            self.assertTrue(created)
            with writer.locked():
                writer.initialize()
                writer.begin()
                writer.commit_tokens(self.tokens, 0.01, '2026-11-06T08:00:00+00:00')
            writer2, created = self.synthetic_writer()
            self.assertFalse(created)
            with writer2.locked():
                self.assertEqual(writer2.status()['records'], 1)
                writer2.begin()
            with writer2.locked():
                self.assertEqual(writer2.status()['state'], 'blocked_uncommitted_attempt')
                with self.assertRaises(transaction.JournalBlocked):
                    writer2.commit_tokens(self.tokens, 0.01, '2026-11-06T08:00:00+00:00')
            record_path = disk.DEFAULT_RUN / 'records.json'
            value = json.loads(record_path.read_text())
            value['records'][0]['raw_output_sha256'] = '0' * 64
            record_path.write_text(json.dumps(value))
            with writer2.locked(), self.assertRaises(transaction.JournalBlocked):
                writer2.status()

    def test_production_lock_conflict_and_failed_replace_preserve_evidence(self):
        with tempfile.TemporaryDirectory(prefix='kba-production-fixture-') as directory, self.patches(directory):
            writer, _ = self.synthetic_writer()
            with writer.locked():
                writer.initialize()
                result = subprocess.run(['flock', '-n', str(disk.DEFAULT_RUN / '.lock'), 'true'], timeout=10)
                self.assertNotEqual(result.returncode, 0)
                writer.begin()
                with patch.object(transaction.os, 'replace', side_effect=OSError('fixture fault')):
                    with self.assertRaises(OSError):
                        writer.commit_tokens(self.tokens, 0.01, '2026-11-06T08:00:00+00:00')
                with self.assertRaises(transaction.JournalBlocked):
                    writer.status()
            self.assertTrue(any(p.name.startswith('.pending-') for p in disk.DEFAULT_RUN.iterdir()))
            with writer.locked(), self.assertRaises(transaction.JournalBlocked):
                writer.status()

    def test_another_process_dies_after_attempt_and_restart_blocks(self):
        with tempfile.TemporaryDirectory(prefix='kba-production-fixture-') as directory, self.patches(directory):
            writer, _ = self.synthetic_writer()
            with writer.locked():
                writer.initialize()
                writer.begin()
                writer.commit_tokens(self.tokens, 0.01, '2026-11-06T08:00:00+00:00')
            code = (
                "import os,sys\nfrom pathlib import Path\nfrom unittest.mock import patch\n"
                "sys.path.insert(0,sys.argv[1])\n"
                "import explanation_scope_runtime as s, explanation_scope_disk_cache as d, explanation_scope_production as p\n"
                "rt=s.Runtime()\nroot=Path(sys.argv[2])\n"
                "with patch.object(d,'ROOT',root), patch.object(d,'DEFAULT_RUN',root/'runs'/'fixture'), "
                "patch.object(rt,'assert_collection_disabled',return_value=None):\n"
                " w=p.ProductionCacheWriter(rt)\n w.synthetic_fixture=True\n"
                " with w.locked():\n  assert w.status()['records']==1\n  w.begin()\n  os._exit(0)\n"
            )
            result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'scripts'), directory],
                                    capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            with writer.locked():
                self.assertEqual(writer.status()['state'], 'blocked_uncommitted_attempt')
                with self.assertRaises(transaction.JournalBlocked):
                    writer.begin()

    def _fake_model(self):
        model = generation.SyntheticModel(self.tokens)
        model.device = torch.device('cpu')
        config = generation._config(self.runtime)
        model.generation_config = SimpleNamespace(eos_token_id=self.runtime.eos_ids, bos_token_id=config.bos_token_id)
        model.config = SimpleNamespace(max_position_embeddings=self.runtime.reference['context_tokens'])
        return model

    def test_collect_full_path_on_mock_cpu_and_synthetic_temp_storage(self):
        with tempfile.TemporaryDirectory(prefix='kba-production-fixture-') as directory, self.patches(directory):
            model = self._fake_model()
            original_open = production._open_run
            def synthetic_open(runtime):
                writer, created = original_open(runtime)
                writer.synthetic_fixture = True
                return writer, created
            with patch.object(production, '_open_run', side_effect=synthetic_open), \
                 patch.object(production, '_verify_input_snapshot'), patch.object(production, '_verify_model_files'), \
                 patch.object(production, '_verify_device'), patch.object(production, '_model_device', return_value=torch.device('cpu')), \
                 patch.object(torch.cuda, 'synchronize'), patch.object(renderer, 'load_model', return_value=model):
                state = production.collect(self.runtime)
            self.assertEqual((state['state'], state['records']), ('validated_complete_unreviewed', 48))
            inspected = disk.inspect_cache(disk.DEFAULT_RUN, self.runtime)
            self.assertTrue(inspected['synthetic_fixture_only'])
            self.assertFalse(inspected['output_origin_verified'])

    def test_collect_generation_failure_blocks_restart_before_model_load(self):
        with tempfile.TemporaryDirectory(prefix='kba-production-fixture-') as directory, self.patches(directory):
            model = self._fake_model()
            original_open = production._open_run
            def synthetic_open(runtime):
                writer, created = original_open(runtime)
                writer.synthetic_fixture = True
                return writer, created
            with patch.object(production, '_open_run', side_effect=synthetic_open), \
                 patch.object(production, '_verify_input_snapshot'), patch.object(production, '_verify_model_files'), \
                 patch.object(production, '_verify_device'), patch.object(production, '_model_device', return_value=torch.device('cpu')), \
                 patch.object(torch.cuda, 'synchronize'), patch.object(renderer, 'load_model', return_value=model) as loader, \
                 patch.object(model, 'generate', side_effect=RuntimeError('synthetic generation fault')):
                with self.assertRaises(RuntimeError):
                    production.collect(self.runtime)
                loader.reset_mock()
                with self.assertRaises(transaction.JournalBlocked):
                    production.collect(self.runtime)
                loader.assert_not_called()
            self.assertTrue((disk.DEFAULT_RUN / 'attempts' / '0000.json').is_file())

    def test_preexisting_incomplete_directory_is_never_reinitialized(self):
        with tempfile.TemporaryDirectory(prefix='kba-production-fixture-') as directory, self.patches(directory):
            writer, created = self.synthetic_writer()
            self.assertTrue(created)
            writer2, created = self.synthetic_writer()
            self.assertFalse(created)
            with writer2.locked(), self.assertRaises(transaction.JournalBlocked):
                writer2.status()
            self.assertFalse((disk.DEFAULT_RUN / 'manifest.json').exists())

    def test_collect_failed_smoke_prevents_fifth_and_later_model_reload(self):
        with tempfile.TemporaryDirectory(prefix='kba-production-fixture-') as directory, self.patches(directory):
            model = self._fake_model()
            model.token_ids = [self.runtime.eos_ids[0]]
            original_open = production._open_run
            def synthetic_open(runtime):
                writer, created = original_open(runtime)
                writer.synthetic_fixture = True
                return writer, created
            with patch.object(production, '_open_run', side_effect=synthetic_open), \
                 patch.object(production, '_verify_input_snapshot'), patch.object(production, '_verify_model_files'), \
                 patch.object(production, '_verify_device'), patch.object(production, '_model_device', return_value=torch.device('cpu')), \
                 patch.object(torch.cuda, 'synchronize'), patch.object(renderer, 'load_model', return_value=model) as loader, \
                 patch.object(model, 'generate', wraps=model.generate) as generated:
                with self.assertRaises(transaction.JournalBlocked):
                    production.collect(self.runtime)
                self.assertEqual(generated.call_count, 4)
                loader.reset_mock()
                with self.assertRaises(transaction.JournalBlocked):
                    production.collect(self.runtime)
                loader.assert_not_called()
            self.assertFalse(json.loads((disk.DEFAULT_RUN / 'smoke.json').read_text())['passed'])


if __name__ == '__main__':
    unittest.main()
