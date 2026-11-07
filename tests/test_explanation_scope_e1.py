"""Real local tokenizer, temporary synthetic caches only; never load model weights or GPU."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import explanation_scope_e1 as e1
import explanation_scope_generation_fixture as generation
import explanation_scope_metrics as metrics
import explanation_scope_production as production
import explanation_scope_runtime as scope
import explanation_scope_transaction_prototype as tx
import evidence_experiment as renderer
import torch


class E1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = scope.Runtime()
        cls.good = cls.runtime.tokenizer.encode('synthetic answer', add_special_tokens=False) + [cls.runtime.eos_ids[0]]
        cls.empty = [cls.runtime.eos_ids[0]]
        cls.truncated = [cls.good[0]] * 128
        cls.when = '2026-11-07T10:00:00+00:00'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='e1-test-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.run = self.base / 'run'
        self.run.mkdir(mode=0o700)
        self.public = self.base / 'run.review-public'
        self.private = self.base / 'run.review-private'
        self.public.mkdir(mode=0o700)
        self.private.mkdir(mode=0o700)
        self.writer = e1.Writer(self.run, self.runtime, synthetic_fixture=True)
        with self.writer.locked():
            self.writer.initialize()

    def add(self, writer, tokens=None):
        marker = writer.begin()
        record = writer.commit_tokens(self.good if tokens is None else tokens, 0.01, self.when)
        self.assertEqual(marker['id'], record['id'])
        return record

    def prepare(self, n):
        with self.writer.locked():
            for _ in range(n):
                if self.writer.status()['state'] == 'awaiting_technical_smoke':
                    self.writer.check_smoke()
                self.add(self.writer)
            if self.writer.status()['state'] == 'awaiting_technical_smoke':
                self.writer.check_smoke()

    def test_default_gate_precedes_runtime_directory_or_model(self):
        with patch.object(e1.scope, 'Runtime') as runtime, patch.object(e1.os, 'mkdir') as mkdir:
            with self.assertRaises(PermissionError):
                e1.collect()
            with self.assertRaises(PermissionError):
                e1.Writer(e1.E1_RUN, self.runtime, synthetic_fixture=False)
            runtime.assert_not_called()
            mkdir.assert_not_called()

    def test_implementation_lock_tampering_blocks_existing_cache(self):
        altered = json.loads(e1.IMPLEMENTATION_LOCK.read_text())
        altered['implementation_sha256']['scripts/explanation_scope_e1.py'] = '0' * 64
        fake = self.base / 'altered-lock.json'
        fake.write_text(json.dumps(altered))
        with patch.object(e1, 'IMPLEMENTATION_LOCK', fake):
            with self.writer.locked(), self.assertRaises(tx.JournalBlocked):
                self.writer.status()

    def test_empty_and_truncated_stop_immediately_before_and_after_smoke_and_restart(self):
        for n in (0, 3, 4):
            for bad, expected in ((self.empty, 'blocked_empty'), (self.truncated, 'blocked_truncated')):
                with self.subTest(prefix=n, state=expected), tempfile.TemporaryDirectory(prefix='e1-case-') as directory:
                    run = Path(directory) / 'run'
                    run.mkdir()
                    writer = e1.Writer(run, self.runtime, synthetic_fixture=True)
                    with writer.locked():
                        writer.initialize()
                        for _ in range(n):
                            self.add(writer)
                        if n == 4:
                            writer.check_smoke()
                        record = self.add(writer, bad)
                        self.assertEqual(writer.status()['state'], expected)
                        self.assertEqual(record['generated_token_ids'], bad)
                        with self.assertRaises(tx.JournalBlocked):
                            writer.begin()
                    resumed = e1.Writer(run, self.runtime, synthetic_fixture=True)
                    with resumed.locked():
                        self.assertEqual(resumed.status(), {'state': expected, 'records': n + 1})
                        with self.assertRaises(tx.JournalBlocked):
                            resumed.begin()
                        self.assertEqual(len(list((run / 'attempts').iterdir())), n + 1)

    def test_limit_with_final_eos_is_valid_and_clean_prefix_resumes(self):
        exact = [self.good[0]] * 127 + [self.runtime.eos_ids[0]]
        with self.writer.locked():
            self.add(self.writer, exact)
            self.assertEqual(self.writer.status()['state'], 'validated_prefix')
        reopened = e1.Writer(self.run, self.runtime, synthetic_fixture=True)
        with reopened.locked():
            self.add(reopened)
            self.assertEqual(reopened.status(), {'state': 'validated_prefix', 'records': 2})

    def test_uncommitted_attempt_survives_reopen_and_cannot_be_filled(self):
        self.prepare(2)
        with self.writer.locked():
            marker = self.writer.begin()
        reopened = e1.Writer(self.run, self.runtime, synthetic_fixture=True)
        with reopened.locked():
            self.assertEqual(reopened.status()['state'], 'blocked_uncommitted_attempt')
            with self.assertRaises(tx.JournalBlocked):
                reopened.begin()
            with self.assertRaises(tx.JournalBlocked):
                reopened.commit_tokens(self.good, 0.01, self.when)
            public, private = e1.export_review(reopened, self.public, self.private)
        item = next(x for x in public['items'] if x['technical_status'] == 'failed')
        source = private['mapping_and_sources'][item['item_id']]
        self.assertEqual(source['source_item_id'], marker['id'])
        self.assertEqual(source['attempt_sha256'], hashlib.sha256((self.run / 'attempts/0002.json').read_bytes()).hexdigest())
        self.assertNotIn('answer', item)
        self.assertEqual(len(public['items']), 48)

    def test_partial_export_hides_conditions_binds_sources_and_preserves_mapping(self):
        self.prepare(2)
        with self.writer.locked():
            public1, private1 = e1.export_review(self.writer, self.public, self.private)
            first_mapping = {k: v['source_item_id'] for k, v in private1['mapping_and_sources'].items()}
            self.add(self.writer, self.empty)
            public2, private2 = e1.export_review(self.writer, self.public, self.private)
        self.assertEqual(first_mapping, {k: v['source_item_id'] for k, v in private2['mapping_and_sources'].items()})
        self.assertEqual([x['technical_status'] for x in public1['items']].count('complete'), 2)
        self.assertEqual([x['technical_status'] for x in public2['items']].count('empty'), 1)
        self.assertEqual([x['technical_status'] for x in public2['items']].count('not_collected'), 45)
        self.assertEqual(len(public2['items']), 48)
        serialized = json.dumps(public2)
        self.assertNotIn('exs01_', serialized)
        self.assertNotIn('source_item_id', serialized)
        self.assertNotIn('plan_sha256', serialized)
        for item in public2['items']:
            self.assertEqual(set(item), {'item_id', 'question', 'documents', 'technical_status'}
                             | ({'answer'} if item['technical_status'] == 'complete' else set()))
            source = private2['mapping_and_sources'][item['item_id']]
            self.assertEqual(source['technical_status'], item['technical_status'])
            if item['technical_status'] == 'complete':
                self.assertEqual(hashlib.sha256(item['answer'].encode()).hexdigest(), source['output_sha256'])
        indexed = metrics.validate(private2['endpoint_template'])
        self.assertEqual(len(indexed), 48)
        self.assertEqual(private2['endpoint_template']['e1_protocol_sha256'], e1.PROTOCOL_SHA256)
        self.assertEqual(sum(row['technical_status'] == 'empty' for row in indexed.values()), 1)
        self.assertTrue(all(row['review_status'] == 'unreviewed' for row in indexed.values()))
        summary = metrics.summarize(private2['endpoint_template'])
        self.assertIsNone(summary['primary']['point'])
        self.assertIsNone(summary['primary']['identification_lower'])
        self.assertEqual(len(list(self.public.glob('packet-*.json'))), 2)

    def test_empty_and_truncated_can_coexist_and_both_are_preserved(self):
        candidates = [token for token in self.runtime.tokenizer.all_special_ids
                      if token not in self.runtime.eos_ids
                      and not self.runtime.tokenizer.decode([token], skip_special_tokens=True).strip()]
        if not candidates:
            self.skipTest('tokenizer has no non-EOS special token')
        with self.writer.locked():
            self.add(self.writer, [candidates[0]] * 128)
            self.assertEqual(self.writer.status()['state'], 'blocked_empty')
            public, private = e1.export_review(self.writer, self.public, self.private)
        item = next(item for item in public['items'] if item['technical_status'] == 'empty')
        source = private['mapping_and_sources'][item['item_id']]
        self.assertTrue(source['empty_output'])
        self.assertTrue(source['hit_output_limit'])

    def test_tampered_cache_and_incomplete_or_changed_export_block(self):
        self.prepare(1)
        with self.writer.locked():
            e1.export_review(self.writer, self.public, self.private)
            packet = next(self.public.glob('packet-*.json'))
            packet.write_text('{}', encoding='utf-8')
            with self.assertRaises(tx.JournalBlocked):
                e1.export_review(self.writer, self.public, self.private)
        with tempfile.TemporaryDirectory(prefix='e1-tamper-') as tmp:
            run = Path(tmp) / 'run'
            run.mkdir()
            writer = e1.Writer(run, self.runtime, synthetic_fixture=True)
            with writer.locked():
                writer.initialize()
                self.add(writer)
                data = json.loads((run / 'records.json').read_text())
                data['records'][0]['raw_output'] = 'forged'
                (run / 'records.json').write_text(json.dumps(data))
                with self.assertRaises(tx.JournalBlocked):
                    writer.status()

    def test_forged_later_record_after_invalid_output_cannot_be_exported(self):
        with self.writer.locked():
            self.add(self.writer, self.empty)
            data = json.loads((self.run / 'records.json').read_text())
            data['records'].append(self.runtime.make_record(1, self.good, 0.01, self.when))
            (self.run / 'records.json').write_text(json.dumps(data))
            marker = {'index': 1, 'id': self.runtime.plan['ordered_ids'][1],
                      'plan_sha256': self.runtime.plan_sha, 'e1_protocol_sha256': e1.PROTOCOL_SHA256}
            (self.run / 'attempts/0001.json').write_text(json.dumps(marker))
            with self.assertRaises(tx.JournalBlocked):
                e1.export_review(self.writer, self.public, self.private)
        self.assertEqual(list(self.public.iterdir()), [])
        self.assertEqual(list(self.private.iterdir()), [])

    def test_partial_snapshot_marker_blocks_second_export(self):
        with self.writer.locked():
            e1.export_review(self.writer, self.public, self.private)
            (self.private / 'begin-incomplete.json').write_text('{}')
            with self.assertRaises(tx.JournalBlocked):
                e1.export_review(self.writer, self.public, self.private)

    def test_changing_persistent_mapping_after_sealed_export_blocks(self):
        with self.writer.locked():
            e1.export_review(self.writer, self.public, self.private)
            path = self.private / 'mapping.json'
            payload = json.loads(path.read_text())
            payload['mapping']['R001'], payload['mapping']['R002'] = payload['mapping']['R002'], payload['mapping']['R001']
            path.write_text(json.dumps(payload))
            with self.assertRaises(tx.JournalBlocked):
                e1.export_review(self.writer, self.public, self.private)

    def test_process_death_after_attempt_blocks_restart(self):
        code = (
            "import os,sys\nfrom pathlib import Path\n"
            "sys.path.insert(0,sys.argv[1])\n"
            "import explanation_scope_e1 as e, explanation_scope_runtime as s\n"
            "r=s.Runtime()\nw=e.Writer(Path(sys.argv[2]),r,synthetic_fixture=True)\n"
            "with w.locked():\n w.begin()\n os._exit(0)\n"
        )
        proc = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT / 'scripts'), str(self.run)],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with self.writer.locked():
            self.assertEqual(self.writer.status()['state'], 'blocked_uncommitted_attempt')
            with self.assertRaises(tx.JournalBlocked):
                self.writer.begin()

    def test_mocked_collect_stops_on_fifth_empty_and_restart_never_loads_model(self):
        model = generation.SyntheticModel(self.good)
        model.device = torch.device('cpu')
        config = generation._config(self.runtime)
        model.generation_config = SimpleNamespace(eos_token_id=self.runtime.eos_ids, bos_token_id=config.bos_token_id)
        model.config = SimpleNamespace(max_position_embeddings=self.runtime.reference['context_tokens'])
        original_generate, original_writer = model.generate, e1.Writer
        calls = []
        def generate(**kwargs):
            calls.append(1)
            model.token_ids = self.empty if len(calls) == 5 else self.good
            return original_generate(**kwargs)
        def fixture_writer(path, runtime, *, synthetic_fixture):
            return original_writer(path, runtime, synthetic_fixture=True)
        run = self.base / 'collect'
        with patch.object(e1, 'E1_RUN', run), patch.object(e1, 'assert_collection_disabled'), \
             patch.object(e1.scope, 'Runtime', return_value=self.runtime), \
             patch.object(e1, 'Writer', side_effect=fixture_writer), \
             patch.object(production, '_verify_model_files'), patch.object(production, '_verify_device'), \
             patch.object(production, '_model_device', return_value=torch.device('cpu')), \
             patch.object(torch.cuda, 'synchronize'), patch.object(renderer, 'load_model', return_value=model) as loader, \
             patch.object(model, 'generate', side_effect=generate):
            with self.assertRaises(tx.JournalBlocked):
                e1.collect()
            self.assertEqual(len(calls), 5)
            self.assertTrue(json.loads((run / 'manifest.json').read_text())['synthetic_fixture'])
            self.assertEqual(len(json.loads((run / 'records.json').read_text())['records']), 5)
            loader.reset_mock()
            with self.assertRaises(tx.JournalBlocked):
                e1.collect()
            loader.assert_not_called()
            self.assertEqual(len(calls), 5)

    def test_model_load_exception_persists_failure_and_blocks_automatic_restart(self):
        original_writer = e1.Writer
        def fixture_writer(path, runtime, *, synthetic_fixture):
            return original_writer(path, runtime, synthetic_fixture=True)
        run = self.base / 'failed-collect'
        with patch.object(e1, 'E1_RUN', run), patch.object(e1, 'assert_collection_disabled'), \
             patch.object(e1.scope, 'Runtime', return_value=self.runtime), \
             patch.object(e1, 'Writer', side_effect=fixture_writer), \
             patch.object(production, '_verify_model_files'), patch.object(production, '_verify_device'), \
             patch.object(renderer, 'load_model', side_effect=RuntimeError('synthetic failure')) as loader:
            with self.assertRaises(RuntimeError):
                e1.collect()
            self.assertEqual(json.loads((run / 'failure.json').read_text()),
                             {'reason': 'execution_exception:RuntimeError'})
            loader.reset_mock()
            with self.assertRaises(tx.JournalBlocked):
                e1.collect()
            loader.assert_not_called()

    def test_mocked_complete_collection_and_packet_keep_48_records(self):
        model = generation.SyntheticModel(self.good)
        model.device = torch.device('cpu')
        config = generation._config(self.runtime)
        model.generation_config = SimpleNamespace(eos_token_id=self.runtime.eos_ids, bos_token_id=config.bos_token_id)
        model.config = SimpleNamespace(max_position_embeddings=self.runtime.reference['context_tokens'])
        original_writer = e1.Writer
        def fixture_writer(path, runtime, *, synthetic_fixture):
            return original_writer(path, runtime, synthetic_fixture=True)
        run = self.base / 'complete'
        public, private = self.base / 'complete.review-public', self.base / 'complete.review-private'
        public.mkdir(mode=0o700)
        private.mkdir(mode=0o700)
        with patch.object(e1, 'E1_RUN', run), patch.object(e1, 'assert_collection_disabled'), \
             patch.object(e1.scope, 'Runtime', return_value=self.runtime), \
             patch.object(e1, 'Writer', side_effect=fixture_writer), \
             patch.object(production, '_verify_model_files'), patch.object(production, '_verify_device'), \
             patch.object(production, '_model_device', return_value=torch.device('cpu')), \
             patch.object(torch.cuda, 'synchronize'), patch.object(renderer, 'load_model', return_value=model):
            self.assertEqual(e1.collect(), {'state': 'validated_complete_unreviewed', 'records': 48})
        writer = original_writer(run, self.runtime, synthetic_fixture=True)
        with writer.locked():
            packet, coordinator = e1.export_review(writer, public, private)
        self.assertEqual(sum(item['technical_status'] == 'complete' for item in packet['items']), 48)
        self.assertEqual(len(coordinator['endpoint_template']['rows']), 48)
        self.assertTrue(json.loads((run / 'manifest.json').read_text())['synthetic_fixture'])

    def test_public_source_materials_reidentify_all_packet_items_by_content(self):
        with self.writer.locked():
            public, private = e1.export_review(self.writer, self.public, self.private)
        source = {scope.input_payload_sha(row): item_id for item_id, row in self.runtime.rows.items()}
        self.assertEqual(len(source), 48)
        for item in public['items']:
            payload = {'question': item['question'], 'documents': item['documents']}
            self.assertEqual(source[scope.input_payload_sha(payload)],
                             private['mapping_and_sources'][item['item_id']]['source_item_id'])

    def test_invalid_paths_and_condition_key_leaks_are_rejected(self):
        with self.writer.locked():
            with self.assertRaises(tx.JournalBlocked):
                e1.export_review(self.writer, self.public, self.public)
            public, private = e1.export_review(self.writer, self.public, self.private)
        legacy = sorted(self.runtime.plan['ordered_ids'], key=lambda x: scope.text_sha('scope-output-review-v1|' + x))
        actual = [private['mapping_and_sources'][f'R{i:03d}']['source_item_id'] for i in range(1, 49)]
        self.assertNotEqual(actual, legacy)
        self.assertTrue(all(set(item) == {'item_id', 'question', 'documents', 'technical_status'} for item in public['items']))


if __name__ == '__main__':
    unittest.main()
