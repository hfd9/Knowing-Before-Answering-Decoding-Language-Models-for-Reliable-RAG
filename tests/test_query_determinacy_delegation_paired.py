"""Check the diagnosed failure modes without generating model responses."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from query_determinacy_delegation_paired import compare, judge, load_packet, prompt, summarize


class DelegationPairedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy, cls.instructions, cls.dev, cls.dev_ref, cls.held, cls.ref, cls.groups = load_packet()

    def test_reference_replay_and_public_prompt(self):
        self.assertEqual((len(self.dev), len(self.held), len(self.groups)), (8, 16, 4))
        for id_, records in self.held.items():
            for route in ('direct', 'extract'):
                rendered = prompt(records, self.instructions, route)
                self.assertNotIn(id_, rendered)
                self.assertNotIn(self.ref[id_]['root'], rendered)
                self.assertTrue(all(f'[{key}] {value}' in rendered for key, value in records.items()))

    def test_heldout_prediction_cannot_be_read_from_wording_family(self):
        for family in ('H1', 'H2'):
            unique = [ref for ref in self.ref.values() if ref['family'] == family and ref['direction'] == 'match']
            self.assertCountEqual((ref['result']['final'] for ref in unique), ('Y', 'Y', 'N', 'N'))
            self.assertCountEqual((ref['structure']['exception']['overrides'] for ref in unique),
                                  ('R1', 'R1', 'R2', 'R2'))

    def test_frozen_baseline_retains_unresolved_and_never_forces_unique(self):
        rows = {k: judge(case, self.ref[k], 'parser') for k, case in self.held.items()}
        summary = summarize(rows, self.groups, self.ref)
        self.assertEqual(summary['correct_grounded'], 4)
        self.assertEqual(len(summary['unresolved']), 12)
        self.assertEqual(summary['unfounded_unique'], [])
        self.assertTrue(all(rows[k]['final'] == 'X' for k in summary['unresolved']))

    def test_correct_token_schema_and_missing_evidence_are_scored(self):
        id_ = next(iter(self.held))
        case, ref = self.held[id_], self.ref[id_]
        structured = json.dumps(ref['structure'], ensure_ascii=False)
        self.assertTrue(judge(case, ref, 'extract', f'```json\n{structured}\n```')['correct_grounded'])
        direct = dict(structure=ref['structure'], **ref['result'])
        raw = json.dumps(direct, ensure_ascii=False)
        self.assertTrue(judge(case, ref, 'direct', raw)['correct_grounded'])
        direct = json.loads(raw)
        direct['worlds']['W1']['evidence'].remove('R3')
        outcome = judge(case, ref, 'direct', json.dumps(direct))
        self.assertFalse(outcome['correct_grounded'])
        self.assertFalse(outcome['world_correct']['W1']['evidence'])

    def test_wrong_direction_and_malformed_outputs_preserve_risk(self):
        id_ = next(k for k, ref in self.ref.items() if ref['direction'] == 'reverse')
        case, ref = self.held[id_], self.ref[id_]
        structure = json.loads(json.dumps(ref['structure']))
        structure['grant'] = {k: structure['exception'][k] for k in ('grantor', 'recipient')}
        forced = judge(case, ref, 'extract', json.dumps(structure))
        self.assertFalse(forced['correct_grounded'])
        self.assertTrue(forced['unfounded_unique'])
        malformed = judge(case, ref, 'direct', '{"final":"Y"}')
        self.assertEqual(malformed['status'], 'invalid')
        self.assertTrue(malformed['unfounded_unique'])
        duplicate = judge(case, ref, 'extract', '{"grant": null, "grant": null, "exception": null}')
        self.assertEqual(duplicate['status'], 'invalid')

    def test_compare_requires_cross_family_gain_and_no_new_risk(self):
        baseline_rows = {k: judge(case, self.ref[k], 'parser') for k, case in self.held.items()}
        baseline = summarize(baseline_rows, self.groups, self.ref)
        perfect_rows = {k: judge(case, self.ref[k], 'extract', json.dumps(self.ref[k]['structure']))
                        for k, case in self.held.items()}
        perfect = summarize(perfect_rows, self.groups, self.ref)
        self.assertEqual(compare(perfect, baseline, self.policy)['decision'], 'continue_candidate')
        same_family = {k: perfect_rows[k] if ref['family'] == 'H1' else baseline_rows[k]
                       for k, ref in self.ref.items()}
        result = compare(summarize(same_family, self.groups, self.ref), baseline, self.policy)
        self.assertEqual(len(result['wins']), 2)
        self.assertEqual(result['decision'], 'no_expansion_signal')
        risky = dict(perfect, unfounded_unique=['q-example-unsupported-unique'])
        self.assertEqual(compare(risky, baseline, self.policy)['decision'], 'no_expansion_signal')


if __name__ == '__main__':
    unittest.main()
