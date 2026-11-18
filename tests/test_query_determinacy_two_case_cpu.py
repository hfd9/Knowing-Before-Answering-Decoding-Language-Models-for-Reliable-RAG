import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import query_determinacy_two_case_cpu as collection
import query_determinacy_two_case_score as score

REFERENCE_SHA = '99c65a841a686835d73f7325e7a77f9495aeba8dcc87ebc2d0496e5d251ab75d'


class TwoCaseTests(unittest.TestCase):
    def scored(self, mode):
        data = collection.simulate(mode)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'results.json'
            raw = json.dumps(data, ensure_ascii=False).encode()
            path.write_bytes(raw)
            result = score.score(path, hashlib.sha256(raw).hexdigest(), REFERENCE_SHA)
        return data, result

    def test_normal_shared_extraction_and_separate_scoring(self):
        data, result = self.scored('normal')
        self.assertEqual((data['model_calls'], data['simulated_calls']), (0, 26))
        self.assertEqual(len(result['rows']), 6)
        for row in result['rows']:
            for method in ('direct', 'joint', 'branch'):
                self.assertTrue(row[method]['correct_and_supported'], (row['case'], row['question'], method))

    def test_extract_failure_does_not_prevent_direct_scoring(self):
        data, result = self.scored('extract_failure')
        self.assertEqual(data['simulated_calls'], 17)
        for row in result['rows']:
            self.assertTrue(row['direct']['correct_and_supported'])
            if row['case'] == 'D7M4':
                self.assertEqual(row['joint']['status'], 'unresolved')
                self.assertEqual(row['branch']['status'], 'unresolved')

    def test_correct_final_does_not_hide_two_wrong_worlds_or_bad_quote(self):
        _, result = self.scored('adversarial')
        row = next(x for x in result['rows'] if x['case'] == 'D7M4' and x['question'] == 'p4')
        for method in ('direct', 'joint', 'branch'):
            self.assertTrue(row[method]['final_correct'])
            self.assertFalse(row[method]['all_worlds_correct'])
            self.assertTrue(all(not x['answer_correct'] for x in row[method]['worlds']))
            self.assertFalse(row[method]['correct_and_supported'])
        row = next(x for x in result['rows'] if x['case'] == 'N3K6' and x['question'] == 'u5')
        for method in ('direct', 'joint', 'branch'):
            self.assertTrue(row[method]['final_correct'])
            self.assertTrue(row[method]['all_worlds_correct'])
            self.assertFalse(row[method]['all_evidence_ok'])
            self.assertFalse(row[method]['correct_and_supported'])

    def test_reject_unsealed_output_before_reference_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad.json'
            path.write_text('{}')
            with patch.object(score, 'BASE', Path(tmp) / 'no-reference-directory'):
                with self.assertRaisesRegex(ValueError, 'hash'):
                    score.score(path, '0' * 64, REFERENCE_SHA)

    def test_reference_mutation_is_rejected(self):
        data = collection.simulate('normal')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'results.json'
            raw = json.dumps(data, ensure_ascii=False).encode()
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, 'reference hash'):
                score.score(path, hashlib.sha256(raw).hexdigest(), '0' * 64)


if __name__ == '__main__':
    unittest.main()
