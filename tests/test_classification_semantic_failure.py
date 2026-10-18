"""Post-analysis denominator, alignment and preservation checks, without a model."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import analyze_classification_semantic_failure as a


class SemanticFailureAnalysisTests(unittest.TestCase):
    def test_invalid_stays_in_denominator_and_macro_f1(self):
        rows = [dict(id=str(i), true_mode=mode) for i, mode in enumerate(a.MODES)]
        result = a.counts(rows, {'0': 'answer', '1': None, '2': 'answer'})
        self.assertEqual(result['confusion_matrix'], [[1, 0, 0, 0], [0, 0, 0, 1], [1, 0, 0, 0]])
        self.assertEqual(result['accuracy'], 1/3)
        self.assertEqual(result['classification_false_answer_rate'], 1/2)
        self.assertEqual(result['per_class']['refuse']['support'], 1)
        self.assertAlmostEqual(result['macro_f1'], 2/9)

    def test_unknown_and_misaligned_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            a.counts([dict(id='x', true_mode='unknown')], {'x': 'refuse'})
        with self.assertRaises(ValueError):
            a.counts([dict(id='x', true_mode='answer')], {'other': 'answer'})
        with self.assertRaises(ValueError):
            a.index([dict(id='x'), dict(id='x')])

    def test_paired_change_direction_and_wrong_to_wrong(self):
        rows = [dict(id=str(i), true_mode=mode) for i, mode in enumerate(a.MODES)]
        result = a.compare(rows, {'0': 'answer', '1': 'answer', '2': 'refuse'},
                           {'0': 'refuse', '1': 'refuse', '2': 'answer'})
        self.assertEqual(result['group_counts'], dict(improved=1, regressed=1, both_correct=0, both_wrong=1))
        self.assertEqual(result['net_correct'], 0)
        self.assertEqual(result['transitions_by_published_class']['conflict'][0][1], 1)

    def test_existing_artifacts_only_allow_identical_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'result.txt'
            a.write_new(path, 'frozen\r\n')
            a.write_new(path, 'frozen\r\n')
            with self.assertRaises(ValueError):
                a.write_new(path, 'changed\n')
            self.assertEqual(path.read_bytes(), b'frozen\r\n')


if __name__ == '__main__':
    unittest.main()
