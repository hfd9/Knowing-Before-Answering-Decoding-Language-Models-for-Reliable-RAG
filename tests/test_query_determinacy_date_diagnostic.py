"""Cover boundaries that can turn incomplete evidence into a unique answer."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import query_determinacy_date_diagnostic as diagnostic


class DateDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = {row['id']: row['input'] for row in diagnostic.pilot.read(diagnostic.pilot.MATERIAL / 'inputs.json')}

    def test_strict_exceeds_excludes_equality(self):
        result = diagnostic.solve_public(self.inputs['R01'].replace('$75,000', '$69,500'))
        self.assertEqual((result['action'], result['answer']), ('answer', False))
        self.assertEqual(result['evidence'], ['E1', 'E2'])

    def test_gap_or_overlap_blocks_a_unique_answer(self):
        text = self.inputs['R03']
        new_rule = next(line for line in text.splitlines() if line.startswith('[E3]'))
        mutations = {'coverage_gap': text.replace(new_rule + '\n', ''),
                     'overlapping_versions': text.replace(new_rule, new_rule + '\n' + new_rule.replace('[E3]', '[E4]'))}
        for reason, mutated in mutations.items():
            with self.subTest(reason=reason):
                result = diagnostic.solve_public(mutated)
                self.assertEqual(result['action'], 'unresolved')
                self.assertEqual(result['branches'][1]['reason'], reason)

    def test_follow_up_must_match_the_public_event_window(self):
        outside = diagnostic.solve_public(self.inputs['R06'], '2025-01-02')
        conflicting = diagnostic.solve_public(self.inputs['R04'], '2025-01-01')
        self.assertEqual(outside['reason'], 'event_date_outside_range')
        self.assertEqual(conflicting['reason'], 'conflicting_event_dates')

    def test_citations_valid_on_wrong_date_fail_date_binding(self):
        expected, = diagnostic.solve_public(self.inputs['R05'])['branches']
        row = {'status': 'complete', 'output': 'Conclusion: NO\nEvidence: E1, E2'}
        branch = diagnostic.branch_record(row, expected)
        self.assertTrue(branch['accepted_by_frozen_aggregate'])
        self.assertFalse(branch['date_bound_evidence'])

    def test_r06_evidence_only_exposes_a_wrong_unique_result(self):
        modes = diagnostic.build()['first_interventions']['R06']
        self.assertEqual(modes['original']['action'], 'unresolved')
        self.assertTrue(modes['evidence_only']['wrong_unique'])
        self.assertFalse(modes['evidence_only']['answer'])
        self.assertEqual(modes['both']['action'], 'ask_date')
        self.assertTrue(modes['both']['strict_pass'])
