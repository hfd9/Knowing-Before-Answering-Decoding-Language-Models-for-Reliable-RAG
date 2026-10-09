"""Verify invalid-output accounting, paired comparisons and resume integrity."""

import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prompt_baseline as baseline


class PromptBaselineTests(unittest.TestCase):
    def rows(self):
        return [{"id": "q1_" + mode, "original_id": "q1", "question": "When?",
                 "docs": ["Evidence {literal}: 1998"] * 5, "true_mode": mode,
                 "label": label} for label, mode in enumerate(baseline.MODES)]

    def records(self, rows, raw_outputs):
        return [{"id": row["id"], "original_id": row["original_id"],
                 "true_mode": row["true_mode"], "raw_output": raw,
                 "pred_mode": baseline.parse_label(raw), "elapsed_seconds": 1.0,
                 "peak_allocated_gib": 1.0, "hit_output_limit": False,
                 "prompt_sha256": hashlib.sha256(baseline.render_label_prompt(row).encode()).hexdigest()}
                for row, raw in zip(rows, raw_outputs)]

    def test_parser_does_not_guess_from_prose_or_multiple_labels(self):
        for text, expected in [(" ANSWER.\n", "answer"), ("refuse", "refuse"), ("Conflict!", "conflict"),
                               ("", None), ("answer or conflict", None), ("The answer is refuse.", None),
                               ('{"label":"answer"}', None), ("conflicting", None)]:
            self.assertEqual(baseline.parse_label(text), expected)

    def test_prompt_keeps_full_evidence_and_does_not_include_gold_labels(self):
        row = self.rows()[0]
        row["docs"][-1] = "long " * 8000 + "Late fact {year}: 1998"
        row["gold_answer"] = "DO_NOT_LEAK_GOLD"
        prompt = baseline.render_label_prompt(row)
        self.assertTrue(prompt.endswith("Question: When?\nLabel:"))
        self.assertIn(row["docs"][-1], prompt)
        self.assertNotIn(row["gold_answer"], prompt)
        altered = dict(row, true_mode="refuse", label=1)
        self.assertEqual(prompt, baseline.render_label_prompt(altered))
        self.assertLess(prompt.index("[Document 1]"), prompt.index("[Document 5]"))

    def test_invalid_is_wrong_with_full_denominators(self):
        rows = self.rows()
        records = self.records(rows, ["answer", "Cannot tell", "answer"])
        metrics = baseline.evaluate(rows, records)
        self.assertAlmostEqual(metrics["accuracy"], 1 / 3)
        self.assertAlmostEqual(metrics["macro_f1"], 2 / 9)
        self.assertEqual(metrics["far"], 0.5)
        self.assertEqual(metrics["invalid_count"], 1)
        self.assertEqual(metrics["unsupported_invalid_count"], 1)
        self.assertEqual(metrics["confusion_matrix"], [[1, 0, 0, 0], [0, 0, 0, 1], [1, 0, 0, 0]])

    def test_resume_rejects_settings_reordering_and_tampering(self):
        rows = self.rows()
        records = self.records(rows, ["answer", "refuse"])
        spec = {"instruction": "v1"}
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            baseline.write_json(run / "predictions.json", {"spec": spec, "records": records})
            self.assertEqual(baseline.load_checkpoint(run, spec, rows), records)
            with self.assertRaisesRegex(ValueError, "settings changed"):
                baseline.load_checkpoint(run, {"instruction": "v2"}, rows)
            with self.assertRaisesRegex(ValueError, "ordering mismatch"):
                baseline.load_checkpoint(run, spec, rows[::-1])
            records[0]["pred_mode"] = "refuse"
            baseline.write_json(run / "predictions.json", {"spec": spec, "records": records})
            with self.assertRaisesRegex(ValueError, "raw output"):
                baseline.load_checkpoint(run, spec, rows)

    def test_analysis_pairs_by_id_and_refuses_incomplete_results(self):
        rows = self.rows()
        records = self.records(rows, ["answer", "refuse", "conflict"])
        spec = {"instruction": "v1"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = root / "baseline"
            ref = root / "reference"
            args = argparse.Namespace(run_dir=run, reference_run=ref, split="test")
            (ref / "data").mkdir(parents=True)
            (ref / "data" / "instances_test.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            router = [{"id": row["id"], "true_mode": row["true_mode"], "pred_mode": "answer"} for row in rows]
            baseline.write_json(ref / "results" / "router_test_predictions.json", router)
            baseline.write_json(run / "predictions.json", {"spec": spec, "records": records[:2]})
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                baseline.analyze(args, rows, spec)
            baseline.write_json(run / "predictions.json", {"spec": spec, "records": records})
            with redirect_stdout(io.StringIO()):
                baseline.analyze(args, rows, spec)
            result = json.loads((run / "comparison.json").read_text())
            self.assertEqual(result["paired_outcomes"]["baseline_only_correct"], 2)
            self.assertAlmostEqual(result["paired_accuracy"]["difference"], 2 / 3)
            self.assertEqual(result["baseline"]["accuracy"], 1.0)
            self.assertTrue((run / "comparison.md").is_file())
            baseline.write_json(ref / "results" / "router_test_predictions.json", router[::-1])
            with self.assertRaisesRegex(ValueError, "ordering mismatch"):
                baseline.analyze(args, rows, spec)

    def test_interrupted_generation_resumes_without_repeating_saved_instances(self):
        import torch

        class Batch(dict):
            @property
            def input_ids(self):
                return self["input_ids"]

            def to(self, device):
                return self

        class Tokenizer:
            eos_token_id = 2
            pad_token_id = 0

            def __call__(self, prompt, **kwargs):
                return Batch(input_ids=torch.tensor([[1, 3]]), attention_mask=torch.ones(1, 2))

            def decode(self, ids, **kwargs):
                return {10: "answer", 11: "refuse", 12: "conflict"}[int(ids[0])]

        class Model:
            generation_config = SimpleNamespace(eos_token_id=2, bos_token_id=1)

            def __init__(self, tokens):
                self.tokens = iter(tokens)
                self.calls = 0

            def eval(self):
                return self

            def requires_grad_(self, flag):
                pass

            def generate(self, **kwargs):
                self.calls += 1
                if kwargs["logits_to_keep"] != 1 or kwargs["generation_config"].do_sample:
                    raise AssertionError("Unexpected generation options")
                token = next(self.tokens)
                if isinstance(token, Exception):
                    raise token
                return torch.tensor([[1, 3, token, 2]])

        rows = self.rows()
        spec = {"instruction": "v1"}
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(run_dir=Path(tmp), model="unused", max_new_tokens=8)
            first, resumed = Model([10, RuntimeError("simulated interruption")]), Model([11, 12])
            with patch("torch.cuda.is_available", return_value=True), \
                 patch("torch.cuda.reset_peak_memory_stats"), patch("torch.cuda.synchronize"), \
                 patch("torch.cuda.max_memory_allocated", return_value=1024), patch("torch.cuda.empty_cache"), \
                 patch("transformers.AutoModelForCausalLM.from_pretrained", side_effect=[first, resumed]) as load, \
                 redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "completed predictions are saved"):
                    baseline.infer(args, rows, spec, Tokenizer())
                self.assertEqual(len(baseline.load_checkpoint(args.run_dir, spec, rows)), 1)
                result = baseline.infer(args, rows, spec, Tokenizer())
                self.assertEqual([r["pred_mode"] for r in result], baseline.MODES)
                self.assertEqual(resumed.calls, 2)
                baseline.infer(args, rows, spec, Tokenizer())
                self.assertEqual(load.call_count, 2)

    def test_cpu_qwen_generation_accepts_memory_saving_options(self):
        import torch
        from transformers import GenerationConfig, Qwen2Config, Qwen2ForCausalLM

        # A tiny random CPU model tests the actual generation API, not benchmark accuracy.
        config = Qwen2Config(vocab_size=32, hidden_size=16, intermediate_size=32,
                             num_hidden_layers=1, num_attention_heads=2,
                             num_key_value_heads=1, max_position_embeddings=128,
                             bos_token_id=1, eos_token_id=2, pad_token_id=0)
        config._attn_implementation = "sdpa"
        model = Qwen2ForCausalLM(config).eval()
        with torch.inference_mode():
            generated = model.generate(input_ids=torch.tensor([[1, 3, 4]]),
                                       attention_mask=torch.ones(1, 3, dtype=torch.long),
                                       generation_config=GenerationConfig(max_new_tokens=2, do_sample=False,
                                                                          num_beams=1, use_cache=True,
                                                                          eos_token_id=2, pad_token_id=0,
                                                                          bos_token_id=1),
                                       logits_to_keep=1)
        self.assertGreater(generated.shape[1], 3)
        self.assertLessEqual(generated.shape[1], 5)


if __name__ == "__main__":
    unittest.main()
