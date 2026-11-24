"""Protect inclusive coverage and comparator boundaries in the structured evaluator."""

from dataclasses import replace
from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from query_determinacy_threshold_versions import ThresholdRule, ThresholdVersion, evaluate  # noqa: E402


class ThresholdVersionsTests(unittest.TestCase):
    def setUp(self):
        self.start, self.end = date(2024, 12, 30), date(2025, 1, 2)
        self.old = ThresholdVersion(date(2024, 1, 1), date(2024, 12, 31), 32400, 'A24')
        self.new = ThresholdVersion(date(2025, 1, 1), date(2025, 12, 31), 33500, 'A25')
        self.rule = ThresholdRule('<=', 'consummation', 'A1', (self.new, self.old))

    def test_comparison_sign_controls_answer_at_equality(self):
        day = date(2025, 1, 1)
        new = evaluate(self.rule, 33500, self.start, self.end, scope_established=True, event_date=day)
        old_sign = evaluate(replace(self.rule, comparison='>'), 33500, self.start, self.end,
                            scope_established=True, event_date=day)
        self.assertIs(new['answer'], True)
        self.assertIs(old_sign['answer'], False)
        self.assertEqual(new['evidence'], ['A1', 'A25'])

    def test_spans_clip_to_the_admitted_range_without_losing_coverage(self):
        result = evaluate(self.rule, 32401, self.start, self.end, scope_established=True)
        self.assertEqual(result['action'], 'ask_date')
        self.assertEqual(result['ask_event'], 'consummation')
        self.assertEqual([(b['from'], b['through'], b['answer']) for b in result['branches']],
                         [('2024-12-30', '2024-12-31', False), ('2025-01-01', '2025-01-02', True)])

    def test_gaps_and_overlaps_never_produce_a_unique_answer(self):
        for modified, reason in ((replace(self.new, valid_from=self.end), 'coverage_gap'),
                                 (replace(self.new, valid_from=date(2024, 12, 31)), 'overlapping_versions')):
            with self.subTest(reason=reason):
                rule = replace(self.rule, versions=(self.old, modified))
                result = evaluate(rule, 32400, self.start, self.end, scope_established=True)
                self.assertEqual((result['action'], result['answer'], result['reason']), ('unresolved', None, reason))

    def test_scope_must_be_known_and_event_must_be_in_range(self):
        for scope, reason in ((None, 'scope_not_established'), (False, 'rule_outside_scope')):
            result = evaluate(self.rule, 32400, self.start, self.end, scope_established=scope)
            self.assertEqual((result['action'], result['reason']), ('unresolved', reason))
        outside = evaluate(self.rule, 32400, self.start, self.end, scope_established=True, event_date=date(2025, 1, 3))
        self.assertEqual((outside['action'], outside['reason']), ('unresolved', 'event_date_outside_range'))
