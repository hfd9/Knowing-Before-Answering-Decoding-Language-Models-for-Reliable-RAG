"""Matched rendering, prompt-state timing, grouped metrics and blind review integrity."""

import argparse
from contextlib import redirect_stdout
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import evidence_experiment as e
import classification_grid as grid
import free_answer_review as review
import free_answer_study as free


class EvidenceExperimentTests(unittest.TestCase):
    def rows(self, split='test'):
        return [{'id': f'{split}_1_{mode}', 'original_id': f'{split}_1', 'split': split,
                 'true_mode': mode, 'label': i, 'question': 'When?', 'gold_answer': 'DO_NOT_LEAK_GOLD',
                 'docs': ['Evidence {braces}: 1998'] * 5} for i, mode in enumerate(e.MODES)]

    def records(self, rows, outputs):
        return [dict(id=r['id'], original_id=r['original_id'], true_mode=r['true_mode'], raw_output=text,
                     pred_mode=e.first_line_label(text), strict_format_pass=e.legacy.parse_label(text) is not None,
                     hit_output_limit=False, elapsed_seconds=1.0,
                     prompt_sha256=e.text_hash(e.render_input(r, 'classification', 'plain')))
                for r, text in zip(rows, outputs)]

    def test_plain_classification_is_identical_to_historical_prompt(self):
        row = self.rows()[0]
        row['docs'][-1] += ' late evidence ' * 6000
        self.assertEqual(e.render_input(row, 'classification', 'plain'), e.legacy.render_label_prompt(row))
        for task in ['classification', 'free_answer']:
            text = e.render_input(row, task, 'plain')
            self.assertIn(row['docs'][-1], text)
            self.assertNotIn(row['gold_answer'], text)
            changed = dict(row, label=1, true_mode='refuse')
            self.assertEqual(text, e.render_input(changed, task, 'plain'))

    def test_chat_tokens_match_native_template_without_added_special_tokens(self):
        from tokenizers import Tokenizer, models, pre_tokenizers
        from transformers import PreTrainedTokenizerFast
        backend = Tokenizer(models.WordLevel({'[UNK]': 0, '[EOS]': 1, 'system': 2, 'user': 3, 'assistant': 4}, unk_token='[UNK]'))
        backend.pre_tokenizer = pre_tokenizers.Whitespace()
        tokenizer = PreTrainedTokenizerFast(tokenizer_object=backend, unk_token='[UNK]', eos_token='[EOS]')
        tokenizer.chat_template = "{% for message in messages %}{{ message['role'] + '\n' + message['content'] + '\n' }}{% endfor %}{% if add_generation_prompt %}assistant\n{% endif %}"
        row = self.rows()[0]
        text = e.render_input(row, 'classification', 'chat', tokenizer)
        self.assertTrue(text.endswith('assistant\n'))
        body = e.render_prompt('P0', row['question'], row['docs'], instruction='')[:-len('Answer:')] + 'Label:'
        expected = tokenizer.apply_chat_template([{'role': 'system', 'content': e.legacy.INSTRUCTION},
                                                  {'role': 'user', 'content': body}], tokenize=True, add_generation_prompt=True)
        self.assertEqual(e.encode(tokenizer, text, 'chat')['input_ids'], expected)
        self.assertEqual(text.count(e.legacy.INSTRUCTION), 1)

    def test_per_class_invalid_denominators_and_separate_false_answers(self):
        rows = self.rows()
        records = self.records(rows, ['answer', 'answer', 'conflict\nExplanation'])
        m = e.classification_metrics(rows, records)
        self.assertEqual(m['refuse_to_answer_count'], 1)
        self.assertEqual(m['conflict_to_answer_count'], 0)
        self.assertEqual(m['classification_false_answer_rate'], 0.5)
        self.assertEqual(m['per_class']['answer']['precision'], 0.5)
        self.assertEqual(m['per_class']['conflict']['recall'], 1.0)
        records[2]['pred_mode'] = None
        m = e.classification_metrics(rows, records)
        self.assertEqual(m['per_class']['conflict']['support'], 1)
        self.assertEqual(m['per_class']['conflict']['f1'], 0)
        self.assertEqual(m['accuracy'], 1 / 3)

    def test_bootstrap_retains_all_three_instances_per_question(self):
        rows = self.rows()
        left = self.records(rows, ['answer', 'refuse', 'conflict'])
        right = self.records(rows, ['answer', 'answer', 'answer'])
        result = e.bootstrap_pair(rows, left, right, resamples=1000)
        accuracy = result['differences']['accuracy']
        self.assertAlmostEqual(accuracy['estimate'], 2 / 3)
        self.assertTrue(np.allclose(accuracy['95ci'], [2 / 3, 2 / 3]))
        self.assertEqual(result['differences']['refuse_recall']['estimate'], 1.0)

    def test_capture_matches_hidden_states_and_runs_before_first_token_logits(self):
        import torch
        from transformers import BatchEncoding, Qwen2Config, Qwen2ForCausalLM
        config = Qwen2Config(vocab_size=32, hidden_size=16, intermediate_size=32,
                             num_hidden_layers=3, num_attention_heads=2, num_key_value_heads=1,
                             max_position_embeddings=128, bos_token_id=1, eos_token_id=2, pad_token_id=0)
        config._attn_implementation = 'sdpa'
        model = Qwen2ForCausalLM(config).eval()
        inputs = {'input_ids': torch.tensor([[1, 3, 4]]), 'attention_mask': torch.ones(1, 3, dtype=torch.long)}
        with torch.inference_mode():
            output = model.model(**inputs, output_hidden_states=True, use_cache=False)
            expected = np.stack([state[0, -1].numpy() for state in output.hidden_states[1:]]).astype(np.float16)
        with e.LastPromptCapture(model) as capture, torch.inference_mode():
            model.model(**inputs, use_cache=False)
        self.assertTrue(np.array_equal(capture.array(), expected))

        class Tokenizer:
            eos_token_id, pad_token_id = 2, 0
            def __call__(self, text, **kwargs):
                return BatchEncoding(inputs.copy())
            def decode(self, ids, **kwargs):
                return 'A concrete answer'
        events, prefills = [], []
        handle = model.lm_head.register_forward_pre_hook(lambda *args: events.append('logits'))
        try:
            def on_prefill(h):
                events.append('probe'); prefills.append(h)
            with patch('torch.cuda.reset_peak_memory_stats'), patch('torch.cuda.synchronize'), \
                 patch('torch.cuda.max_memory_allocated', return_value=0):
                _, generated_features = e.generate_one(model, Tokenizer(), self.rows()[0], 'free_answer', 'plain', 3,
                                                         capture=True, on_prefill=on_prefill)
            self.assertEqual(events[0], 'probe')
            self.assertEqual(events.count('probe'), 1)
            self.assertEqual(len(prefills), 1)
            self.assertTrue(np.allclose(generated_features, expected, atol=0.002))
        finally:
            handle.remove()

    def test_feature_resume_rejects_corruption(self):
        row = self.rows()[0]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'states.json'
            state = Path(tmp) / 'state.npy'
            e.save_array(state, np.ones((2, 4), dtype=np.float16))
            record = dict(id=row['id'], true_mode=row['true_mode'], feature_file='state.npy',
                          feature_sha256=e.repro.digest_file(state),
                          prompt_sha256=e.text_hash(e.render_input(row, 'free_answer', 'plain')))
            spec = {'task': 'test'}
            e.repro.write_json(path, {'spec': spec, 'records': [record]})
            e.load_records(path, spec, [row], 'free_answer', 'plain', None, [2, 4])
            e.save_array(state, np.zeros((2, 4), dtype=np.float16))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                e.load_records(path, spec, [row], 'free_answer', 'plain', None, [2, 4])

    def test_grid_report_contains_four_conditions_and_class_diagnostics(self):
        rows = self.rows()
        router = self.records(rows, ['answer', 'refuse', 'conflict'])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / 'legacy.json'
            legacy.write_text('{}')
            args = argparse.Namespace(run_dir=root, reference_run=root, conditions=list(grid.CONDITIONS),
                                      splits=['test'], legacy_predictions=legacy)
            for name, (fmt, _) in grid.CONDITIONS.items():
                records = self.records(rows, ['answer\nExplanation', 'refuse', 'conflict'])
                for row, record in zip(rows, records):
                    record['prompt_sha256'] = e.text_hash(e.render_input(row, 'classification', fmt, FakeChatTokenizer()))
                e.repro.write_json(root / name / 'test/predictions.json',
                                  {'spec': grid.condition_spec('protocol', name, 'test', legacy), 'records': records})
            with patch.object(grid, 'reference_router', return_value=router), redirect_stdout(io.StringIO()):
                grid.analyze(args, {'test': rows}, 'protocol', FakeChatTokenizer())
            report = e.read_json(root / 'reports/test.json')
            self.assertEqual(set(report['methods']), {'router', *grid.CONDITIONS})
            self.assertEqual(report['methods']['plain8']['accuracy'], 1.0)
            self.assertAlmostEqual(report['methods']['chat64']['strict_format_pass_rate'], 2 / 3)
            self.assertIn('chat64_minus_plain64', report['paired_question_bootstrap'])
            self.assertTrue((root / 'reports/test_per_class.csv').exists())

    def test_behavior_denominators_keep_unknown_and_disclaimed_answers(self):
        records = [dict(id=f'r{i}', original_id=f'q{i}', true_mode='refuse', probe_pred=probe, behavior=behavior)
                   for i, (probe, behavior) in enumerate([
                       ('refuse', {'has_substantive_answer': True, 'acknowledges_insufficiency': True}),
                       ('refuse', {'has_substantive_answer': None}),
                       ('answer', {'has_substantive_answer': False})])]
        result = review.behavior_summary(records)['rates']
        conditional = result['refuse_probe_refuse_then_answer_rate']
        self.assertEqual(conditional['denominator'], 2)
        self.assertEqual(conditional['known_positive'], 1)
        self.assertIsNone(conditional['rate'])
        self.assertEqual([conditional['lower_bound'], conditional['upper_bound']], [0.5, 1])
        share = result['refuse_recognized_then_answer_share_of_all_refuse']
        self.assertEqual(share['denominator'], 3)
        self.assertEqual([share['lower_bound'], share['upper_bound']], [1 / 3, 2 / 3])

    def test_blind_review_hides_labels_and_rejects_other_batches(self):
        rows = self.rows()
        records = self.records(rows, ['answer', 'refuse', '</script><script>unsafe</script>'])
        for r in records:
            r['probe_pred'] = 'PROBE_SECRET'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = review.export_review(root, {r['id']: r for r in rows}, {'plain': records})
            page = (root / 'review/blind_review.html').read_text()
            self.assertNotIn('PROBE_SECRET', page)
            self.assertNotIn(rows[0]['id'], page)
            self.assertNotIn('</script><script>unsafe', page)
            path = root / 'review/annotations_template.csv'
            digest = e.repro.digest_file(root / 'review/manifest.json')
            annotations = review.load_annotations(path, manifest, digest)
            self.assertEqual(len(annotations), 3)
            with path.open(newline='') as f:
                reader = csv.DictReader(f); fields = reader.fieldnames; entries = list(reader)
            entries[0]['review_manifest_sha256'] = 'different-batch'
            with path.open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(entries)
            with self.assertRaisesRegex(ValueError, 'different output batch'):
                review.load_annotations(path, manifest, digest)

    def test_matched_free_probe_and_review_pipeline_with_synthetic_states(self):
        """Exercise real fitting, validated resume and unknown/complete behavior reports."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / 'model'
            e.repro.write_json(model / 'config.json', {'num_hidden_layers': 2, 'hidden_size': 4})
            args = argparse.Namespace(run_dir=root, model=str(model), formats=['plain', 'chat'],
                                      annotations=root / 'annotations.csv')
            rows = {}
            for split in ['train', 'val', 'test']:
                rows[split] = [dict(row, id=f'{split}_{group}_{row["true_mode"]}', original_id=f'{split}_{group}')
                               for group in range(3) for row in self.rows(split)]
            tokenizer = FakeChatTokenizer()

            def features(row):
                vector = np.eye(4, dtype=np.float16)[row['label']] + np.float16(0.1)
                return np.stack([vector, vector])

            for fmt in args.formats:
                for split in ['train', 'val']:
                    path = root / fmt / split / 'states.json'
                    records = [dict(id=row['id'], true_mode=row['true_mode'],
                                    prompt_sha256=e.text_hash(e.render_input(row, 'free_answer', fmt, tokenizer)),
                                    **free.save_feature(path.parent, index, features(row)))
                               for index, row in enumerate(rows[split])]
                    e.repro.write_json(path, {'spec': free.checkpoint_spec('p', fmt, split, 'extract'), 'records': records})
            with redirect_stdout(io.StringIO()):
                free.train_probes(args, rows, 'p', tokenizer)
            for fmt in args.formats:
                path, spec, _, probe = free.generation_records(args, rows['test'], fmt, 'p', tokenizer)
                self.assertEqual(probe['layer'], 0)  # First validation maximum, no test selection.
                records = []
                for index, row in enumerate(rows['test']):
                    h = features(row)
                    probability = probe['router'].predict_proba(probe['scaler'].transform(h[0][None].astype(np.float32)))[0]
                    records.append(dict(id=row['id'], original_id=row['original_id'], true_mode=row['true_mode'],
                                        raw_output='1998', hit_output_limit=False,
                                        prompt_sha256=e.text_hash(e.render_input(row, 'free_answer', fmt, tokenizer)),
                                        probe_pred=e.MODES[int(probe['router'].classes_[np.argmax(probability)])],
                                        probe_probabilities={e.MODES[int(c)]: float(p) for c, p in zip(probe['router'].classes_, probability)},
                                        probe_layer_zero_based=0, probe_decision_pre_first_token=True,
                                        **free.save_feature(path.parent, index, h)))
                e.repro.write_json(path, {'spec': spec, 'records': records})
            with redirect_stdout(io.StringIO()):
                free.analyze(args, rows['test'], 'p', tokenizer)
            report = e.read_json(root / 'reports/behavior.json')
            for fmt in args.formats:
                self.assertIsNone(report['formats'][fmt]['behavior']['rates']['all_refuse_substantive_answer_rate']['rate'])
            template = root / 'review/annotations_template.csv'
            with template.open(newline='') as f:
                reader = csv.DictReader(f); fields = reader.fieldnames; annotations = list(reader)
            for record in annotations:
                record.update(dict.fromkeys(review.FIELDS, 'no'))
                record.update(has_substantive_answer='yes', selects_single_answer='yes', reviewer='synthetic-test')
            with args.annotations.open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(annotations)
            with redirect_stdout(io.StringIO()):
                free.analyze(args, rows['test'], 'p', tokenizer)
            report = e.read_json(root / 'reports/behavior.json')
            for fmt in args.formats:
                summary = report['formats'][fmt]
                self.assertEqual(summary['review_status'], 'complete')
                rate = summary['behavior']['rates']['refuse_probe_refuse_then_answer_rate']
                self.assertEqual(rate['known_positive'], 3)
                self.assertEqual(rate['denominator'], 3)
                self.assertEqual(rate['rate'], 1.0)
            self.assertEqual(report['paired_behavior_differences']['refuse_has_substantive_answer_chat_minus_plain']['estimate'], 0)


class FakeChatTokenizer:
    def apply_chat_template(self, messages, **kwargs):
        return '\n'.join(m['role'] + ':' + m['content'] for m in messages) + '\nassistant:'


if __name__ == '__main__':
    unittest.main()
