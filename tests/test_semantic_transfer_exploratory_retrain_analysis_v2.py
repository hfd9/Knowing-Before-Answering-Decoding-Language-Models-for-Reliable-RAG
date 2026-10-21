"""Regression for paired-metric token metadata and no-refit analysis."""

import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import semantic_transfer_exploratory_retrain_analysis_v2 as analysis


class RetrainAnalysisV2Tests(unittest.TestCase):
    def test_metadata_join_keeps_probabilities_and_offline_timepoint(self):
        predicted = {'a': dict(id='a', probe_probabilities=dict(answer=.2, refuse=.3, conflict=.5),
            probe_decision_pre_first_token=False)}
        original = {'a': dict(input_tokens=123)}
        result = analysis.with_token_metadata(predicted, original)
        self.assertEqual(result['a']['input_tokens'], 123)
        self.assertEqual(result['a']['probe_probabilities'], predicted['a']['probe_probabilities'])
        self.assertFalse(result['a']['probe_decision_pre_first_token'])
        self.assertNotIn('input_tokens', predicted['a'])

    def test_missing_id_or_invalid_length_rejected(self):
        with self.assertRaises(ValueError):
            analysis.with_token_metadata({'a': {}}, {'b': dict(input_tokens=1)})
        with self.assertRaises(ValueError):
            analysis.with_token_metadata({'a': {}}, {'a': dict(input_tokens=0)})

    def test_exact_old_predictions_work_with_frozen_paired_metrics(self):
        root = analysis.ROOT
        raw = analysis.fit.review.read(root, analysis.fit.review.RUN + '/predictions.json')['records']
        original = {r['id']: r for r in raw}
        predictions = {r['id']: {k: r[k] for k in ['id', 'probe_pred', 'probe_probabilities']} for r in raw}
        enriched = analysis.with_token_metadata(predictions, original)
        rows = analysis.fit.review.read(root, analysis.fit.review.MATERIALS)
        labels = {r['id']: r['semantic_mode'] for r in analysis.fit.review.read(root,
            analysis.fit.review.AUTHOR)['ratings']}
        self.assertEqual(analysis.fit.metrics.summarize(rows, enriched, labels),
            analysis.fit.metrics.summarize(rows, original, labels))

    def test_real_saved_model_analysis_has_no_fitting_path(self):
        with patch.object(analysis.fit, 'fit_once', side_effect=AssertionError('Must never refit')), \
                patch.object(analysis.fit.metrics, 'bootstrap', return_value=dict(test_only=True)):
            report, cells, predictions = analysis.compute()
        self.assertEqual((len(cells), len(predictions)), (240, 240))
        self.assertEqual(report['new_probe_fits'], 1)
        self.assertEqual(report['analysis_stage_new_fits'], 0)
        self.assertEqual(report['original_design_fit_budget_remaining'], 0)


if __name__ == '__main__':
    unittest.main()
