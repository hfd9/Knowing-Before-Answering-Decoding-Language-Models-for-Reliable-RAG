import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import query_determinacy_shared_extract_prototype as prototype


class SharedExtractPrototypeTests(unittest.TestCase):
    def setUp(self):
        self.background = {'id': 'synthetic', 'evidence': 'synthetic evidence', 'domain': 'integer'}
        self.questions = [{'id': str(i), 'text': 'synthetic question ' + str(i)} for i in range(3)]

    def test_one_extraction_shared_by_both_arms_and_no_gold(self):
        seen = []
        def invoke(req):
            seen.append(req)
            return {'status': 'complete', 'output': '[13,21]' if req['kind'] == 'extract' else '是'}
        result = prototype.simulate(self.background, self.questions, invoke)
        self.assertEqual(len(seen), 13)
        self.assertEqual(sum(r['kind'] == 'extract' for r in seen), 1)
        self.assertEqual(sum(r['kind'] == 'direct' for r in seen), 3)
        self.assertEqual(sum(r['kind'] == 'joint' and r['values'] == ('13', '21') for r in seen), 3)
        self.assertEqual(sum(r['kind'] == 'branch' and r['values'] == ('13',) for r in seen), 3)
        self.assertEqual(sum(r['kind'] == 'branch' and r['values'] == ('21',) for r in seen), 3)
        self.assertEqual(len(result['downstream']), 3)
        self.assertTrue(all(set(r) == {'kind', 'background_id', 'evidence', 'question_id', 'question', 'values'} for r in seen))

    def test_failed_extraction_does_not_call_joint_or_branch(self):
        for status, output, expected in [('complete', '[true,2]', 'invalid'),
                                          ('technical_failure', '', 'technical_failure')]:
            with self.subTest(status=status):
                def invoke(req):
                    return {'status': status, 'output': output} if req['kind'] == 'extract' else {'status': 'complete', 'output': '是'}
                result = prototype.simulate(self.background, self.questions, invoke)
                self.assertEqual(len(result['calls']), 4)
                self.assertTrue(all(x['status'] == expected and x['joint'] is None and x['branches'] is None
                                    for x in result['downstream'].values()))

    def test_branch_failure_preserved_and_other_branch_still_attempted(self):
        def invoke(req):
            if req['kind'] == 'extract':
                return {'status': 'complete', 'output': '[1,2]'}
            if req['kind'] == 'branch' and req['values'] == ('1',):
                return {'status': 'technical_failure', 'output': ''}
            return {'status': 'complete', 'output': '是'}
        result = prototype.simulate(self.background, self.questions, invoke)
        self.assertEqual(len(result['calls']), 13)
        for row in result['downstream'].values():
            self.assertEqual([x['status'] for x in row['branches']], ['technical_failure', 'complete'])

    def test_labels_or_bad_envelopes_rejected(self):
        call = lambda req: {'status': 'complete', 'output': '是'}
        with self.assertRaises(ValueError):
            prototype.simulate(dict(self.background, reference=['13', '21']), self.questions, call)
        with self.assertRaises(ValueError):
            prototype.simulate(self.background, [dict(self.questions[0], expected='Y')] + self.questions[1:], call)
        with self.assertRaises(ValueError):
            prototype.simulate(self.background, self.questions, lambda req: {'output': '是'})


if __name__ == '__main__':
    unittest.main()
