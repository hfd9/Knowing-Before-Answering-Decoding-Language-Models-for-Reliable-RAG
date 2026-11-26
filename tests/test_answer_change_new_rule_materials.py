import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'docs/review/2026-11-26-new-rule-materials-v1'
spec = importlib.util.spec_from_file_location('new_materials', PACK / 'build.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MaterialTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((PACK / 'rules.json').read_text())

    def test_12_cases_and_authored_references(self):
        public, refs = m.build(self.data)
        self.assertEqual(len(public['cases']), 12)
        self.assertEqual(set(refs['cases']), {c['id'] for c in public['cases']})
        for r in self.data['rules']:
            for label in ('same', 'different'):
                row = refs['cases'][f'{r["id"]}/{label}/missing']
                self.assertFalse(row['independently_reviewed'])
                self.assertEqual(len(set(row['branches'].values())), 1 if label == 'same' else 2)

    def test_explicit_threshold_boundaries(self):
        self.assertFalse(m.decision('>=', 999999, 1000000))
        self.assertTrue(m.decision('>=', 1000000, 1000000))
        self.assertTrue(m.decision('>=', 1000001, 1000000))
        self.assertFalse(m.decision('>', 11599, 11600))
        self.assertFalse(m.decision('>', 11600, 11600))
        self.assertTrue(m.decision('>', 11601, 11600))
        self.assertFalse(m.decision('>=', 1099999, 1100000))
        self.assertTrue(m.decision('>=', 1100000, 1100000))
        self.assertTrue(m.decision('>=', 1100001, 1100000))
        self.assertFalse(m.decision('>', 11949, 11950))
        self.assertFalse(m.decision('>', 11950, 11950))
        self.assertTrue(m.decision('>', 11951, 11950))

    def test_hand_expected_version_pairs(self):
        _, refs = m.build(self.data)
        cases = refs['cases']
        self.assertEqual(list(cases['adviser_aum/same/missing']['branches'].values()), [True, True])
        self.assertEqual(list(cases['adviser_aum/different/missing']['branches'].values()), [True, False])
        self.assertEqual(list(cases['eitc_investment/same/missing']['branches'].values()), [False, False])
        self.assertEqual(list(cases['eitc_investment/different/missing']['branches'].values()), [True, False])

    def test_wrong_category_or_operator_does_not_silently_pass(self):
        self.data['rules'][0]['different_amount'] = self.data['rules'][0]['same_amount']
        with self.assertRaisesRegex(ValueError, 'pair category'):
            m.build(self.data)
        with self.assertRaises(ValueError):
            m.decision('!=', 1, 2)


if __name__ == '__main__':
    unittest.main()
