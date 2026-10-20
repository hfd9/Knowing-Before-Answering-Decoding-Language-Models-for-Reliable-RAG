"""Synthetic workflow tests only: none of these labels are research observations."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import semantic_transfer_study as study
import semantic_transfer_metrics as metrics


def cells(bases=2, partition='semantic_dev'):
    rows, predictions, labels = [], {}, {}
    for i in range(bases):
        for expression in ['A', 'B']:
            for condition, mode in [('S', 'answer'), ('K', 'answer'), ('I', 'refuse'), ('C', 'conflict')]:
                key = f'synthetic_{i}_{expression}_{condition}'
                rows.append(dict(id=key, original_id=f'synthetic_{i}', partition=partition,
                    expression=expression, condition=condition, question='Synthetic question?', docs=['Synthetic evidence.'] * 5))
                labels[key] = mode
                predictions[key] = dict(probe_pred=mode, input_tokens=10 + (expression == 'B'),
                    probe_probabilities={m: float(m == mode) for m in metrics.MODES})
    return rows, predictions, labels


class MetricsTests(unittest.TestCase):
    def test_consistent_wrong_predictions_do_not_establish_reliability(self):
        rows, predictions, labels = cells()
        for prediction in predictions.values():
            prediction['probe_pred'] = 'conflict'
        report = metrics.summarize(rows, predictions, labels)
        self.assertEqual(report['AB_agreement']['value'], 1)
        self.assertEqual(report['AB_both_correct']['value'], .25)
        self.assertEqual(report['S_false_conflict']['value'], 1)
        self.assertEqual(report['K_false_conflict']['value'], 1)
        self.assertEqual(report['accuracy'], .25)
        self.assertTrue(metrics.trigger_on_dev(rows, predictions, labels, len(rows))['triggered'])

    def test_unknown_and_semantic_mismatch_are_not_condition_labels(self):
        rows, predictions, labels = cells(1)
        labels[rows[0]['id']] = None
        labels['synthetic_0_B_I'] = 'answer'  # Independent judgment overrides the intended I relation.
        report = metrics.summarize(rows, predictions, labels, planned=16)
        self.assertEqual(report['semantic_coverage'], 7 / 16)
        self.assertEqual(report['unknown_or_missing_cells'], 9)
        self.assertEqual(report['AB_semantically_eligible_pairs'], 2)
        self.assertEqual(report['S_to_I_both_correct']['denominator'], 0)
        pairs = metrics.paired_rows(rows, predictions, labels)
        self.assertEqual(len(pairs), 10)
        self.assertTrue(all(p['input_token_delta'] == 1 for p in pairs if p['contrast'].startswith('AB')))

    def test_dev_trigger_rejects_eval_and_does_not_call_low_coverage_a_pass(self):
        rows, predictions, labels = cells(1)
        self.assertFalse(metrics.trigger_on_dev(rows, predictions, labels)['can_declare_pass'])
        self.assertTrue(metrics.trigger_on_dev(rows, predictions, labels, 8)['can_declare_pass'])
        rows[0]['partition'] = 'semantic_eval'
        with self.assertRaisesRegex(ValueError, 'semantic_dev only'):
            metrics.trigger_on_dev(rows, predictions, labels)

    def test_grouped_bootstrap_and_identical_paired_difference(self):
        rows, predictions, labels = cells(2)
        for row in rows:
            if row['original_id'] == 'synthetic_1':
                predictions[row['id']]['probe_pred'] = {'answer': 'refuse', 'refuse': 'conflict', 'conflict': 'answer'}[labels[row['id']]]
        result = metrics.bootstrap(rows, predictions, labels, repeats=1000)
        self.assertEqual(result['base_questions'], 2)
        self.assertEqual(result['intervals']['accuracy']['lower'], 0)
        self.assertEqual(result['intervals']['accuracy']['upper'], 1)
        result = metrics.bootstrap(rows, predictions, labels, repeats=1000, comparison=predictions)
        for interval in result['intervals'].values():
            self.assertEqual(interval['lower'], 0)
            self.assertEqual(interval['upper'], 0)
        self.assertEqual(result, metrics.bootstrap(rows, predictions, labels, repeats=1000, comparison=predictions))

    def test_behavior_unknowns_keep_whole_semantic_denominator(self):
        rows, predictions, labels = cells(2)
        ratings = {'synthetic_0_A_I': {'has_substantive_answer': 'yes'},
            'synthetic_0_B_I': {'has_substantive_answer': 'no'}}
        report = metrics.behavior_summary(rows, labels, ratings)
        rate = report['insufficient_substantive_answer']
        self.assertEqual((rate['eligible'], rate['yes'], rate['no'], rate['unknown']), (4, 1, 1, 2))
        self.assertIsNone(rate['point'])
        self.assertEqual((rate['lower'], rate['upper']), (.25, .75))
        self.assertEqual(report['conflict_single_side_selection']['unknown'], 4)

    def test_insufficiency_acknowledgement_while_answering_is_not_refusal(self):
        rows, _, labels = cells(1)
        ratings = {'synthetic_0_A_S': dict(acknowledges_insufficiency='yes', has_substantive_answer='yes'),
            'synthetic_0_B_S': dict(acknowledges_insufficiency='yes', has_substantive_answer='no')}
        rate = metrics.behavior_summary(rows, labels, ratings)['S_erroneous_refusal']
        self.assertEqual((rate['yes'], rate['no'], rate['unknown'], rate['point']), (1, 1, 0, .5))


class StudyTests(unittest.TestCase):
    def test_closed_gate_precedes_probe_model_and_cache_access(self):
        with patch('pickle.load', side_effect=AssertionError('must not deserialize')), \
                patch('pickle.loads', side_effect=AssertionError('must not deserialize')):
            with self.assertRaisesRegex(ValueError, 'Review gate closed'):
                study.execute(Path('/does-not-exist'), [], {}, {'gpu_launch_ready': False}, {}, None)
            with self.assertRaisesRegex(ValueError, 'Review gate closed'):
                study.analyze(Path('/does-not-exist'), [], {}, {'gpu_launch_ready': False}, {}, None)

    def test_real_cli_closed_gate_fails_before_importing_gpu_stack(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'runs') as folder:
            path = Path(folder)
            study.put(path / 'review_gate.json', {'gpu_launch_ready': False})
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/semantic_transfer_study.py'),
                '--stage', 'run', '--run-dir', str(path)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Review gate closed', result.stderr)
            self.assertEqual(set(p.name for p in path.iterdir()), {'review_gate.json'})

    def test_frozen_artifacts_reject_changes_and_verify_never_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'artifact.json'
            with self.assertRaisesRegex(ValueError, 'Missing frozen'):
                study.put(path, {}, write=False)
            self.assertFalse(path.exists())
            study.put(path, {'a': 1})
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'Frozen artifact differs'):
                study.put(path, {'a': 2})
            self.assertEqual(path.read_bytes(), before)

    def fit_fixture(self, path):
        rows, predictions, labels = cells(1)
        records = list(predictions.values())
        for record, row in zip(records, rows):
            record['id'] = row['id']
            record['probe_pred'] = 'answer'
        for i, label in enumerate(metrics.MODES):
            row = dict(id=f'train_A_{i}', original_id='train_fixture', partition='semantic_train',
                expression='A', condition=['S', 'I', 'C'][i])
            rows.append(row)
            labels[row['id']] = label
            relative = f'features/train_{i}.npy'
            (path / 'features').mkdir(exist_ok=True)
            np.save(path / relative, np.full((36, 2048), i + 1, dtype=np.float16))
            records.append(dict(id=row['id'], feature_file=relative))
        rows.append(dict(id='excluded_B', original_id='train_fixture', partition='semantic_train', expression='B', condition='S'))
        labels['excluded_B'] = 'answer'  # Deliberately no B feature: touching it fails the test.
        return rows, labels, records

    def test_single_fixed_fit_excludes_B_and_resume_does_not_refit(self):
        from sklearn.linear_model import LogisticRegression
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            rows, labels, records = self.fit_fixture(path)
            saved, probe = study.optional_fit(path, rows, labels, records)
            self.assertEqual(saved['training_fits'], 1)
            self.assertEqual(probe['layer'], 28)
            self.assertTrue(np.all(probe['scaler'].mean_ == 2))
            self.assertEqual(set(study.read(path / 'fit_decision.json')['training_ids']), {'train_A_0', 'train_A_1', 'train_A_2'})
            with patch.object(LogisticRegression, 'fit', side_effect=AssertionError('second fit forbidden')):
                repeated, _ = study.optional_fit(path, rows, labels, records)
            self.assertEqual(repeated, saved)

    def test_failed_or_interrupted_fit_cannot_silently_retry(self):
        from sklearn.linear_model import LogisticRegression
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            rows, labels, records = self.fit_fixture(path)
            with patch.object(LogisticRegression, 'fit', side_effect=RuntimeError('synthetic fit failure')):
                saved, probe = study.optional_fit(path, rows, labels, records)
            self.assertIsNone(probe)
            self.assertEqual(saved['status'], 'fit_failed_no_retry')
            with patch.object(LogisticRegression, 'fit', side_effect=AssertionError('second fit forbidden')):
                self.assertEqual(study.optional_fit(path, rows, labels, records)[0], saved)
            (path / 'semantic_probe.json').unlink()  # Simulate interruption after attempt marker.
            with self.assertRaisesRegex(ValueError, 'already attempted'):
                study.optional_fit(path, rows, labels, records)

    def test_missing_training_class_is_result_without_fit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            rows, labels, records = self.fit_fixture(path)
            labels['train_A_2'] = None
            saved, probe = study.optional_fit(path, rows, labels, records)
            self.assertEqual(saved['status'], 'not_fit_missing_training_class')
            self.assertEqual(saved['training_fits'], 0)
            self.assertIsNone(probe)
            self.assertFalse((path / 'fit_attempt.json').exists())

    def test_eval_lock_detects_probe_or_label_change(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for name in ['protocol.json', 'approved_labels.json', 'fit_decision.json', 'semantic_probe.json']:
                study.put(path / name, {})
            study.evaluation_lock(path, {})
            study.evaluation_lock(path, {}, write=False)
            (path / 'approved_labels.json').write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, 'Frozen artifact differs'):
                study.evaluation_lock(path, {}, write=False)

    def test_cpu_simulated_resume_and_eval_lock_order_with_strict_cache(self):
        import evidence_experiment as e
        from sklearn.dummy import DummyClassifier
        from sklearn.preprocessing import StandardScaler
        features = np.asarray([[1.] * 2048, [2.] * 2048, [3.] * 2048], dtype=np.float32)
        scaler = StandardScaler().fit(features)
        classifier = DummyClassifier(strategy='prior').fit(features, [0, 1, 2])
        probe = dict(layer=28, scaler=scaler, router=classifier)
        rows, _, labels = cells(3)
        for i, row in enumerate(rows):
            row['partition'] = ['semantic_train', 'semantic_dev', 'semantic_eval'][i // 8]
        class Tokenizer:
            def decode(self, tokens, **kwargs):
                return 'Synthetic answer.'
        tokenizer = Tokenizer()
        old_protocol = study.read(study.PROBE / 'protocol.json')
        protocol = dict(model=old_protocol['model'])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            study.put(path / 'protocol.json', protocol)
            study.put(path / 'approved_labels.json', labels)
            calls = []
            def synthetic_generate(model, tok, row, old, eos):
                if row['partition'] == 'semantic_eval':
                    self.assertTrue((path / 'evaluation_lock.json').is_file())
                    self.assertTrue((path / 'semantic_probe.json').is_file())
                calls.append(row['id'])
                states = np.full((36, 2048), 1 + (row['condition'] in ['I', 'C']), dtype=np.float16)
                record = dict(**{k: row[k] for k in ['id', 'original_id', 'partition', 'expression', 'condition']},
                    prompt_sha256=study.text_hash(row['id']), input_tokens=1,
                    generated_token_ids=[999, eos[0]], generated_tokens=2,
                    raw_output='Synthetic answer.', raw_output_sha256=study.text_hash('Synthetic answer.'),
                    ended_with_eos=True, hit_output_limit=False, **study.predict(old, states))
                return record, states
            with patch('free_answer_study.load_probe', return_value=(probe, 'fixture')), \
                    patch('classification_semantic_baseline.assert_gpu_idle'), \
                    patch.object(e, 'load_model', return_value=object()) as loader, \
                    patch.object(e, 'render_input', side_effect=lambda row, *args: row['id']), \
                    patch.object(e, 'encode', return_value={'input_ids': [7]}), \
                    patch.object(study, 'generate', side_effect=synthetic_generate):
                study.execute(path, rows, labels, {'gpu_launch_ready': True}, protocol, tokenizer)
                self.assertEqual(len(calls), 24)
                self.assertEqual(loader.call_count, 1)
                study.execute(path, rows, labels, {'gpu_launch_ready': True}, protocol, tokenizer)
                self.assertEqual(len(calls), 24)  # No repeated generation/model loading on resume.
                self.assertEqual(loader.call_count, 1)
                records = study.validate_cache(path, rows, tokenizer, probe)
                self.assertEqual(len(records), 24)
                value = study.read(path / 'predictions.json')
                value['records'][0]['probe_probabilities']['answer'] += .1
                (path / 'predictions.json').write_text(study.serialize(value))
                with self.assertRaisesRegex(ValueError, 'probability mismatch'):
                    study.validate_cache(path, rows, tokenizer, probe)
                value['records'][0]['probe_probabilities']['answer'] -= .1
                value['records'][0]['generated_token_ids'] = [True]
                (path / 'predictions.json').write_text(study.serialize(value))
                with self.assertRaisesRegex(ValueError, 'Invalid cached tokens'):
                    study.validate_cache(path, rows, tokenizer, probe)
                # Simulate a crash after the final generation attempt but before checkpoint commit.
                (path / 'predictions.json').write_text(study.serialize(dict(
                    protocol_sha256=study.digest(path / 'protocol.json'), records=records[:-1])))
                with self.assertRaisesRegex(ValueError, 'Uncommitted generation attempt'):
                    study.execute(path, rows, labels, {'gpu_launch_ready': True}, protocol, tokenizer)
                self.assertEqual(len(calls), 24)


class ApprovalTests(unittest.TestCase):
    def fixture(self, path):
        rows, _, labels = cells(30, partition='semantic_train')
        design = dict(partitions=dict(semantic_train=[f'synthetic_{i}' for i in range(30)]))
        mapping = {r['id']: dict(a=f'A{i:03d}', b=f'B{i:03d}') for i, r in enumerate(rows)}
        packets = {side: dict(items=[dict(item_id=mapping[r['id']][side], question=r['question'], documents=r['docs'])
            for r in rows]) for side in ['a', 'b']}
        study.put(path / 'protocol.json', {'synthetic_fixture_only': True})
        approval = dict(status='explicitly_approved_after_context_audit',
            materials_protocol_sha256=study.digest(path / 'protocol.json'), approved_by='synthetic_test_auditor',
            approval_rationale='Synthetic workflow only, no real research judgments.', no_probe_or_generated_outputs_seen=True,
            independence_limit_acknowledged=True, reviews={}, context_audits={},
            labels=[dict(id=r['id'], semantic_label=labels[r['id']]) for r in rows])
        for side in ['a', 'b']:
            packet_path = path / f'review_{side}/packet.json'
            study.put(packet_path, packets[side])
            review_path = path / f'{side}_ratings.json'
            study.put(review_path, dict(reviewer=f'synthetic_{side}', history_exposed=False,
                exposure_description='Synthetic isolated review fixture.', packet_sha256=study.digest(packet_path),
                ratings=[dict(item_id=mapping[r['id']][side], semantic_mode=labels[r['id']], confidence='high',
                    required_facts=['Synthetic premise'], support_chain=['Synthetic support'], missing_facts=['Synthetic missing premise'],
                    conflicting_claims=['Synthetic claim', 'Synthetic incompatible claim'], resolution_basis='',
                    rationale='Synthetic workflow judgment.', citations=[dict(doc_slot=1, quote='Synthetic evidence.')]) for r in rows]))
            context = path / f'{side}_context.txt'
            context.write_text(f'SYNTHETIC complete context fixture {side}; not a research review.')
            approval['reviews'][side] = dict(path=str(review_path), sha256=study.digest(review_path))
            approval['context_audits'][side] = dict(reviewer=f'synthetic_{side}', auditor='synthetic_test_auditor',
                context_id=f'synthetic_context_{side}', audit_rationale='Synthetic test declaration only.',
                received_packet_sha256=study.digest(packet_path), history_exposed=False, author_labels_exposed=False,
                probe_or_outputs_exposed=False, complete_received_context_checked=True,
                full_context_path=str(context), full_context_sha256=study.digest(context))
        return rows, mapping, packets, design, approval

    def test_no_reviews_stay_null_and_explicit_audited_fixture_can_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            rows, mapping, packets, design, approval = self.fixture(path)
            labels, gate, _ = study.approval_labels(path, rows, mapping, packets, design, None)
            self.assertEqual(gate['approved_semantic_labels'], 0)
            self.assertTrue(all(v is None for v in labels.values()))
            self.assertFalse(gate['gpu_launch_ready'])
            approved = path / 'approval.json'
            study.put(approved, approval)
            labels, gate, _ = study.approval_labels(path, rows, mapping, packets, design, approved)
            self.assertTrue(gate['gpu_launch_ready'])
            self.assertEqual(gate['approved_semantic_labels'], 240)

    def test_contamination_missing_receipts_and_unagreed_labels_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            rows, mapping, packets, design, approval = self.fixture(path)
            mutations = [lambda v: v.update(status='consensus_candidates'),
                lambda v: v['context_audits']['a'].update(history_exposed=True),
                lambda v: v['context_audits']['a'].update(complete_received_context_checked=False),
                lambda v: v['context_audits']['a'].update(full_context_sha256='wrong'),
                lambda v: v['context_audits']['b'].update(context_id='synthetic_context_a'),
                lambda v: v['labels'][0].update(semantic_label='conflict'),
                lambda v: v['labels'].append(copy.deepcopy(v['labels'][0]))]
            for mutate in mutations:
                value = copy.deepcopy(approval)
                mutate(value)
                approved = path / 'approval.json'
                approved.write_text(study.serialize(value))
                with self.assertRaises(ValueError):
                    study.approval_labels(path, rows, mapping, packets, design, approved)


if __name__ == '__main__':
    unittest.main()
