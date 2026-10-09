"""Check evidence preservation, question grouping and cache integrity."""

import argparse
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import small_repro as repro
from prompts import render_prompt


class SmallReproTests(unittest.TestCase):
    def test_prompt_preserves_late_evidence_and_literal_braces(self):
        doc = "irrelevant " * 500 + "金标准 {answer}: 1998"
        prompt = render_prompt("P0", "When?", [doc])
        self.assertIn(doc, prompt)
        self.assertTrue(prompt.endswith("Question: When?\nAnswer:"))
        self.assertLess(render_prompt("P4", "When?", [doc]).index("Question: When?"),
                        render_prompt("P4", "When?", [doc]).index("[Document 1]"))
        self.assertIn("<doc id=\"1\">" + doc + "</doc>", render_prompt("P5", "When?", [doc]))

    def make_data(self, root):
        archive = root / "dataset" / "instances.zip"
        archive.parent.mkdir()
        with zipfile.ZipFile(archive, "w") as z:
            for split in repro.SPLITS:
                rows = []
                for question in range(3):
                    for mode in repro.MODES:
                        rid = f"{split}_{question}"
                        rows.append({"id": rid + "_" + mode, "original_id": rid,
                                     "question": f"Question {rid}?", "gold_answer": "1998",
                                     "true_mode": mode, "label": repro.LABEL_MAP[mode], "split": split,
                                     "docs": ["evidence"] * 5, "retriever_scores": [1.0] * 5})
                z.writestr(f"instances_{split}.jsonl", "".join(json.dumps(r) + "\n" for r in rows))
        args = argparse.Namespace(train_questions=2, val_questions=2, test_questions=2,
                                  seed=42, model=str(root / "model"), template="P0")
        return args

    def test_sampling_keeps_triplets_and_refuses_changed_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.make_data(root)
            with patch.object(repro, "PROJECT", root):
                manifest = repro.prepare(args, root / "run")
                self.assertEqual(manifest, repro.prepare(args, root / "run"))
                ids = []
                for split in repro.SPLITS:
                    rows = repro.load_rows(root / "run" / "data" / f"instances_{split}.jsonl")
                    self.assertEqual(len(rows), 6)
                    self.assertEqual(manifest["splits"][split]["class_counts"], dict.fromkeys(repro.MODES, 2))
                    for original_id in {r["original_id"] for r in rows}:
                        self.assertEqual({r["true_mode"] for r in rows if r["original_id"] == original_id}, set(repro.MODES))
                    ids.append({r["original_id"] for r in rows})
                self.assertFalse(ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2])
                args.seed += 1
                with self.assertRaisesRegex(ValueError, "Sampling settings changed"):
                    repro.prepare(args, root / "run")

    def test_cache_rejects_reordered_labels_and_changed_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.make_data(root)
            model = root / "model"
            model.mkdir()
            for name in ["config.json", "tokenizer.json", "tokenizer_config.json"]:
                (model / name).write_text("{}")
            (model / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {"weight": "model-1.safetensors"}}))
            (model / "model-1.safetensors").write_bytes(b"test weights fingerprint")
            (root / "code").mkdir()
            (root / "code" / "prompts.py").write_text("test renderer fingerprint")
            run = root / "run"
            with patch.object(repro, "PROJECT", root):
                repro.prepare(args, run)
                data_path = run / "data" / "instances_train.jsonl"
                rows = repro.load_rows(data_path)
                hidden_path, labels_path, meta_path = repro.feature_paths(args, run, "train")
                hidden_path.parent.mkdir()
                hidden = np.ones((6, 2, 4), dtype=np.float16)
                np.save(hidden_path, hidden)
                labels = np.asarray([r["label"] for r in rows])
                np.save(labels_path, labels)
                repro.write_json(meta_path, {"spec": repro.feature_spec(args, rows, data_path), "shape": list(hidden.shape)})
                repro.load_features(args, run, "train")
                np.save(labels_path, labels[::-1])
                with self.assertRaisesRegex(ValueError, "ordering mismatch"):
                    repro.load_features(args, run, "train")
                np.save(labels_path, labels)
                (model / "config.json").write_text('{"changed": true}')
                with self.assertRaisesRegex(ValueError, "do not match"):
                    repro.load_features(args, run, "train")


if __name__ == "__main__":
    unittest.main()
