"""Temporary fake-fit tests do not consume the real design's one-fit allowance."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import semantic_transfer_exploratory_retrain as retrain


class FakeScaler:
    def fit(self, x):
        self.mean_ = x.mean(axis=0)
        self.n_features_in_ = x.shape[1]
        return self

    def transform(self, x):
        return x - self.mean_


class FakeClassifier:
    calls = 0

    def __init__(self, **parameters):
        self.parameters = parameters

    def fit(self, x, y):
        type(self).calls += 1
        self.n_iter_ = np.array([3])
        self.classes_ = np.array([0, 1, 2])
        return self

    def predict_proba(self, x):
        return np.tile([.2, .3, .5], (len(x), 1))


class FailingClassifier(FakeClassifier):
    def fit(self, x, y):
        raise RuntimeError('simulated failure')


def fixture(root):
    rows, labels = [], {}
    for i in range(12):
        for c, mode in [('S', 'answer'), ('K', 'answer'), ('I', 'refuse'), ('C', 'conflict')]:
            key = f'{i}_A_{c}'
            rows.append(dict(id=key, original_id=f'base{i}', partition='semantic_train', expression='A'))
            labels[key] = mode
    protocol = dict(task='semantic_transfer_chat_L28_exposed_author_retrain_v1',
        design_sha256='d' * 64, training_ids=[r['id'] for r in rows],
        classifier=dict(C=1, class_weight='balanced', solver='lbfgs', max_iter=2000, random_state=42))
    run = root / retrain.RUN
    run.mkdir(parents=True)
    (run / 'protocol.json').write_text(json.dumps(protocol))
    return rows, labels, protocol, run


class ExploratoryRetrainTests(unittest.TestCase):
    def test_training_excludes_B_and_other_partitions(self):
        with tempfile.TemporaryDirectory() as directory:
            rows, labels, _, _ = fixture(Path(directory))
            extra = [dict(r, id=r['id'] + '_B', expression='B') for r in rows]
            extra += [dict(r, id=r['id'] + '_dev', partition='semantic_dev') for r in rows]
            self.assertEqual(retrain.training_rows(rows + extra, labels), rows)

    def test_unknown_training_reference_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            rows, labels, _, _ = fixture(Path(directory))
            labels[rows[0]['id']] = 'unknown'
            with self.assertRaises(ValueError):
                retrain.training_rows(rows, labels)

    def test_shared_budget_marker_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, protocol, run = fixture(root)
            retrain.claim_budget(root, run, protocol)
            original = (root / retrain.BUDGET).read_bytes()
            with self.assertRaises(FileExistsError):
                retrain.claim_budget(root, run, protocol)
            self.assertEqual((root / retrain.BUDGET).read_bytes(), original)

    def test_other_run_of_same_design_blocks_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, protocol, run = fixture(root)
            other = root / 'runs/other'
            other.mkdir()
            (other / 'protocol.json').write_text(json.dumps(protocol))
            (other / 'fit_attempt.json').write_text('{}')
            with self.assertRaises(ValueError):
                retrain.claim_budget(root, run, protocol)

    def test_old_v5_budget_guard_recognizes_new_exploratory_attempt(self):
        import semantic_transfer_study_v5 as binding
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, protocol, run = fixture(root)
            protocol['design_sha256'] = binding.digest(binding.core.intake.DESIGN)
            (run / 'protocol.json').write_text(json.dumps(protocol))
            (run / 'fit_attempt.json').write_text('{}')
            with self.assertRaises(ValueError):
                binding.require_shared_fit_budget(root / 'runs/formal', root=root / 'runs')

    def test_fit_reads_only_A48_and_reuse_does_not_refit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows, labels, protocol, run = fixture(root)
            x = np.arange(48 * 2048, dtype=np.float32).reshape(48, 2048)
            FakeClassifier.calls = 0
            with patch.object(retrain, 'load_features', return_value=x) as loader:
                probe, metadata = retrain.fit_once(root, rows, labels, {}, protocol,
                    dict(amended_exploratory_fit_allowed=True), (FakeScaler, FakeClassifier))
                self.assertEqual(loader.call_args.args[2], protocol['training_ids'])
                self.assertEqual(metadata['training_rows'], 48)
            with patch.object(FakeClassifier, 'fit', side_effect=AssertionError('refit')):
                _, saved = retrain.fit_once(root, rows, labels, {}, protocol,
                    dict(amended_exploratory_fit_allowed=True), (FakeScaler, FakeClassifier))
            self.assertEqual(FakeClassifier.calls, 1)
            self.assertEqual(saved, metadata)

    def test_failed_fit_consumes_budget_and_cannot_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows, labels, protocol, run = fixture(root)
            with patch.object(retrain, 'load_features', return_value=np.ones((48, 2048), np.float32)):
                with self.assertRaises(RuntimeError):
                    retrain.fit_once(root, rows, labels, {}, protocol,
                        dict(amended_exploratory_fit_allowed=True), (FakeScaler, FailingClassifier))
            self.assertTrue((run / 'fit_attempt.json').exists())
            self.assertTrue((root / retrain.BUDGET).exists())
            with self.assertRaises(ValueError):
                retrain.fit_once(root, rows, labels, {}, protocol,
                    dict(amended_exploratory_fit_allowed=True), (FakeScaler, FakeClassifier))

    def test_claim_without_completion_stops_interrupted_fit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows, labels, protocol, run = fixture(root)
            retrain.claim_budget(root, run, protocol)
            with self.assertRaises(ValueError):
                retrain.fit_once(root, rows, labels, {}, protocol,
                    dict(amended_exploratory_fit_allowed=True), (FakeScaler, FakeClassifier))

    def test_development_nontrigger_does_not_claim_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows, labels, protocol, run = fixture(root)
            with self.assertRaises(ValueError):
                retrain.fit_once(root, rows, labels, {}, protocol,
                    dict(amended_exploratory_fit_allowed=False), (FakeScaler, FakeClassifier))
            self.assertFalse((root / retrain.BUDGET).exists())

    def test_prediction_marks_offline_execution_and_prefill_feature(self):
        scaler, classifier = FakeScaler(), FakeClassifier()
        x = np.ones((2, 2048), np.float32)
        scaler.fit(x)
        classifier.classes_ = np.array([0, 1, 2])
        predictions = retrain.predict(dict(layer=28, scaler=scaler, router=classifier), x, ['a', 'b'])
        self.assertEqual(predictions['a']['probe_pred'], 'conflict')
        self.assertFalse(predictions['a']['probe_decision_pre_first_token'])
        self.assertTrue(predictions['a']['probe_feature_pre_first_token'])
        self.assertTrue(predictions['a']['executed_offline_after_generation'])

    def test_modified_model_pickle_is_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows, labels, protocol, run = fixture(root)
            with patch.object(retrain, 'load_features', return_value=np.ones((48, 2048), np.float32)):
                retrain.fit_once(root, rows, labels, {}, protocol,
                    dict(amended_exploratory_fit_allowed=True), (FakeScaler, FakeClassifier))
            (run / 'semantic_probe.pkl').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):
                retrain.saved_probe(root, run)


if __name__ == '__main__':
    unittest.main()
