"""Check direction, priority, and conservative unknowns in the source parser."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from query_determinacy_delegation_source import (
    exception_from_source, fact_direction, solve_from_sources, verify_fact,
)


class DelegationSourceTests(unittest.TestCase):
    def setUp(self):
        self.edge = {'grantor': '灯检组', 'recipient': '底片组'}
        self.facts = (
            '本件仅有一项授权：「灯检组」授权「底片组」为本件签发复核单。',
            '本件复核单的核发权仅有一笔委托：「底片组」从「灯检组」取得该权。',
            '本件复核单仅登记一条有效代签委托：委托方为「灯检组」，代签方为「底片组」。',
            '关于本件复核单，能替「灯检组」代签的只有「底片组」。这是唯一有效的授权委托。',
        )
        self.rules = (
            '本件若由「灯检组」授权「底片组」签发复核单，则改按本条判为准入，优先于R2。',
            '本条的生效条件是「底片组」取得「灯检组」授予的本件复核单核发权。条件满足时，本件判为准入，本条取代R2。',
            '适用本条须同时对上两个身份：授权方为「灯检组」，代签本件复核单的一方为「底片组」。'
            '身份符合时，本件判为准入，该结论覆盖R2。',
            '在替「灯检组」代签本件复核单的权力交给「底片组」时，用本条取代R2，把本件判为准入。',
        )

    def test_all_forms_derive_same_directed_fact_and_rule(self):
        for fact, rule in zip(self.facts, self.rules, strict=True):
            self.assertEqual(fact_direction(fact), self.edge)
            self.assertEqual(exception_from_source(rule), dict(self.edge, answer='Y', overrides='R2'))

    def test_swapping_actors_changes_unique_answer_in_every_form(self):
        base = dict(W1='本件类别为「底片已验」。', W2='本件类别为「底片待验」。',
                    R1='「底片已验」类别按本条判为准入。', R2='「底片待验」类别按本条判为不准入。')
        for fact, rule in zip(self.facts, self.rules, strict=True):
            reverse = fact.replace('灯检组', '交换位置').replace('底片组', '灯检组').replace('交换位置', '底片组')
            self.assertEqual(fact_direction(reverse), {'grantor': '底片组', 'recipient': '灯检组'})
            self.assertEqual(solve_from_sources(dict(base, R3=rule, F1=fact))['final'], 'Y')
            self.assertEqual(solve_from_sources(dict(base, R3=rule, F1=reverse))['final'], 'U')

    def test_unknown_or_ambiguous_records_abstain(self):
        for fact in self.facts:
            self.assertIsNone(fact_direction(fact + '该授权已撤销。'))
            self.assertIsNone(fact_direction(fact.replace('底片组', '灯检组')))
        for rule in self.rules:
            self.assertIsNone(exception_from_source(rule + '同时适用R1。'))
            self.assertIsNone(exception_from_source(rule.replace('R2', 'R9')))
        records = dict(W1='本件类别为「底片已验」。', W2='本件类别为「底片待验」。',
                       R1='「底片已验」类别按本条判为准入。', R2='「底片待验」类别按本条判为不准入。',
                       R3=self.rules[0], F1='授权登记仍待查。')
        self.assertEqual(solve_from_sources(records)['final'], 'X')
        self.assertEqual(solve_from_sources(dict(records, R3='规则优先关系仍待查。', F1=self.facts[0]))['final'], 'X')

    def test_verifier_keeps_matches_and_rejects_reverse_without_mutation(self):
        records = {'F1': self.facts[2]}
        expected = dict(self.edge, answer='Y', overrides='R2')
        original = {'grant': self.edge, 'exception': expected}
        self.assertEqual(verify_fact(records, original), ('confirmed', self.edge, original))
        reverse = {'grantor': '底片组', 'recipient': '灯检组'}
        revised = dict(original, grant=reverse)
        status, source, checked = verify_fact(records, revised)
        self.assertEqual((status, source, checked), ('roles_reversed', self.edge, dict(original, grant=None)))
        self.assertEqual(revised['grant'], reverse)


if __name__ == '__main__':
    unittest.main()
