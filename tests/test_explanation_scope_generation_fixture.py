"""CPU tensors, real local tokenizer, and fabricated output tokens only."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import explanation_scope_cache_writer_fixture as cache
import explanation_scope_disk_cache as disk
import explanation_scope_generation_fixture as generation
import explanation_scope_runtime as scope
import explanation_scope_transaction_prototype as transaction


class GenerationFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = scope.Runtime()
        cls.ids = cls.runtime.tokenizer.encode('synthetic output', add_special_tokens=False) + [cls.runtime.eos_ids[0]]

    def writer(self, directory):
        return cache.FixtureCacheWriter(directory, self.runtime)

    def test_tensor_path_matches_input_and_frozen_generation_parameters(self):
        with tempfile.TemporaryDirectory(prefix='kba-generation-fixture-') as directory:
            writer = self.writer(directory)
            fake = generation.SyntheticModel(self.ids)
            original = fake.generate
            with writer.locked():
                writer.initialize()
                with patch.object(fake, 'generate', wraps=original) as called:
                    result = generation.run_one(self.runtime, writer, fake)
                args = called.call_args.kwargs
                config = args['generation_config']
                expected = self.runtime.generation_input(result['id'])
                self.assertEqual(args['input_ids'].tolist(), [expected['input_ids']])
                self.assertEqual(args['attention_mask'].tolist(), [[1] * len(expected['input_ids'])])
                self.assertEqual(args['input_ids'].device.type, 'cpu')
                self.assertEqual((config.max_new_tokens, config.do_sample, config.num_beams, config.use_cache),
                                 (128, False, 1, True))
                self.assertEqual(config.eos_token_id, self.runtime.eos_ids)
                self.assertEqual(args['logits_to_keep'], 1)
                self.assertEqual(result['generated_token_ids'], self.ids)
            inspected = disk.inspect_cache(directory, self.runtime)
            self.assertEqual(inspected['records'], 1)
            self.assertTrue(inspected['synthetic_fixture_only'])
            self.assertFalse(inspected['output_origin_verified'])

    def test_model_error_preserves_attempt_and_prevents_retry(self):
        with tempfile.TemporaryDirectory(prefix='kba-generation-fixture-') as directory:
            writer = self.writer(directory)
            fake = generation.SyntheticModel(self.ids)
            with writer.locked():
                writer.initialize()
                with patch.object(fake, 'generate', side_effect=RuntimeError('synthetic failure')):
                    with self.assertRaises(RuntimeError):
                        generation.run_one(self.runtime, writer, fake)
                self.assertEqual(writer.status()['state'], 'blocked_uncommitted_attempt')
                with self.assertRaises(transaction.JournalBlocked):
                    generation.run_one(self.runtime, writer, fake)
            with writer.locked():
                self.assertEqual(writer.status()['state'], 'blocked_uncommitted_attempt')

    def test_malformed_or_mutated_model_output_blocks_commit(self):
        def corrupt_prefix(**kwargs):
            inputs = kwargs['input_ids'].clone()
            inputs[0, 0] += 1
            return torch.cat((inputs, torch.tensor([self.ids])), dim=1)

        def mutate_inputs(**kwargs):
            kwargs['input_ids'][0, 0] += 1
            return torch.cat((kwargs['input_ids'], torch.tensor([self.ids])), dim=1)

        cases = [lambda **k: torch.tensor(self.ids), corrupt_prefix, mutate_inputs,
                 lambda **k: k['input_ids'],
                 lambda **k: torch.cat((k['input_ids'], torch.tensor([[1]])), dim=1)]
        for callback in cases:
            with self.subTest(callback=callback), tempfile.TemporaryDirectory(prefix='kba-generation-fixture-') as directory:
                writer = self.writer(directory)
                fake = generation.SyntheticModel(self.ids)
                with writer.locked():
                    writer.initialize()
                    with patch.object(fake, 'generate', side_effect=callback):
                        with self.assertRaises(ValueError):
                            generation.run_one(self.runtime, writer, fake)
                    self.assertEqual(writer.status()['state'], 'blocked_uncommitted_attempt')

    def test_failed_smoke_prevents_fifth_model_call(self):
        with tempfile.TemporaryDirectory(prefix='kba-generation-fixture-') as directory:
            writer = self.writer(directory)
            fake = generation.SyntheticModel([self.runtime.eos_ids[0]])
            with writer.locked():
                writer.initialize()
                for _ in range(4):
                    generation.run_one(self.runtime, writer, fake)
                self.assertFalse(writer.check_smoke()['passed'])
                with patch.object(fake, 'generate', wraps=fake.generate) as called:
                    with self.assertRaises(transaction.JournalBlocked):
                        generation.run_one(self.runtime, writer, fake)
                    called.assert_not_called()
                self.assertEqual(writer.status()['records'], 4)

    def test_passed_smoke_allows_fifth_fixture(self):
        with tempfile.TemporaryDirectory(prefix='kba-generation-fixture-') as directory:
            writer = self.writer(directory)
            fake = generation.SyntheticModel(self.ids)
            with writer.locked():
                writer.initialize()
                for _ in range(4):
                    generation.run_one(self.runtime, writer, fake)
                self.assertTrue(writer.check_smoke()['passed'])
                record = generation.run_one(self.runtime, writer, fake)
                self.assertEqual(record['index'], 4)
                self.assertEqual(writer.status()['records'], 5)

    def test_changed_config_or_plan_stops_before_attempt(self):
        with tempfile.TemporaryDirectory(prefix='kba-generation-fixture-') as directory:
            writer = self.writer(directory)
            fake = generation.SyntheticModel(self.ids)
            with writer.locked():
                writer.initialize()
                saved = self.runtime.metadata_hashes['generation_config.json']
                try:
                    self.runtime.metadata_hashes['generation_config.json'] = '0' * 64
                    with self.assertRaises(ValueError):
                        generation.run_one(self.runtime, writer, fake)
                finally:
                    self.runtime.metadata_hashes['generation_config.json'] = saved
                saved = self.runtime.plan['generation']['sample']
                try:
                    self.runtime.plan['generation']['sample'] = True
                    with self.assertRaises(ValueError):
                        generation.run_one(self.runtime, writer, fake)
                finally:
                    self.runtime.plan['generation']['sample'] = saved
                self.assertEqual(list((Path(directory) / 'attempts').iterdir()), [])

    def test_output_limit_is_recorded_and_tokens_after_eos_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix='kba-generation-fixture-') as directory:
            writer = self.writer(directory)
            fake = generation.SyntheticModel([self.ids[0]] * 128)
            with writer.locked():
                writer.initialize()
                record = generation.run_one(self.runtime, writer, fake)
                self.assertTrue(record['hit_output_limit'])
                self.assertFalse(record['ended_with_eos'])
        with tempfile.TemporaryDirectory(prefix='kba-generation-fixture-') as directory:
            writer = self.writer(directory)
            fake = generation.SyntheticModel([self.runtime.eos_ids[0], self.ids[0]])
            with writer.locked():
                writer.initialize()
                with self.assertRaises(ValueError):
                    generation.run_one(self.runtime, writer, fake)
                self.assertEqual(writer.status()['state'], 'blocked_uncommitted_attempt')

    def test_production_and_arbitrary_models_are_rejected(self):
        before = disk.DEFAULT_RUN.exists()
        with self.assertRaises(PermissionError):
            generation.production_generate(self.runtime)
        with tempfile.TemporaryDirectory(prefix='kba-generation-fixture-') as directory:
            writer = self.writer(directory)
            with writer.locked():
                writer.initialize()
                with self.assertRaises(TypeError):
                    generation.run_one(self.runtime, writer, object())
                self.assertEqual(writer.status()['records'], 0)
        self.assertEqual(disk.DEFAULT_RUN.exists(), before)


if __name__ == '__main__':
    unittest.main()
