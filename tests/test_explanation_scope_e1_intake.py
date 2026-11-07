"""Synthetic E1 review intake tests; no model inference, external reviewers or real scores."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import explanation_scope_e1 as e1
import explanation_scope_e1_intake as intake
import explanation_scope_metrics as metrics
import explanation_scope_runtime as scope


class IntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_tmp = tempfile.TemporaryDirectory(prefix='e1-intake-source-')
        base = Path(cls.original_tmp.name)
        run = base / 'run'
        run.mkdir(mode=0o700)
        public = base / 'run.review-public'
        private = base / 'run.review-private'
        public.mkdir(mode=0o700)
        private.mkdir(mode=0o700)
        runtime = scope.Runtime()
        tokens = runtime.tokenizer.encode('synthetic answer', add_special_tokens=False) + [runtime.eos_ids[0]]
        writer = e1.Writer(run, runtime, synthetic_fixture=True)
        with writer.locked():
            writer.initialize()
            for _ in range(2):
                writer.begin()
                writer.commit_tokens(tokens, 0.1, '2026-11-07T12:00:00+00:00')
            writer.begin()
            writer.commit_tokens([runtime.eos_ids[0]], 0.1, '2026-11-07T12:00:00+00:00')
            cls.packet, cls.coordinator = e1.export_review(writer, public, private)
        cls.packet_path = next(public.glob('packet-*.json'))
        cls.coordinator_path = next(private.glob('coordinator-*.json'))
        cls.export_seal_path = next(private.glob('seal-*.json'))
        cls.i0 = next(i for i, s in cls.coordinator['mapping_and_sources'].items() if s['source_item_id'] == 'exs01_I0')
        cls.s = next(i for i, s in cls.coordinator['mapping_and_sources'].items() if s['source_item_id'] == 'exs01_S')
        cls.empty = next(i for i, s in cls.coordinator['mapping_and_sources'].items() if s['technical_status'] == 'empty')

    @classmethod
    def tearDownClass(cls):
        cls.original_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='e1-intake-test-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.sealed = self.mkdir('sealed')
        self.result = self.mkdir('result')
        self.review_path = self.base / 'review-input.json'
        self.conversion_path = self.base / 'conversion-input.json'

    def mkdir(self, name):
        path = self.base / name
        path.mkdir(mode=0o700)
        return path

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def review(self, chosen=None):
        chosen = self.i0 if chosen is None else chosen
        items = []
        for item in self.packet['items']:
            row = {'item_id': item['item_id'], 'review_status': 'unreviewed',
                   'full_answer_reviewed': False, 'claims': []}
            if item['item_id'] == chosen:
                answer = item.get('answer', 'synthetic answer')
                doc = item['documents'][0]
                quote = doc.split()[0]
                start = doc.index(quote)
                row.update({'review_status': 'reviewed', 'full_answer_reviewed': True, 'claims': [{
                    'claim_id': 'C1', 'claim': 'synthetic claim', 'role': 'explanation',
                    'judgment': 'supported', 'reason': 'Synthetic declaration for pipeline test.',
                    'output_citation': {'start': 0, 'end': len(answer), 'quote': answer},
                    'document_support': [{'document_index': 1, 'start': start, 'end': start + len(quote), 'quote': quote}],
                    'counterevidence': []}]})
            items.append(row)
        return {'reviewer_id': 'synthetic-reviewer', 'history_exposure': 'unknown',
                'exposure_description': 'Synthetic fixture; no real reviewer.', 'items': items}

    def conversion(self, receipt, chosen=None):
        chosen = self.i0 if chosen is None else chosen
        fields = {key: None for key in metrics.FIELDS}
        fields.update({'gives_unretracted_target_value': 'no', 'provides_substantive_explanation': 'yes',
                       'whole_explanation_support': 'supported', 'overbroad_missing_information_claim': 'no',
                       'withholds_target_with_support': 'yes', 'unsupported_target_conflict': 'no'})
        return {'converter_id': 'synthetic-converter', 'history_exposure': 'declared_exposed',
                'exposure_description': 'Synthetic fixture; condition mapping seen.',
                'sealed_review_sha256': receipt['review_bytes_sha256'],
                'items': [{'item_id': chosen, 'claim_ids': ['C1'], 'rationale': 'Synthetic declaration only.',
                           'fields': fields}]}

    def seal(self, review=None):
        self.write(self.review_path, self.review() if review is None else review)
        return intake.seal_review(self.packet_path, self.review_path, self.sealed)

    def connect(self, receipt, conversion=None):
        self.write(self.conversion_path, self.conversion(receipt) if conversion is None else conversion)
        return intake.connect(self.packet_path, self.sealed, self.coordinator_path,
                              self.export_seal_path, self.conversion_path, self.result)

    def test_end_to_end_partial_review_and_manual_conversion_preserve_full_denominator(self):
        receipt = self.seal()
        result, summary = self.connect(receipt)
        self.assertEqual(receipt['reviewed_items'], 1)
        self.assertEqual(result['converted_items'], 1)
        self.assertEqual(result['reviewer_id'], 'synthetic-reviewer')
        self.assertEqual(result['converter_id'], 'synthetic-converter')
        self.assertFalse(result['independent_approval'])
        self.assertFalse(result['semantic_truth_verified'])
        self.assertFalse(result['raw_cache_bytes_verified_by_intake'])
        self.assertFalse(result['formal_gate'])
        self.assertEqual(summary['planned_slots'], 48)
        self.assertEqual(summary['reviewed_slots'], 1)
        self.assertEqual(summary['primary']['planned_pairs'], 12)
        self.assertEqual(summary['primary']['reviewed_endpoints'], 1)
        self.assertIsNone(summary['primary']['point'])
        self.assertAlmostEqual(summary['primary']['identification_lower'], -11 / 12)
        self.assertEqual(summary['primary']['identification_upper'], 1.0)
        rows = json.loads((self.result / 'endpoints.json').read_text())['rows']
        empty = next(r for r in rows if r['source_item_id'] == self.empty)
        self.assertEqual(empty['technical_status'], 'empty')
        self.assertEqual(empty['review_status'], 'unreviewed')
        self.assertTrue(all(empty[field] is None for field in metrics.FIELDS))
        self.assertEqual((self.sealed / 'review.json').read_bytes(), self.review_path.read_bytes())
        self.assertEqual((self.result / 'conversion.json').read_bytes(), self.conversion_path.read_bytes())
        checked = intake.verify_result(self.packet_path, self.sealed, self.coordinator_path,
                                       self.export_seal_path, self.result)
        self.assertEqual((checked['planned_slots'], checked['planned_pairs']), (48, 12))
        self.assertFalse(checked['semantic_truth_verified'])
        altered = json.loads((self.result / 'summary.json').read_text())
        altered['primary']['identification_lower'] = 0.0
        self.write(self.result / 'summary.json', altered)
        with self.assertRaises(ValueError):
            intake.verify_result(self.packet_path, self.sealed, self.coordinator_path,
                                 self.export_seal_path, self.result)

    def test_empty_conversion_keeps_null_estimate_and_bounds(self):
        receipt = self.seal()
        conversion = self.conversion(receipt)
        conversion['items'] = []
        _, summary = self.connect(receipt, conversion)
        self.assertEqual(summary['reviewed_slots'], 0)
        self.assertIsNone(summary['primary']['point'])
        self.assertIsNone(summary['primary']['identification_lower'])
        self.assertIsNone(summary['primary']['identification_upper'])

    def test_seal_and_connect_cli_work_in_separate_processes(self):
        self.write(self.review_path, self.review())
        script = str(ROOT / 'scripts/explanation_scope_e1_intake.py')
        first = subprocess.run([sys.executable, '-B', script, 'seal', '--packet', str(self.packet_path),
                                '--review', str(self.review_path), '--output-dir', str(self.sealed)],
                               capture_output=True, text=True, timeout=90)
        self.assertEqual(first.returncode, 0, first.stderr)
        receipt = json.loads(first.stdout)
        self.write(self.conversion_path, self.conversion(receipt))
        second = subprocess.run([sys.executable, '-B', script, 'connect', '--packet', str(self.packet_path),
                                 '--sealed-dir', str(self.sealed), '--coordinator', str(self.coordinator_path),
                                 '--export-seal', str(self.export_seal_path), '--conversion', str(self.conversion_path),
                                 '--output-dir', str(self.result)], capture_output=True, text=True, timeout=90)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)['converted_items'], 1)
        self.assertEqual(json.loads((self.result / 'summary.json').read_text())['primary']['planned_pairs'], 12)
        third = subprocess.run([sys.executable, '-B', script, 'verify', '--packet', str(self.packet_path),
                                '--sealed-dir', str(self.sealed), '--coordinator', str(self.coordinator_path),
                                '--export-seal', str(self.export_seal_path), '--result-dir', str(self.result)],
                               capture_output=True, text=True, timeout=90)
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertEqual(json.loads(third.stdout)['reviewed_slots'], 1)

    def test_seal_reads_no_condition_mapping(self):
        self.write(self.review_path, self.review())
        seen = []
        original = intake.read_json
        def observed(path):
            seen.append(Path(path))
            return original(path)
        with patch.object(intake, 'read_json', side_effect=observed):
            intake.seal_review(self.packet_path, self.review_path, self.sealed)
        self.assertEqual(seen, [self.packet_path, self.review_path])

    def test_bad_citation_missing_support_and_empty_output_are_rejected_before_write(self):
        variants = []
        bad_quote = self.review()
        row = next(r for r in bad_quote['items'] if r['item_id'] == self.i0)
        row['claims'][0]['output_citation']['quote'] = 'forged'
        variants.append(bad_quote)
        bad_doc = self.review()
        next(r for r in bad_doc['items'] if r['item_id'] == self.i0)['claims'][0]['document_support'][0]['document_index'] = 6
        variants.append(bad_doc)
        no_support = self.review()
        next(r for r in no_support['items'] if r['item_id'] == self.i0)['claims'][0]['document_support'] = []
        variants.append(no_support)
        variants.append(self.review(self.empty))
        for i, value in enumerate(variants):
            with self.subTest(variant=i):
                output = self.mkdir('invalid-' + str(i))
                self.write(self.review_path, value)
                with self.assertRaises(ValueError):
                    intake.seal_review(self.packet_path, self.review_path, output)
                self.assertEqual(list(output.iterdir()), [])

    def test_duplicate_ids_duplicate_json_keys_and_hidden_fields_are_rejected(self):
        review = self.review()
        review['items'][0]['item_id'] = review['items'][1]['item_id']
        self.write(self.review_path, review)
        with self.assertRaises(ValueError):
            intake.seal_review(self.packet_path, self.review_path, self.sealed)
        review = self.review()
        review['condition'] = 'IU'
        self.write(self.review_path, review)
        with self.assertRaises(ValueError):
            intake.seal_review(self.packet_path, self.review_path, self.sealed)
        self.review_path.write_text('{"reviewer_id":"x","reviewer_id":"y"}')
        with self.assertRaises(ValueError):
            intake.seal_review(self.packet_path, self.review_path, self.sealed)
        self.assertEqual(list(self.sealed.iterdir()), [])

    def test_unsealed_or_tampered_review_fails_before_mapping_read(self):
        receipt = self.seal()
        self.write(self.conversion_path, self.conversion(receipt))
        (self.sealed / 'review.json').write_text('{}')
        seen = []
        original = intake.read_json
        def observed(path):
            seen.append(Path(path))
            return original(path)
        with patch.object(intake, 'read_json', side_effect=observed):
            with self.assertRaises(ValueError):
                intake.connect(self.packet_path, self.sealed, self.coordinator_path,
                               self.export_seal_path, self.conversion_path, self.result)
        self.assertNotIn(self.coordinator_path, seen)
        self.assertEqual(list(self.result.iterdir()), [])

    def test_wrong_packet_coordinator_seal_or_conversion_claim_is_rejected(self):
        receipt = self.seal()
        changed_packet = deepcopy(self.packet)
        changed_packet['items'][0]['question'] += ' changed'
        packet_path = self.base / 'wrong-packet.json'
        self.write(packet_path, changed_packet)
        self.write(self.conversion_path, self.conversion(receipt))
        with self.assertRaises(ValueError):
            intake.connect(packet_path, self.sealed, self.coordinator_path,
                           self.export_seal_path, self.conversion_path, self.result)
        wrong_seal = self.base / 'wrong-seal.json'
        self.write(wrong_seal, {'packet_sha256': '0' * 64, 'coordinator_sha256': '0' * 64})
        with self.assertRaises(ValueError):
            intake.connect(self.packet_path, self.sealed, self.coordinator_path,
                           wrong_seal, self.conversion_path, self.result)
        conversion = self.conversion(receipt)
        conversion['items'][0]['claim_ids'] = ['C-NOT-SEALED']
        self.write(self.conversion_path, conversion)
        with self.assertRaises(ValueError):
            intake.connect(self.packet_path, self.sealed, self.coordinator_path,
                           self.export_seal_path, self.conversion_path, self.result)
        self.assertEqual(list(self.result.iterdir()), [])

    def test_packet_mapping_and_input_output_hash_must_agree(self):
        receipt = self.seal()
        coordinator = deepcopy(self.coordinator)
        coordinator['mapping_and_sources'][self.i0]['input_sha256'] = '0' * 64
        source = self.base / 'bad-coordinator.json'
        seal = self.base / 'matching-bad-export-seal.json'
        self.write(source, coordinator)
        self.write(seal, {'packet_sha256': scope.json_sha(self.packet),
                          'coordinator_sha256': scope.json_sha(coordinator)})
        self.write(self.conversion_path, self.conversion(receipt))
        with self.assertRaises(ValueError):
            intake.connect(self.packet_path, self.sealed, source, seal, self.conversion_path, self.result)

    def test_no_overwrite_or_repair_of_partial_seal(self):
        receipt = self.seal()
        with self.assertRaises(ValueError):
            intake.seal_review(self.packet_path, self.review_path, self.sealed)
        (self.sealed / 'receipt.json').unlink()
        self.write(self.conversion_path, self.conversion(receipt))
        with self.assertRaises(ValueError):
            intake.connect(self.packet_path, self.sealed, self.coordinator_path,
                           self.export_seal_path, self.conversion_path, self.result)

    def test_technical_failure_and_unreviewed_claims_never_become_scored(self):
        review = self.review(self.empty)
        self.write(self.review_path, review)
        with self.assertRaises(ValueError):
            intake.seal_review(self.packet_path, self.review_path, self.sealed)
        review = self.review()
        target = next(row for row in review['items'] if row['item_id'] == self.i0)
        target['review_status'] = 'unreviewed'
        self.write(self.review_path, review)
        with self.assertRaises(ValueError):
            intake.seal_review(self.packet_path, self.review_path, self.sealed)


if __name__ == '__main__':
    unittest.main()
