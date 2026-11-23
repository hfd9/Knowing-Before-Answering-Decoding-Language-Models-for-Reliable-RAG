"""Boundaries that would otherwise turn incomplete evidence into an answer."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from query_determinacy_rule_applicability import evaluate, normalize


class RuleApplicabilityTests(unittest.TestCase):
    def test_date_at_boundary_applies_and_day_before_does_not(self):
        target = {'cutoff': '2030-06-15'}
        for day, label in ((14, 'U'), (15, 'Y'), (16, 'Y')):
            text = f'本件于2030年6月{day}日完成核验。'
            self.assertEqual(evaluate('date', target, normalize('date', text))['final'], label)
        self.assertIsNone(normalize('date', '本件于2030年2月30日完成核验。'))

    def test_wrong_entity_never_implies_a_negative_applicability_result(self):
        target = {'first': '青栎', 'second': '霁蓝'}
        unrelated = normalize('scope', '台账记载：「青栎」和「别物」是两件不同物品的登记名。')
        result = evaluate('scope', target, unrelated)
        self.assertIsNone(result['exception_applies'])
        self.assertIsNone(result['final'])
        self.assertEqual(result['worlds']['W2']['answer'], 'X')
        self.assertEqual(result['worlds']['W2']['evidence'], [])

    def test_reversed_grant_and_rephrase_preserve_roles(self):
        target = {'from': '馆务组', 'to': '布展组'}
        direct = '馆务组授权布展组为本件签发豁免。'
        reversed_grant = '布展组授权馆务组为本件签发豁免。'
        self.assertEqual(evaluate('delegation', target, normalize('delegation', direct))['final'], 'Y')
        flipped = evaluate('delegation', target, normalize('delegation', reversed_grant))
        self.assertEqual(flipped['final'], 'U')
        self.assertEqual(flipped['worlds']['W2']['rule'], 'R2')
        self.assertIn('F1', flipped['worlds']['W2']['evidence'])
        proxy = '这次能替馆务组为本件签发豁免的是布展组。'
        self.assertIsNone(normalize('delegation', proxy))
        self.assertEqual(normalize('delegation', proxy, include_proxy=True),
                         normalize('delegation', direct))

    def test_uncertainty_or_conflicting_sentences_are_unresolved(self):
        target = {'from': '馆务组', 'to': '布展组'}
        for text in ('授权方向未查明。', '馆务组授权布展组为本件签发豁免。布展组授权馆务组为本件签发豁免。'):
            self.assertIsNone(evaluate('delegation', target, normalize('delegation', text))['final'])


if __name__ == '__main__':
    unittest.main()
