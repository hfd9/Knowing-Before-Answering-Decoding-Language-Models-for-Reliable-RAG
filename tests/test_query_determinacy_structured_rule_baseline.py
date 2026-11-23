"""Category proof joins must preserve polarity, binding, and unknown cases."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_shared_structured as structured
from query_determinacy_structured_rule_baseline import category_lookup

PUBLIC = ROOT / 'docs/review/2026-11-18-two-case-cpu-v1/public.json'


class CategoryBaselineTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(PUBLIC.read_bytes())['cases'][1]
        self.spans, self.sources = structured.materials(self.case)
        self.query = self.case['questions'][1]['text']

    def lookup(self, spans, query=None, bound=('S1','S2')):
        return category_lookup(query or self.query, bound, self.sources, spans)

    def test_real_category_rows_and_exact_evidence(self):
        expected = (('N','N'), ('Y','N'), ('Y','Y'))
        for question, labels in zip(self.case['questions'], expected):
            r = self.lookup(self.spans, question['text'])
            self.assertEqual(r['status'], 'compared')
            self.assertEqual(tuple(w['answer'] for w in r['worlds']), labels)
            self.assertEqual([w['evidence_ids'] for w in r['worlds']], [['S1','R1'],['S2','R2']])

    def test_reversed_candidates_keep_their_own_rule(self):
        r = self.lookup(self.spans, bound=('S2','S1'))
        self.assertEqual([(w['value'], w['answer'], w['evidence_ids']) for w in r['worlds']],
                         [('LM7','N',['S2','R2']), ('VX3','Y',['S1','R1'])])

    def test_unknown_attribute_or_conflict_cannot_default_to_no(self):
        r = self.lookup(self.spans, '按规则表，该零件是否适合干燥？')
        self.assertIsNone(r['worlds'])
        for extra in ('，不适合干燥运输', '，适合干燥运输'):
            spans = copy.deepcopy(self.spans)
            spans['R1']['text'] += extra
            self.assertEqual(self.lookup(spans)['reason'], 'missing_or_ambiguous_attribute')

    def test_missing_or_duplicate_code_rule_is_unresolved(self):
        spans = copy.deepcopy(self.spans)
        spans['R1']['text'] = spans['R1']['text'].replace('VX3', 'VX30')
        self.assertEqual(self.lookup(spans)['reason'], 'missing_or_ambiguous_rule_row')
        spans['R1']['text'] = spans['R1']['text'].replace('VX30', 'LM7')
        self.assertEqual(self.lookup(spans, bound=('S2','S1'))['reason'], 'missing_or_ambiguous_rule_row')

    def test_bad_binding_or_unsupported_language_is_unresolved(self):
        for bound in (None, ('S1','S1'), ('S1','S3'), ('S1',)):
            self.assertEqual(self.lookup(self.spans, bound=bound)['reason'], 'source_binding_failed')
        self.assertEqual(self.lookup(self.spans, '该零件一般会不会适合干燥运输？')['reason'], 'unsupported_question')
        spans = copy.deepcopy(self.spans)
        spans['R1']['text'] = 'VX3通常适合干燥运输'
        self.assertEqual(self.lookup(spans)['reason'], 'unsupported_rule')


if __name__ == '__main__':
    unittest.main()
