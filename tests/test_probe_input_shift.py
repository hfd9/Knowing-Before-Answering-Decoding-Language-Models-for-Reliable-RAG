"""Paired input changes, source reuse, no-generation capture and integrity checks."""

import argparse
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import probe_input_shift as d
from test_controlled_evidence_pilot import Tokenizer, Scaler, Router


class InputShiftTests(unittest.TestCase):
    def test_real_materials_exact_52_factor_cells_20_reusable_sources(self):
        spec, rows, edits = d.build()
        self.assertEqual(len(rows), 52)
        self.assertEqual(sum(r['source'] is not None for r in rows), 20)
        self.assertEqual(len(edits), 12)
        for oid in spec['base_order']:
            group = {(r['question_level'], r['document_level']): r for r in rows if r['original_id'] == oid}
            self.assertEqual(group['O', 'O']['docs'], group['A', 'O']['docs'])
            self.assertEqual(group['O', 'P']['docs'], group['A', 'P']['docs'])
            self.assertEqual(group['A', 'O']['question'], group['A', 'P']['question'])
            if oid in spec['neutral_edits']:
                original = group['A', 'P']['docs']; neutral = group['A', 'N']['docs']
                for edit in [r for r in edits if r['original_id'] == oid]:
                    before = original[edit['doc_slot'] - 1]
                    self.assertEqual(before[edit['start']:edit['end']], edit['before'])
                    self.assertEqual(neutral[edit['doc_slot'] - 1], before[:edit['start']] + before[edit['end']:])
        self.assertEqual(d.build()[1], rows)

    def test_metadata_and_sources_do_not_enter_model_prompt(self):
        row = d.build()[1][0]
        text = d.prompt(row, Tokenizer())
        other = dict(row, id='hidden', source={'SECRET': 'not a prompt'}, document_level='SECRET')
        self.assertEqual(text, d.prompt(other, Tokenizer()))

    def test_real_cached_endpoints_validate_prompts_and_arrays(self):
        from transformers import AutoTokenizer
        model = d.e.read_json(d.p.DEFAULT / 'protocol.json')['model']
        tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=True)
        rows = d.build()[1]
        for row in [r for r in rows if r['source']][:2]:
            self.assertEqual(d.source_state(row, tokenizer, model).shape, (36, 2048))
            corrupted = copy.deepcopy(row); corrupted['question'] += ' altered'
            with self.assertRaisesRegex(ValueError, 'prompt'):
                d.source_state(corrupted, tokenizer, model)
            corrupted = copy.deepcopy(row); corrupted['source']['record']['feature_sha256'] = 'bad'
            with self.assertRaisesRegex(ValueError, 'hash'):
                d.source_state(corrupted, tokenizer, model)

    def test_actual_tiny_cpu_prefill_matches_hf_and_never_calls_lm_head(self):
        import torch
        from transformers import Qwen2Config, Qwen2ForCausalLM
        torch.set_num_threads(1)
        model = Qwen2ForCausalLM(Qwen2Config(vocab_size=32, hidden_size=16, intermediate_size=32,
                    num_hidden_layers=3, num_attention_heads=2, num_key_value_heads=1,
                    max_position_embeddings=128)).eval()
        ids = torch.tensor([[2, 7, 9, 8]])
        with torch.inference_mode():
            reference = model(ids, output_hidden_states=True).hidden_states
        head = model.lm_head.register_forward_pre_hook(lambda *args: self.fail('No logits/generation allowed'))
        try:
            with d.e.LastPromptCapture(model) as capture, torch.inference_mode():
                model.model(ids, use_cache=False, output_hidden_states=False)
            states = capture.array()
            expected = np.stack([h[0, -1].float().numpy() for h in reference[1:]]).astype(np.float16)
            np.testing.assert_allclose(states, expected, rtol=1e-3, atol=1e-3)
            with d.e.LastPromptCapture(model) as other, torch.inference_mode():
                model.model(ids, use_cache=True)
            np.testing.assert_array_equal(states, other.array())
        finally:
            head.remove()

    def test_bridge_rejects_feature_drift_not_semantic_accuracy(self):
        probe = dict(layer=1, scaler=Scaler(), router=Router())
        a = np.ones((3, 16), dtype=np.float16)
        self.assertEqual(d.bridge_error(a, a.copy(), probe)['max_layer_relative_l2'], 0)
        self.assertGreater(d.bridge_error(a * 2, a, probe)['max_layer_relative_l2'], .02)
        for bad in [a * 0, a.astype(np.float32), np.full_like(a, np.nan)]:
            with self.assertRaises(ValueError):
                d.validate_states(bad, [3, 16])

    def test_gpu_busy_aborts_without_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(run_dir=Path(tmp), model='unused', smoke=True)
            row = dict(id='one', source=None)
            with patch.object(d.p.s, 'assert_gpu_idle', side_effect=RuntimeError('GPU busy')), \
                 patch.object(d.e, 'load_model', side_effect=AssertionError('Must not load')):
                with self.assertRaisesRegex(RuntimeError, 'busy'):
                    d.run(args, {}, [row], None, None, {})
            self.assertEqual(d.e.read_json(Path(tmp) / 'last_failure.json')['id'], 'one')

    def test_real_tokenizer_probe_smoke_cache_bridge_replay_and_resume(self):
        model = d.e.read_json(d.p.DEFAULT / 'protocol.json')['model']
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(run_dir=Path(tmp), model=model, smoke=True)
            spec, rows, probe, tokenizer, _ = d.prepare(args)
            records = []
            for row in rows:
                states = d.source_state(row, tokenizer, model) if row['source'] else np.ones((36, 2048), dtype=np.float16)
                relative = f'features/{len(records):04d}.npy'
                d.e.save_array(args.run_dir / relative, states)
                record = {k: row[k] for k in ['id', 'original_id', 'question_level', 'document_level']}
                record.update(origin='new_forward', prompt_sha256=d.e.text_hash(d.prompt(row, tokenizer)),
                              input_tokens=len(d.e.encode(tokenizer, d.prompt(row, tokenizer), 'chat')['input_ids']),
                              capture_phase='decoder_prefill_without_generation', feature_file=relative,
                              feature_sha256=d.m.digest(args.run_dir / relative), **d.prediction(probe, states))
                records.append(record)
            value = dict(protocol_sha256=d.m.digest(args.run_dir / 'protocol.json'), records=records)
            path = args.run_dir / 'states.json'; d.e.repro.write_json(path, value)
            self.assertEqual(len(d.cache(args, rows, probe, tokenizer)), 6)
            gate = d.smoke_gate(args, spec, rows, records, probe, tokenizer)
            self.assertEqual(gate['status'], 'technical_smoke_passed')
            self.assertEqual(len(gate['bridges']), 2)
            self.assertFalse(gate['semantic_accuracy_gate'])
            with patch.object(d.e, 'load_model', side_effect=AssertionError('Completed resume must not load model')):
                self.assertEqual(len(d.run(args, spec, rows, probe, tokenizer, {})), 6)
            d.prepare(args, write=False)
            for field, bad_value in [('probe_pred', 'INVALID'), ('input_tokens', -1),
                                     ('origin', 'reused_endpoint'), ('capture_phase', 'generated')]:
                bad = copy.deepcopy(value); bad['records'][0][field] = bad_value
                d.e.repro.write_json(path, bad)
                with self.subTest(field=field), self.assertRaises(ValueError):
                    d.cache(args, rows, probe, tokenizer)
            d.e.repro.write_json(path, value)
            bad = copy.deepcopy(records)
            source_index = next(i for i, r in enumerate(rows) if r['source'])
            feature_path = args.run_dir / bad[source_index]['feature_file']
            h = np.load(feature_path); d.e.save_array(feature_path, h * 2)
            bad[source_index]['feature_sha256'] = d.m.digest(feature_path)
            with self.assertRaisesRegex(ValueError, 'bridge failed'):
                d.smoke_gate(args, spec, rows, bad, probe, tokenizer)
            before = (args.run_dir / 'materials/inputs.json').read_bytes()
            (args.run_dir / 'materials/inputs.json').write_text('[]')
            with self.assertRaisesRegex(ValueError, 'artifact differs'):
                d.prepare(args, write=False)
            (args.run_dir / 'materials/inputs.json').write_bytes(before)

    def test_report_pairs_keep_original_vs_pilot_bundle_distinct_and_no_accuracy(self):
        rows = d.build()[1]
        records = [dict(r, input_tokens=100, origin='reused_endpoint' if r['source'] else 'new_forward',
                        probe_pred='conflict', probe_probabilities=dict(answer=.1, refuse=.1, conflict=.8)) for r in rows]
        result = d.report(rows, records)
        self.assertEqual(result['new_forwards'], 32)
        self.assertEqual(result['reused_endpoints'], 20)
        self.assertEqual(result['contrasts']['remove_negatives_adapted_question']['n_pairs'], 6)
        self.assertEqual(result['contrasts']['question_on_original_docs']['n_pairs'], 10)
        self.assertEqual(result['generated_answers'], 0)
        self.assertNotIn('accuracy', result)
        with self.assertRaises(ValueError):
            d.report(rows, records[:-1])

    def test_launcher_does_not_start_formal_after_smoke_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = Path(tmp) / 'scripts'; scripts.mkdir()
            launcher = scripts / 'run_probe_input_shift_review.sh'
            launcher.write_bytes((ROOT / 'scripts' / launcher.name).read_bytes())
            (scripts / 'run_probe_input_shift.sh').write_text('#!/bin/sh\nexit 9\n')
            result = subprocess.run(['sh', str(launcher)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse((Path(tmp) / 'runs/qwen2.5-3b-probe-input-shift-v1/launch/full.log').exists())


if __name__ == '__main__':
    unittest.main()
