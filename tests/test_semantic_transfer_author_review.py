"""Integrity/denominator checks for manual exposed review, not tests of semantic truth."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import semantic_transfer_author_review as audit


class AuthorReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = audit.read(audit.MATERIALS / 'materials/inputs.json')
        cls.value = audit.read(audit.RATINGS)
        cls.seal = audit.read(audit.DEV_SEAL)

    def test_all240_and_dev48_seal_exact_citations_and_backgrounds(self):
        by_id, documents, backgrounds = audit.validate(self.rows, self.value, self.seal)
        self.assertEqual((len(by_id), len(documents), len(backgrounds)), (240, 435, 90))
        self.assertEqual(sum(len(v['occurrences']) for v in documents.values()), 1200)
        self.assertEqual(len({b['document_sha256'] for b in backgrounds}), 83)

    def test_false_quote_missing_judgment_or_altered_dev_judgment_rejected(self):
        for mutate in [lambda v: v['ratings'].pop(),
                lambda v: v['ratings'][0]['citations'][0].update(quote='not in the supplied passage'),
                lambda v: v['ratings'][0]['citations'][0].update(start=-1),
                lambda v: v['ratings'][96].update(rationale='changed after development seal')]:
            value = copy.deepcopy(self.value)
            mutate(value)
            with self.assertRaises(ValueError):
                audit.validate(self.rows, value, self.seal)

    def test_exposure_cannot_be_upgraded_or_imported_as_independent(self):
        for field, wrong in [('history_exposed', False), ('independent_gold', True),
                ('approved_for_training', True), ('gpu_launch_ready', True)]:
            value = copy.deepcopy(self.value)
            value[field] = wrong
            with self.assertRaisesRegex(ValueError, 'never become independent'):
                audit.validate(self.rows, value, self.seal)
        with self.assertRaisesRegex(ValueError, 'History-exposed'):
            audit.intake.validate_review(self.value, {}, '')

    def test_semantic_state_and_minimal_edit_audits_remain_separate(self):
        authors = audit.read(audit.MATERIALS / 'coordinator/author_judgments.json')
        preflight = audit.read(audit.MATERIALS / 'preflight.json')
        summary, pairs = audit.derive(self.rows, self.value, authors, preflight)
        self.assertEqual(summary['counts'], {'answer': 120, 'refuse': 60, 'conflict': 58, 'unknown': 2})
        self.assertEqual(summary['unknown_ids'], ['stv17_A_C', 'stv17_B_C'])
        self.assertEqual(len(pairs), 300)
        self.assertEqual(summary['S_to_I_pairs']['reviewed_answer_to_refuse'], 60)
        self.assertEqual(summary['S_to_I_pairs']['structural_counts'],
            {'other_facts_changed': 52, 'deletion_only_at_required_relation': 6, 'modality_recast': 2})
        self.assertEqual(summary['S_to_C_pairs']['unknown_pairs'], 2)
        self.assertEqual(summary['S_to_K_pairs']['reviewed_answer_to_answer'], 60)
        self.assertEqual(summary['approved_semantic_labels'], 0)
        self.assertFalse(summary['gpu_launch_ready'])
        self.assertTrue(all(p['probe_prediction'] is None and p['probability_delta'] is None for p in pairs))

    def test_actual_cpu_export_and_readonly_replay_leave_sources_and_gate_unchanged(self):
        preserved = [audit.RATINGS, audit.DEV_SEAL, audit.MATERIALS / 'materials/inputs.json',
            ROOT / 'runs/qwen2.5-3b-semantic-transfer-study-preparation-v1/review_gate.json',
            ROOT / 'runs/qwen2.5-3b-semantic-transfer-study-preparation-v1/approved_labels.json']
        before = {str(p): audit.digest(p) for p in preserved}
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            audit.process(run=output, write=True)
            hashes = {p.name: audit.digest(p) for p in output.iterdir()}
            audit.process(run=output, write=False)
            self.assertEqual(hashes, {p.name: audit.digest(p) for p in output.iterdir()})
            (output / 'summary.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Frozen review artifact differs'):
                audit.process(run=output, write=False)
        self.assertEqual(before, {str(p): audit.digest(p) for p in preserved})


if __name__ == '__main__':
    unittest.main()
