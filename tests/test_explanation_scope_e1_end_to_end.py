"""CPU-only E1 full pipeline using mock generation and synthetic reviewer declarations."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import evidence_experiment as renderer
import explanation_scope_e1 as e1
import explanation_scope_e1_intake as intake
import explanation_scope_generation_fixture as generation
import explanation_scope_metrics as metrics
import explanation_scope_production as production
import explanation_scope_runtime as scope
import explanation_scope_transaction_prototype as transaction


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = scope.Runtime()
        cls.tokens = cls.runtime.tokenizer.encode('synthetic answer', add_special_tokens=False) + [cls.runtime.eos_ids[0]]

    def run_case(self, fail_fifth):
        with tempfile.TemporaryDirectory(prefix='e1-pipeline-') as directory:
            root = Path(directory)
            run = root / 'run'
            public = root / 'run.review-public'
            private = root / 'run.review-private'
            sealed = root / 'sealed'
            result = root / 'result'
            for path in (public, private, sealed, result):
                path.mkdir(mode=0o700)
            model = generation.SyntheticModel(self.tokens)
            model.device = torch.device('cpu')
            config = generation._config(self.runtime)
            model.generation_config = SimpleNamespace(eos_token_id=self.runtime.eos_ids, bos_token_id=config.bos_token_id)
            model.config = SimpleNamespace(max_position_embeddings=self.runtime.reference['context_tokens'])
            original_writer, original_generate = e1.Writer, model.generate
            calls = []
            def fixture_writer(path, runtime, *, synthetic_fixture):
                return original_writer(path, runtime, synthetic_fixture=True)
            def generate(**kwargs):
                calls.append(1)
                model.token_ids = [self.runtime.eos_ids[0]] if fail_fifth and len(calls) == 5 else self.tokens
                return original_generate(**kwargs)
            with patch.object(e1, 'E1_RUN', run), patch.object(e1, 'assert_collection_disabled'), \
                 patch.object(e1.scope, 'Runtime', return_value=self.runtime), \
                 patch.object(e1, 'Writer', side_effect=fixture_writer), \
                 patch.object(production, '_verify_model_files'), patch.object(production, '_verify_device'), \
                 patch.object(production, '_model_device', return_value=torch.device('cpu')), \
                 patch.object(torch.cuda, 'synchronize'), patch.object(renderer, 'load_model', return_value=model), \
                 patch.object(model, 'generate', side_effect=generate):
                if fail_fifth:
                    with self.assertRaises(transaction.JournalBlocked):
                        e1.collect()
                else:
                    self.assertEqual(e1.collect(), {'state': 'validated_complete_unreviewed', 'records': 48})
            self.assertEqual(len(calls), 5 if fail_fifth else 48)
            writer = original_writer(run, self.runtime, synthetic_fixture=True)
            with writer.locked():
                packet, coordinator = e1.export_review(writer, public, private)
            packet_path = next(public.glob('packet-*.json'))
            coordinator_path = next(private.glob('coordinator-*.json'))
            export_seal_path = next(private.glob('seal-*.json'))
            review = {'reviewer_id': 'synthetic-reviewer', 'history_exposure': 'declared_exposed',
                      'exposure_description': 'Synthetic fixture with no actual reviewer.', 'items': []}
            for item in packet['items']:
                reviewed = item['technical_status'] == 'complete'
                claims = []
                if reviewed:
                    answer = item['answer']
                    claims = [{'claim_id': 'C1', 'claim': 'Synthetic placeholder, no semantic claim.',
                        'role': 'other', 'judgment': 'not_applicable', 'reason': 'Synthetic test only.',
                        'output_citation': {'start': 0, 'end': len(answer), 'quote': answer},
                        'document_support': [], 'counterevidence': []}]
                review['items'].append({'item_id': item['item_id'],
                    'review_status': 'reviewed' if reviewed else 'unreviewed',
                    'full_answer_reviewed': reviewed, 'claims': claims})
            review_path = root / 'review-input.json'
            review_path.write_text(json.dumps(review, ensure_ascii=False), encoding='utf-8')
            sealed_receipt = intake.seal_review(packet_path, review_path, sealed)
            # The test accesses the mapping only after sealing; these are fabricated declarations.
            conversion = {'converter_id': 'synthetic-converter', 'history_exposure': 'declared_exposed',
                          'exposure_description': 'Synthetic fixture, mapping visible to test.',
                          'sealed_review_sha256': sealed_receipt['review_bytes_sha256'], 'items': []}
            for item in packet['items']:
                if item['technical_status'] != 'complete':
                    continue
                source_id = coordinator['mapping_and_sources'][item['item_id']]['source_item_id']
                condition = source_id.rsplit('_', 1)[1]
                fields = {key: None for key in metrics.FIELDS}
                fields.update({'gives_unretracted_target_value': 'no', 'provides_substantive_explanation': 'no',
                               'whole_explanation_support': 'not_applicable', 'overbroad_missing_information_claim': 'no'})
                if condition == 'S':
                    fields['grounded_target_answer'] = 'no'
                elif condition in ('I0', 'IU'):
                    fields.update({'withholds_target_with_support': 'yes', 'unsupported_target_conflict': 'no'})
                else:
                    fields.update({'recognizes_target_conflict': 'no', 'unresolved_target_side_selection': 'no'})
                conversion['items'].append({'item_id': item['item_id'], 'claim_ids': ['C1'],
                                            'rationale': 'Synthetic values, not semantic scoring.', 'fields': fields})
            conversion_path = root / 'conversion-input.json'
            conversion_path.write_text(json.dumps(conversion, ensure_ascii=False), encoding='utf-8')
            receipt, summary = intake.connect(packet_path, sealed, coordinator_path, export_seal_path,
                                               conversion_path, result)
            replay = intake.verify_result(packet_path, sealed, coordinator_path, export_seal_path, result)
            self.assertEqual(replay['planned_slots'], 48)
            self.assertEqual(replay['planned_pairs'], 12)
            self.assertFalse(replay['semantic_truth_verified'])
            self.assertFalse(receipt['formal_gate'])
            self.assertTrue(coordinator['synthetic_fixture'])
            if fail_fifth:
                self.assertEqual(sealed_receipt['reviewed_items'], 4)
                self.assertEqual(summary['primary']['fully_reviewed_pairs'], 1)
                self.assertIsNone(summary['primary']['point'])
                self.assertAlmostEqual(summary['primary']['identification_lower'], -11 / 12)
                self.assertAlmostEqual(summary['primary']['identification_upper'], 11 / 12)
                self.assertEqual(sum(x['technical_status'] == 'empty' for x in packet['items']), 1)
                self.assertEqual(sum(x['technical_status'] == 'not_collected' for x in packet['items']), 43)
            else:
                self.assertEqual(sealed_receipt['reviewed_items'], 48)
                self.assertEqual(summary['primary']['fully_reviewed_pairs'], 12)
                self.assertEqual(summary['primary']['point'], 0)
                self.assertEqual(summary['primary']['identification_lower'], 0)
                self.assertEqual(summary['primary']['identification_upper'], 0)

    def test_full_48_mocked_generation_to_sealed_review_and_replay(self):
        self.run_case(fail_fifth=False)

    def test_fifth_empty_stops_and_partial_review_retains_full_12_pairs(self):
        self.run_case(fail_fifth=True)


if __name__ == '__main__':
    unittest.main()
