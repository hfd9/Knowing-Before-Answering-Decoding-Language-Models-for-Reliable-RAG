"""Exercise the date decision entry point with valid and rejected evidence."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / 'scripts/query_determinacy_date_verified.py'
sys.path.insert(0, str(ENTRY.parent))

import query_determinacy_date_verified as verified  # noqa: E402


class VerifiedDateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'docs/review/2026-11-24-date-material-acceptance-v1/inputs.json'
        cls.inputs = {row['id']: row['input'] for row in json.loads(path.read_bytes())}

    def test_checked_branches_can_answer_or_ask(self):
        first = {'date': '2024-12-31', 'answer': True, 'evidence': ['E2', 'E1']}
        second = {'date': '2025-01-01', 'answer': True, 'evidence': ['E1', 'E3']}
        same = verified.verify_branches(self.inputs['R03'], [second, first])
        different = verified.verify_branches(self.inputs['R06'], [dict(second, answer=False), first])
        self.assertEqual((same['action'], same['answer']), ('answer', True))
        self.assertEqual((different['action'], different['answer']), ('ask_date', None))
        self.assertIn('become contractually bound', different['question'])

    def test_correct_citations_do_not_allow_two_false_conclusions(self):
        claims = [{'date': '2024-12-31', 'answer': False, 'evidence': ['E1', 'E2']},
                  {'date': '2025-01-01', 'answer': False, 'evidence': ['E1', 'E3']}]
        result = verified.verify_branches(self.inputs['R06'], claims)
        self.assertEqual((result['action'], result['answer'], result['evidence']), ('unresolved', None, []))
        self.assertEqual(result['issues'], [{'code': 'conclusion_does_not_match_rule', 'date': '2024-12-31'}])

    def test_citations_must_belong_to_the_supplied_date(self):
        old_rule = {'date': '2025-01-01', 'answer': False, 'evidence': ['E1', 'E2']}
        result = verified.verify_branches(self.inputs['R06'], [old_rule], '2025-01-01')
        self.assertEqual(result['action'], 'unresolved')
        self.assertEqual(result['issues'], [{'code': 'evidence_does_not_match_date', 'date': '2025-01-01'}])

    def test_missing_duplicate_unexpected_and_invalid_branches(self):
        one = {'date': '2024-12-31', 'answer': True, 'evidence': ['E1', 'E2']}
        two = {'date': '2025-01-01', 'answer': False, 'evidence': ['E1', 'E3']}
        candidates = [([one], 'missing_branch'), ([one, one, two], 'duplicate_branch'),
                      ([one, two, dict(two, date='2025-01-02')], 'unexpected_branch'),
                      ([one, dict(two, answer=0)], 'invalid_branch'),
                      ([one, dict(two, evidence=['E1', 'E3', 'E3'])], 'invalid_branch'), (None, 'invalid_branch_list')]
        for claims, error in candidates:
            with self.subTest(error=error):
                result = verified.verify_branches(self.inputs['R06'], claims)
                self.assertEqual(result['action'], 'unresolved')
                self.assertIn(error, {issue['code'] for issue in result['issues']})

    def test_unsupported_comparator_and_conflicting_dates_remain_unresolved(self):
        changed = self.inputs['R03'].replace('amount exceeding the threshold', 'amount at least the threshold')
        self.assertEqual(verified.evaluate(changed)['reason'], 'unsupported_packet')
        self.assertEqual(verified.evaluate(self.inputs['R01'], '2025-01-01')['reason'], 'conflicting_event_dates')

    def test_cli_accepts_text_file_and_does_not_fallback_from_null_claims(self):
        with tempfile.TemporaryDirectory() as work:
            packet, claims = (Path(work) / name for name in ('packet.txt', 'claims.json'))
            packet.write_bytes(self.inputs['R06'].replace('\n', '\r\n').encode() + b'\r\n')
            claims.write_text('null', encoding='utf-8')
            command = [sys.executable, str(ENTRY), str(packet), '--event-date', '2025-01-01']
            solved = json.loads(subprocess.check_output(command, text=True))
            guarded = json.loads(subprocess.check_output(command + ['--branches', str(claims)], text=True))
        self.assertEqual((solved['action'], solved['answer']), ('answer', False))
        self.assertEqual(guarded['action'], 'unresolved')
        self.assertIn('invalid_branch_list', {issue['code'] for issue in guarded['issues']})
