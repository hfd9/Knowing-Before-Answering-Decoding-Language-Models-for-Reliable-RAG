"""Test user-operated E1 release exclusively with CPU mocks and temporary synthetic runs."""
from contextlib import ExitStack, redirect_stdout
import hashlib
import io
import json
import os
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
import explanation_scope_e1 as original
import explanation_scope_e1_intake as intake
import explanation_scope_e1_user_collection as user
import explanation_scope_generation_fixture as generation
import explanation_scope_ledger_simulator as ledger
import explanation_scope_production as production
import explanation_scope_runtime as scope
import explanation_scope_transaction_prototype as tx


class UserCollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = scope.Runtime()
        cls.tokens = cls.runtime.tokenizer.encode('synthetic user run', add_special_tokens=False) + [cls.runtime.eos_ids[0]]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='e1-user-test-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.run = self.base / 'run'
        self.plan_path = self.base / 'plan.json'
        self.release_path = self.base / 'release.json'
        self.evidence_path = self.base / 'evidence.json'
        self.review_path = self.base / 'review.md'
        self.review_path.write_text('Synthetic-only review fixture.\n')
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(user, 'E1_RUN', self.run))
        stack.enter_context(patch.object(user, 'USER_PLAN', self.plan_path))
        stack.enter_context(patch.object(user, 'USER_RELEASE', self.release_path))
        stack.enter_context(patch.object(user, 'USER_TEST_EVIDENCE', self.evidence_path))
        stack.enter_context(patch.object(user, 'USER_REVIEW', self.review_path))
        stack.enter_context(patch.dict(os.environ, {'CUDA_VISIBLE_DEVICES': '0'}, clear=False))
        source, source_sha = ledger.load_plan()
        self.plan = {'status': 'fixed_user_execution_plan_requires_release', 'operator': 'user',
            'gpu_index': 0, 'gpu_uuid': 'GPU-1652bafc-65ec-03e5-1c07-ccd400b237b5',
            'run_dir': 'runs/qwen2.5-3b-explanation-scope-e1-user-v1', 'ordered_ids': source['ordered_ids'],
            'smoke_ids': source['smoke_ids'], 'smoke_included_in_48': True, 'max_attempts': 48,
            'max_attempts_per_slot': 1, 'output_limit': 128, 'primary': 'mean_J_IU_minus_J_I0_over_12_scenes',
            'fit_budget': 0, 'held_out_380_accessed': False, 'independent_approvals': 0,
            'source_plan_sha256': source_sha,
            'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in user.USER_SOURCE_FILES}}
        self.plan_path.write_text(json.dumps(self.plan))
        evidence = {'status': 'all_user_execution_cpu_tests_passed',
                    'user_script_sha256': hashlib.sha256((ROOT / 'scripts/explanation_scope_e1_user_collection.py').read_bytes()).hexdigest(),
                    'test_file_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'tests_passed': 8, 'gpu_inference_performed': False, 'fixture': True}
        self.evidence_path.write_text(json.dumps(evidence))
        _, plan_sha = user.check_user_plan()
        self.release_path.write_text(json.dumps(user.expected_release(plan_sha)))

    def model(self, bad_fifth=False):
        model = generation.SyntheticModel(self.tokens)
        model.device = torch.device('cpu')
        config = generation._config(self.runtime)
        model.generation_config = SimpleNamespace(eos_token_id=self.runtime.eos_ids, bos_token_id=config.bos_token_id)
        model.config = SimpleNamespace(max_position_embeddings=self.runtime.reference['context_tokens'])
        original_generate = model.generate
        calls = []
        def generate(**kwargs):
            calls.append(1)
            model.token_ids = [self.runtime.eos_ids[0]] if bad_fifth and len(calls) == 5 else self.tokens
            return original_generate(**kwargs)
        return model, calls, generate

    def collect_patches(self, model, generate):
        stack = ExitStack()
        original_writer = user.Writer
        def fixture_writer(path, runtime, *, synthetic_fixture):
            return original_writer(path, runtime, synthetic_fixture=True)
        stack.enter_context(patch.object(user.scope, 'Runtime', return_value=self.runtime))
        stack.enter_context(patch.object(user, 'Writer', side_effect=fixture_writer))
        stack.enter_context(patch.object(user, 'verify_device'))
        stack.enter_context(patch.object(production, '_model_device', return_value=torch.device('cpu')))
        stack.enter_context(patch.object(torch.cuda, 'synchronize'))
        stack.enter_context(patch.object(renderer, 'load_model', return_value=model))
        stack.enter_context(patch.object(model, 'generate', side_effect=generate))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return stack

    def test_missing_release_rejects_before_runtime_or_run_creation(self):
        self.release_path.unlink()
        with patch.object(user.scope, 'Runtime') as runtime, patch.object(user, 'verify_device') as device:
            with self.assertRaises((PermissionError, ValueError)):
                user.collect()
        runtime.assert_not_called()
        device.assert_not_called()
        self.assertFalse(self.run.exists())

    def test_plan_source_or_review_or_test_evidence_tampering_blocks_release(self):
        user.assert_user_release()
        original_plan = self.plan_path.read_text()
        self.plan['source_sha256']['scripts/explanation_scope_e1_user_collection.py'] = '0' * 64
        self.plan_path.write_text(json.dumps(self.plan))
        with self.assertRaises(PermissionError):
            user.assert_user_release()
        self.plan_path.write_text(original_plan)
        self.review_path.write_text('Changed review fixture.\n')
        with self.assertRaises(PermissionError):
            user.assert_user_release()

    def test_original_gate_stays_closed(self):
        user.assert_user_release()
        with self.assertRaises(PermissionError):
            original.assert_collection_disabled()

    def test_gpu_busy_does_not_create_new_run_or_load_model(self):
        with patch.object(user.scope, 'Runtime', return_value=self.runtime), \
             patch.object(user, 'verify_device', side_effect=RuntimeError('GPU busy')), \
             patch.object(renderer, 'load_model') as loader:
            with self.assertRaisesRegex(RuntimeError, 'GPU busy'):
                user.collect()
        loader.assert_not_called()
        self.assertFalse(self.run.exists())

    def test_physical_gpu_identity_and_busy_checks_are_called(self):
        response = SimpleNamespace(stdout=self.plan['gpu_uuid'] + '\n')
        with patch.object(user.subprocess, 'run', return_value=response) as query, \
             patch.object(production, '_verify_model_files') as weights, \
             patch.object(production, '_verify_device') as device:
            user.verify_device(self.runtime)
        self.assertIn('--query-gpu=uuid', query.call_args.args[0])
        weights.assert_called_once_with(self.runtime)
        device.assert_called_once()
        response.stdout = 'GPU-wrong\n'
        with patch.object(user.subprocess, 'run', return_value=response), \
             patch.object(production, '_verify_device') as device:
            with self.assertRaisesRegex(RuntimeError, 'UUID'):
                user.verify_device(self.runtime)
        device.assert_not_called()

    def test_full_48_generated_only_by_mock_cpu_and_no_reanswer_on_resume(self):
        model, calls, generate = self.model()
        with self.collect_patches(model, generate):
            self.assertEqual(user.collect(), {'state': 'validated_complete_unreviewed', 'records': 48})
            self.assertEqual(user.collect(), {'state': 'validated_complete_unreviewed', 'records': 48})
        self.assertEqual(len(calls), 48)
        self.assertTrue(json.loads((self.run / 'manifest.json').read_text())['synthetic_fixture'])
        self.assertEqual(len(list((self.run / 'attempts').iterdir())), 48)
        original_writer = user.Writer
        with patch.object(user.scope, 'Runtime', return_value=self.runtime), \
             patch.object(user, 'Writer', side_effect=lambda path, runtime, synthetic_fixture: original_writer(path, runtime, synthetic_fixture=True)), \
             patch.object(user, 'verify_device') as device, patch.object(renderer, 'load_model') as loader:
            inspection = user.inspect_cache()
            packaged = user.package_cache()
        self.assertEqual((inspection['status'], inspection['committed_records'], inspection['attempts']),
                         ('validated_complete_unreviewed', 48, 48))
        self.assertEqual(packaged['planned_slots'], 48)
        device.assert_not_called()
        loader.assert_not_called()
        public = Path(packaged['public_directory'])
        private = Path(packaged['coordinator_directory'])
        packet = json.loads(next(public.glob('packet-*.json')).read_text())
        coordinator = json.loads(next(private.glob('coordinator-*.json')).read_text())
        seal = json.loads(next(private.glob('seal-*.json')).read_text())
        self.assertEqual(len(intake.validate_coordinator(packet, coordinator, seal)['rows']), 48)
        self.assertEqual(coordinator['operator'], 'user')

    def test_fifth_empty_stops_and_resume_never_calls_gpu_or_model(self):
        model, calls, generate = self.model(bad_fifth=True)
        with self.collect_patches(model, generate):
            with self.assertRaises(tx.JournalBlocked):
                user.collect()
        self.assertEqual(len(calls), 5)
        # Reopen explicitly with the actual synthetic writer, then exercise collect in a fresh patch context.
        original_writer = user.Writer
        with patch.object(user.scope, 'Runtime', return_value=self.runtime), \
             patch.object(user, 'Writer', side_effect=lambda path, runtime, synthetic_fixture: original_writer(path, runtime, synthetic_fixture=True)), \
             patch.object(user, 'verify_device') as device, patch.object(renderer, 'load_model') as loader:
            with self.assertRaises(tx.JournalBlocked):
                user.collect()
            inspection = user.inspect_cache()
            packaged = user.package_cache()
        device.assert_not_called()
        loader.assert_not_called()
        self.assertEqual(len(list((self.run / 'attempts').iterdir())), 5)
        self.assertEqual(inspection['status'], 'blocked_empty')
        self.assertEqual(inspection['technical_counts'], {'complete': 4, 'empty': 1})
        self.assertEqual(packaged['source_cache_state'], 'blocked_empty')

    def test_release_and_plan_cannot_be_enabled_by_cli_flag(self):
        self.release_path.unlink()
        with self.assertRaises((PermissionError, ValueError)):
            user.assert_user_release()
        with self.assertRaises(PermissionError):
            original.assert_collection_disabled()


if __name__ == '__main__':
    unittest.main()
