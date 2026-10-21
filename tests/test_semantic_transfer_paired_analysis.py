"""Pairing, three-valued endpoints and clustered-resampling integrity tests."""

import copy
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import semantic_transfer_paired_analysis as paired


def fixture():
    rows = []
    for i in range(30):
        for e in ['A', 'B']:
            for c in ['S', 'K', 'I', 'C']:
                row = dict(id=f'stv{i:02}_{e}_{c}', item_id=f'{i}_{e}_{c}',
                    original_id=f'base{i:02}', partition='semantic_train', expression=e,
                    condition=c, question=f'question {i}', probe_pred='conflict',
                    probe_probabilities=dict(answer=.3, refuse=.1, conflict=.6),
                    exposed_author_input_mode=dict(S='answer', K='answer', I='refuse', C='conflict')[c],
                    **{f: 'no' for f in paired.FIELDS})
                if i == 29 and c in ['S', 'K']:
                    row['exposed_author_input_mode'] = 'unknown'
                rows.append(row)
    return rows


class PairedAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = fixture()
        cls.endpoint = dict(focal_probability='refuse', target_behavior='has_substantive_answer',
            behavior_changes=['has_substantive_answer', 'acknowledges_insufficiency'])

    def test_all_pairs_retained_including_unknown_reference_membership(self):
        pairs = paired.make_pairs(self.rows)
        self.assertEqual(len(pairs), 180)
        self.assertEqual(sum(p['author_reference_eligible'] for p in pairs), 174)
        self.assertEqual({c: sum(p['contrast'] == c for p in pairs)
            for c in paired.CONTRASTS}, {c: 60 for c in paired.CONTRASTS})

    def test_missing_or_duplicate_variant_rejected(self):
        with self.assertRaises(ValueError):
            paired.make_pairs(self.rows[:-1])
        rows = copy.deepcopy(self.rows)
        rows[-1]['expression'], rows[-1]['condition'] = 'A', 'S'
        with self.assertRaises(ValueError):
            paired.make_pairs(rows)

    def test_question_or_partition_mismatch_rejected(self):
        for field in ['question', 'partition']:
            rows = copy.deepcopy(self.rows)
            rows[2][field] = 'different'
            with self.subTest(field=field), self.assertRaises(ValueError):
                paired.make_pairs(rows)

    def test_nonfinite_or_nonprobability_values_rejected(self):
        for value in [float('nan'), -.2, 2., .7]:
            rows = copy.deepcopy(self.rows)
            rows[0]['probe_probabilities']['refuse'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                paired.make_pairs(rows)

    def test_probability_deltas_keep_direction_and_zero_sum(self):
        rows = copy.deepcopy(self.rows)
        rows[2]['probe_probabilities'] = dict(answer=.2, refuse=.3, conflict=.5)
        p = paired.make_pairs(rows)[0]
        self.assertAlmostEqual(p['delta_p_refuse'], .2)
        self.assertAlmostEqual(p['delta_p_answer'], -.1)
        self.assertAlmostEqual(sum(p['delta_p_' + m] for m in paired.MODES), 0)

    def test_unknown_joint_not_treated_as_a_negative_answer(self):
        p = paired.make_pairs(self.rows)[0]
        p['right_has_substantive_answer'] = 'unknown'
        p['delta_p_refuse'] = .1
        values = paired.interval_metrics(p, self.endpoint)
        self.assertEqual(values['increase_and_target_behavior'], (0, 1))
        p['delta_p_refuse'] = -.1
        self.assertEqual(paired.interval_metrics(p, self.endpoint)['increase_and_target_behavior'], (0, 0))

    def test_unknown_endpoint_difference_retains_both_bounds(self):
        p = paired.make_pairs(self.rows)[0]
        p['left_has_substantive_answer'] = p['right_has_substantive_answer'] = 'unknown'
        values = paired.interval_metrics(p, self.endpoint)
        self.assertEqual(values['change_has_substantive_answer'], (-1, 1))
        summary = paired.cluster_summary([p], self.endpoint, repeats=20)
        result = summary['metrics']['change_has_substantive_answer']
        self.assertIsNone(result['point'])
        self.assertEqual(result['sampling_95_for_lower_bound'], [-1, -1])
        self.assertEqual(result['sampling_95_for_upper_bound'], [1, 1])

    def test_bootstrap_resamples_whole_bases_with_multiplicity(self):
        pairs = [p for p in paired.make_pairs(self.rows) if p['contrast'] == 'S_to_I'][:6]
        for p, value in zip(pairs, [0, 0, 1, 1, .5, .5]):
            p['delta_p_refuse'] = value
        result = paired.cluster_summary(pairs, self.endpoint, repeats=2000, seed=7)
        metric = result['metrics']['delta_p_refuse']
        self.assertEqual((result['pairs'], result['bases']), (6, 3))
        draws = np.random.default_rng(7).integers(0, 3, (2000, 3))
        expected = np.quantile(np.asarray([0, 1, .5])[draws].mean(axis=1), [.025, .975])
        np.testing.assert_allclose(metric['sampling_95_for_lower_bound'], expected)
        self.assertEqual(metric['sampling_95_for_lower_bound'], [0, 1])
        self.assertEqual(metric['point'], .5)

    def test_unequal_base_sizes_use_sampled_row_denominators(self):
        pairs = [p for p in paired.make_pairs(self.rows) if p['contrast'] == 'S_to_I'][:4]
        pairs = pairs[:1] + pairs[2:]
        for p, value in zip(pairs, [1, 0, 0]):
            p['delta_p_refuse'] = value
        result = paired.cluster_summary(pairs, self.endpoint, repeats=100, seed=9)
        self.assertAlmostEqual(result['metrics']['delta_p_refuse']['point'], 1 / 3)

    def test_refusal_is_a_conjunction_and_not_any_nonanswer(self):
        row = dict(acknowledges_insufficiency='yes', has_substantive_answer='unknown')
        self.assertEqual(paired.behavior(row, 'erroneous_refusal'), 'unknown')
        row['acknowledges_insufficiency'] = 'no'
        self.assertEqual(paired.behavior(row, 'erroneous_refusal'), 'no')

    def test_composition_separates_both_mixed_and_neither_bases(self):
        rows = copy.deepcopy(self.rows)
        for r in rows:
            if r['condition'] == 'I' and (r['original_id'] == 'base00' or
                    (r['original_id'] == 'base01' and r['expression'] == 'A')):
                r['probe_pred'] = 'refuse'
        pairs = paired.make_pairs(rows)
        bases = paired.base_rows(rows, pairs)
        result = paired.composition(rows, bases)
        groups = result['I_probe_base_groups']
        self.assertEqual([groups[n]['bases'] for n in ['both_refuse', 'mixed', 'neither_refuse']], [1, 1, 28])
        self.assertEqual(len(result['within_base_mixed_comparisons']), 1)
        self.assertEqual(result['within_base_mixed_comparisons'][0]['refuse_minus_other_lower'], 0)


if __name__ == '__main__':
    unittest.main()
