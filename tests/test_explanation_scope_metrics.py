"""Synthetic endpoint declarations, not actual experimental materials or review evidence."""
import copy
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import explanation_scope_metrics as metrics


def fixture():
    review = metrics.blank_review()
    review['provenance'] = dict(reviewer_id='synthetic_fixture_not_actual_reviewer',
                                history_exposure='declared_exposed',
                                description='Synthetic endpoint test only; no actual review.')
    for row in review['rows']:
        row.update(technical_status='complete', review_status='reviewed',
                   source_item_id=f"synthetic_{row['scene']}_{row['condition']}",
                   input_sha256=hashlib.sha256(str(row).encode()).hexdigest(),
                   output_sha256='0' * 64, gives_unretracted_target_value='no',
                   provides_substantive_explanation='yes', whole_explanation_support='supported',
                   overbroad_missing_information_claim='no')
        if row['condition'] in ('I0', 'IU'):
            row.update(withholds_target_with_support='yes', unsupported_target_conflict='no')
        elif row['condition'] == 'S':
            row.update(gives_unretracted_target_value='yes', grounded_target_answer='yes')
        else:
            row.update(recognizes_target_conflict='yes', unresolved_target_side_selection='no')
    return review


def row_for(review, condition, scene=1):
    return next(row for row in review['rows'] if row['scene'] == scene and row['condition'] == condition)


def assert_conflict(row):
    row.update(unsupported_target_conflict='yes', whole_explanation_support='unsupported')


class ScopeMetricsTests(unittest.TestCase):
    def test_blank_slots_are_not_zero_error_results(self):
        result = metrics.summarize(metrics.blank_review())
        self.assertEqual(result['status'], 'no_reviewed_endpoints')
        self.assertEqual(result['reviewed_slots'], 0)
        for k in ('point', 'identification_lower', 'identification_upper'):
            self.assertIsNone(result['primary'][k])
        for group in result['conditions'].values():
            for endpoint in group['endpoints'].values():
                self.assertEqual(endpoint['planned'], 12)
                self.assertEqual(endpoint['unreviewed'], 12)
                self.assertEqual(endpoint['explicit_reviewed_unknown'], 0)
                self.assertIsNone(endpoint['point'])

    def test_full_grid_missing_extra_duplicate_or_boolean_scene_is_rejected(self):
        mutations = [lambda r: r['rows'].pop(),
                     lambda r: r['rows'].append(copy.deepcopy(r['rows'][0])),
                     lambda r: r['rows'].__setitem__(1, copy.deepcopy(r['rows'][0])),
                     lambda r: r['rows'][0].update(scene=True)]
        for mutate in mutations:
            review = fixture(); mutate(review)
            with self.assertRaises(ValueError):
                metrics.summarize(review)

    def test_changed_contract_or_draft_binding_rejected(self):
        for field in ('draft_sha256', 'contract_sha256'):
            review = fixture(); review[field] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'binding'):
                metrics.summarize(review)

    def test_unreviewed_null_and_explicit_unknown_remain_distinct(self):
        review = fixture()
        row_for(review, 'IU').update(withholds_target_with_support='unknown',
                                     unsupported_target_conflict='unknown',
                                     whole_explanation_support='ambiguous')
        result = metrics.summarize(review)
        w = result['conditions']['IU']['endpoints']['withholds_target_with_support']
        self.assertEqual((w['reviewed'], w['unreviewed'], w['explicit_reviewed_unknown']), (12, 0, 1))
        self.assertIsNone(result['primary']['point'])
        self.assertEqual(result['primary']['identification_lower'], 0)
        self.assertAlmostEqual(result['primary']['identification_upper'], 1/12)
        review = metrics.blank_review()
        row_for(review, 'IU')['unsupported_target_conflict'] = 'no'
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            metrics.summarize(review)

    def test_joint_logic_and_all_81_paired_bounds(self):
        states = list(itertools.product(('yes', 'no', 'unknown'), repeat=2))
        def possible(value):
            return {'yes': {1}, 'no': {0}, 'unknown': {0, 1}}[value]
        possible_joint = {}
        for w, e in states:
            outcomes = {a & b for a in possible(w) for b in possible(e)}
            code = metrics.joint(w, e)
            self.assertEqual(possible(code), outcomes)
            possible_joint[(w, e)] = outcomes
        for left, right in itertools.product(states, repeat=2):
            lower_l, upper_l = metrics.interval(metrics.joint(*left))
            lower_r, upper_r = metrics.interval(metrics.joint(*right))
            outcomes = {a-b for a in possible_joint[left] for b in possible_joint[right]}
            self.assertEqual((min(outcomes), max(outcomes)), (lower_l-upper_r, upper_l-lower_r))

    def test_joint_can_be_known_no_with_one_reviewed_unknown(self):
        review = fixture()
        row_for(review, 'IU').update(withholds_target_with_support='no',
                                     unsupported_target_conflict='unknown',
                                     whole_explanation_support='ambiguous')
        result = metrics.summarize(review)
        self.assertEqual(result['primary']['point'], 0)
        self.assertIsNone(result['conditions']['IU']['endpoints']['unsupported_target_conflict']['point'])

    def test_direction_and_order_independence(self):
        for condition, sign in [('IU', 1), ('I0', -1)]:
            review = fixture()
            for row in review['rows']:
                if row['condition'] == condition:
                    assert_conflict(row)
            result = metrics.summarize(review)
            self.assertEqual(result['primary']['point'], sign)
            review['rows'].reverse()
            self.assertEqual(metrics.summarize(review), result)

    def test_primary_is_not_filtered_by_supported_withholding(self):
        review = fixture()
        first = row_for(review, 'IU', 1)
        first.update(withholds_target_with_support='no', gives_unretracted_target_value='yes')
        assert_conflict(first)
        assert_conflict(row_for(review, 'IU', 2))
        result = metrics.summarize(review)
        self.assertEqual(result['primary']['planned_pairs'], 12)
        self.assertAlmostEqual(result['primary']['point'], 1/12)
        self.assertEqual(result['conditions']['IU']['endpoints']['unsupported_target_conflict']['yes'], 2)
        conditional = result['conditions']['IU']['E_given_W_yes_descriptive_only']
        self.assertEqual(conditional['selected_reviewed_rows'], 11)
        self.assertAlmostEqual(conditional['summary']['point'], 1/11)
        self.assertTrue(conditional['not_the_primary_effect'])

    def test_partial_review_keeps_full12_denominator(self):
        review = metrics.blank_review()
        complete = fixture()
        review['provenance'] = complete['provenance']
        review['rows'][2] = copy.deepcopy(row_for(complete, 'IU'))
        assert_conflict(review['rows'][2])
        result = metrics.summarize(review)
        self.assertEqual(result['reviewed_slots'], 1)
        self.assertEqual(result['primary']['fully_reviewed_pairs'], 0)
        self.assertIsNone(result['primary']['point'])
        self.assertAlmostEqual(result['primary']['identification_lower'], -11/12)
        self.assertEqual(result['primary']['identification_upper'], 1)

    def test_technical_failures_cannot_be_scored_as_correct(self):
        for status in ('not_collected', 'empty', 'truncated', 'unreadable', 'failed'):
            review = fixture(); row_for(review, 'IU')['technical_status'] = status
            with self.assertRaisesRegex(ValueError, 'Only complete'):
                metrics.summarize(review)
        review = metrics.blank_review()
        row_for(review, 'IU')['technical_status'] = 'truncated'
        self.assertIsNone(metrics.summarize(review)['primary']['point'])

    def test_conditions_have_distinct_applicable_endpoints(self):
        review = fixture(); row_for(review, 'CT')['unsupported_target_conflict'] = 'yes'
        with self.assertRaisesRegex(ValueError, 'inapplicable'):
            metrics.summarize(review)
        review = fixture()
        row_for(review, 'CT').update(gives_unretracted_target_value='yes',
                                     unresolved_target_side_selection='yes')
        result = metrics.summarize(review)
        self.assertEqual(result['conditions']['CT']['endpoints']['recognizes_target_conflict']['yes'], 12)
        self.assertEqual(result['conditions']['CT']['endpoints']['unresolved_target_side_selection']['yes'], 1)
        self.assertEqual(result['primary']['point'], 0)

    def test_target_and_explanation_support_do_not_overwrite_each_other(self):
        review = fixture()
        row_for(review, 'S')['whole_explanation_support'] = 'unsupported'
        assert_conflict(row_for(review, 'IU'))
        result = metrics.summarize(review)
        self.assertEqual(result['conditions']['S']['endpoints']['grounded_target_answer']['yes'], 12)
        self.assertEqual(result['conditions']['IU']['endpoints']['withholds_target_with_support']['yes'], 12)
        self.assertAlmostEqual(result['primary']['point'], 1/12)

    def test_no_explanation_is_not_applicable_not_supported(self):
        review = fixture()
        row = row_for(review, 'IU')
        row.update(provides_substantive_explanation='no', whole_explanation_support='not_applicable')
        result = metrics.summarize(review)
        self.assertEqual(result['conditions']['IU']['whole_explanation_support']['not_applicable'], 1)
        self.assertEqual(result['conditions']['IU']['whole_explanation_support']['supported'], 11)
        row['whole_explanation_support'] = 'supported'
        with self.assertRaisesRegex(ValueError, 'absence'):
            metrics.summarize(review)

    def test_false_missing_information_claim_can_coexist_with_correct_withholding(self):
        review = fixture()
        row_for(review, 'IU').update(overbroad_missing_information_claim='yes',
                                     whole_explanation_support='contradicted')
        result = metrics.summarize(review)
        self.assertEqual(result['conditions']['IU']['endpoints']['withholds_target_with_support']['yes'], 12)
        self.assertEqual(result['conditions']['IU']['endpoints']['overbroad_missing_information_claim']['yes'], 1)
        self.assertEqual(result['primary']['point'], 0)
        row_for(review, 'IU')['whole_explanation_support'] = 'supported'
        with self.assertRaisesRegex(ValueError, 'false missing'):
            metrics.summarize(review)

    def test_inconsistent_target_claims_and_source_declarations_rejected(self):
        changes = [('IU', {'gives_unretracted_target_value': 'yes'}),
                   ('IU', {'unsupported_target_conflict': 'yes'}),
                   ('S', {'gives_unretracted_target_value': 'no'}),
                   ('CT', {'unresolved_target_side_selection': 'yes'}),
                   ('IU', {'input_sha256': 'invented'})]
        for condition, change in changes:
            review = fixture(); row_for(review, condition).update(change)
            with self.assertRaises(ValueError):
                metrics.summarize(review)

    def test_self_reported_independence_never_opens_gate(self):
        review = fixture()
        review['provenance']['history_exposure'] = 'declared_unexposed'
        result = metrics.summarize(review)
        self.assertEqual(result['actual_independent_approvals'], 0)
        self.assertFalse(result['formal_gate'])
        self.assertFalse(result['gpu_launch_ready'])
        self.assertFalse(result['provenance_and_citations_verified'])

    def test_default_cli_only_verifies_empty_template(self):
        run = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/explanation_scope_metrics.py')],
                             capture_output=True, text=True, check=True)
        result = json.loads(run.stdout)
        self.assertEqual(result['verification'], 'contract_and_empty_planning_template_consistent')
        self.assertEqual(result['reviewed_slots'], 0)
        self.assertIsNone(result['primary']['point'])


if __name__ == '__main__':
    unittest.main()
