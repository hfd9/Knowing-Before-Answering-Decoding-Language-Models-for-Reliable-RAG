"""Question-grouped, offline reproduction of the hidden-state router.

Stages: prepare -> extract -> probe -> router. Defaults: 600/285/300 rows.
Every original question retains its answer/refuse/conflict instances.
The LM is frozen; only linear probes and their calibrator are trained.
"""

import argparse
import hashlib
import json
import os
import pickle
import random
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "code"))
from prompts import TEMPLATE_PATH, render_prompt

MODES = ["answer", "refuse", "conflict"]
LABEL_MAP = {mode: idx for idx, mode in enumerate(MODES)}
SPLITS = ["train", "val", "test"]
RENDER_POLICY = "plain_json_templates_full_docs_v1"


def digest_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def prepare(args, run):
    archive = PROJECT / "dataset" / "instances.zip"
    counts = dict(zip(SPLITS, [args.train_questions, args.val_questions, args.test_questions]))
    spec = {"seed": args.seed, "questions": counts, "source_sha256": digest_file(archive)}
    manifest_path = run / "data" / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["sampling"] != spec:
            raise ValueError("Sampling settings changed. Use a new --run_dir to keep experiments separate.")
        for split in SPLITS:
            if digest_file(run / "data" / f"instances_{split}.jsonl") != manifest["splits"][split]["sha256"]:
                raise ValueError(f"Prepared {split} data was modified. Use a new --run_dir.")
        print("Prepared data matches the manifest; reusing it.", flush=True)
        return manifest

    manifest = {"sampling": spec, "splits": {}}
    question_sets = {}
    id_sets = {}
    with zipfile.ZipFile(archive) as z:
        for split in SPLITS:
            rows = [json.loads(line) for line in z.read(f"instances_{split}.jsonl").decode().splitlines() if line.strip()]
            grouped = defaultdict(list)
            for row in rows:
                if row["label"] != LABEL_MAP[row["true_mode"]] or row["split"] != split:
                    raise ValueError(f"Invalid label/split: {row['id']}")
                if len(row["docs"]) != 5 or len(row["retriever_scores"]) != 5:
                    raise ValueError(f"Invalid document/score count: {row['id']}")
                grouped[row["original_id"]].append(row)
            for original_id, group in grouped.items():
                if sorted(row["true_mode"] for row in group) != sorted(MODES):
                    raise ValueError(f"Incomplete evidence triplet: {original_id}")
                if len({row["question"] for row in group}) != 1:
                    raise ValueError(f"Mismatched question in triplet: {original_id}")
            count = counts[split]
            if not 1 <= count <= len(grouped):
                raise ValueError(f"{split}: choose 1..{len(grouped)} questions, got {count}")
            selected_ids = set(random.Random(args.seed).sample(sorted(grouped), count))
            selected = [row for row in rows if row["original_id"] in selected_ids]
            id_sets[split] = selected_ids
            question_sets[split] = {row["question"] for row in selected}
            out = run / "data" / f"instances_{split}.jsonl"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected), encoding="utf-8")
            manifest["splits"][split] = {
                "n_questions": count, "n_instances": len(selected),
                "class_counts": dict(Counter(row["true_mode"] for row in selected)),
                "original_ids": sorted(selected_ids), "sha256": digest_file(out),
            }
            print(f"{split}: {count} questions, {len(selected)} instances", flush=True)
    for i, left in enumerate(SPLITS):
        for right in SPLITS[i + 1:]:
            if id_sets[left] & id_sets[right] or question_sets[left] & question_sets[right]:
                raise ValueError(f"Question leakage between {left} and {right}")
    write_json(manifest_path, manifest)
    return manifest


def feature_spec(args, rows, data_path):
    model_path = Path(args.model).resolve()
    config = model_path / "config.json"
    index = model_path / "model.safetensors.index.json"
    if not config.is_file() or not index.is_file():
        raise ValueError(f"Expected a complete local sharded HF model: {model_path}")
    files = [config, index, model_path / "tokenizer.json", model_path / "tokenizer_config.json"]
    shards = sorted(set(json.loads(index.read_text())["weight_map"].values()))
    weights = []
    for shard in shards:
        path = model_path / shard
        stat = path.stat()
        weights.append({"file": shard, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
    return {
        "model": str(model_path), "model_files": {p.name: digest_file(p) for p in files},
        "weights": weights, "template": args.template,
        "template_sha256": digest_file(TEMPLATE_PATH), "renderer_sha256": digest_file(PROJECT / "code" / "prompts.py"),
        "render_policy": RENDER_POLICY, "data_sha256": digest_file(data_path),
        "ids": [row["id"] for row in rows], "labels": [row["label"] for row in rows],
    }


def feature_paths(args, run, split):
    directory = run / "activations"
    tag = f"{args.template}_{split}"
    return directory / f"H_{tag}.npy", directory / f"y_{tag}.npy", directory / f"meta_{tag}.json"


def load_features(args, run, split):
    data_path = run / "data" / f"instances_{split}.jsonl"
    rows = load_rows(data_path)
    hidden_path, labels_path, meta_path = feature_paths(args, run, split)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta["spec"] != feature_spec(args, rows, data_path):
        raise ValueError(f"{split}: cached features do not match the model, prompt or data. Use a new --run_dir.")
    hidden = np.load(hidden_path, mmap_mode="r")
    labels = np.load(labels_path)
    if list(hidden.shape) != meta["shape"] or hidden.shape[0] != len(rows):
        raise ValueError(f"{split}: invalid activation dimensions")
    if not np.array_equal(labels, [row["label"] for row in rows]):
        raise ValueError(f"{split}: feature/label ordering mismatch")
    if not np.isfinite(hidden).all() or np.any(np.all(hidden == 0, axis=(1, 2))):
        raise ValueError(f"{split}: invalid or all-zero feature rows")
    return hidden, labels, meta


def extract(args, run):
    import torch
    from tqdm import tqdm
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Run this command in your activated host terminal.")
    model = tokenizer = None
    for split in SPLITS:
        hidden_path, labels_path, meta_path = feature_paths(args, run, split)
        if meta_path.exists():
            load_features(args, run, split)
            print(f"{split}: verified existing activations; skipping extraction.", flush=True)
            continue
        rows = load_rows(run / "data" / f"instances_{split}.jsonl")
        if model is None:
            tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
            model = AutoModelForCausalLM.from_pretrained(
                args.model, local_files_only=True, dtype=torch.bfloat16,
                device_map={"": 0}, attn_implementation="sdpa",
            ).eval()
            model.requires_grad_(False)
            if not hasattr(model, "model") or not hasattr(model.model, "layers"):
                raise TypeError("This small reproduction entry supports dense Qwen/Llama-style decoders.")
        layers, dim = model.config.num_hidden_layers, model.config.hidden_size
        hidden = np.empty((len(rows), layers, dim), dtype=np.float16)
        token_counts = []
        torch.cuda.reset_peak_memory_stats()
        start = time.monotonic()
        for idx, row in enumerate(tqdm(rows, desc=f"extract/{split}")):
            prompt = render_prompt(args.template, row["question"], row["docs"], tokenizer=tokenizer)
            inputs = tokenizer(prompt, return_tensors="pt", truncation=False).to("cuda:0")
            length = inputs.input_ids.shape[1]
            if length > model.config.max_position_embeddings:
                raise ValueError(f"{row['id']}: {length} tokens exceed the model context; evidence was not truncated.")
            token_counts.append(length)
            try:
                with torch.inference_mode():
                    # Same hidden states as CausalLM; avoid allocating full-vocabulary logits.
                    output = model.model(**inputs, output_hidden_states=True,
                                         output_attentions=False, use_cache=False)
                for layer in range(layers):
                    hidden[idx, layer] = output.hidden_states[layer + 1][0, -1].float().cpu().numpy()
                if not np.isfinite(hidden[idx]).all() or not np.any(hidden[idx]):
                    raise ValueError("Non-finite or all-zero hidden states")
            except Exception as error:
                raise RuntimeError(f"Feature extraction failed for {row['id']} ({length} tokens). No completed cache was saved.") from error
            finally:
                if "output" in locals():
                    del output
                del inputs
        hidden_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(hidden_path, hidden)
        np.save(labels_path, np.asarray([row["label"] for row in rows], dtype=np.int8))
        meta = {
            "spec": feature_spec(args, rows, run / "data" / f"instances_{split}.jsonl"),
            "shape": list(hidden.shape), "convention": "H[i,l] = hidden_states[l+1][0,-1,:]",
            "dtype": "float16", "attention": "sdpa; attention matrices not returned",
            "full_documents": True, "token_counts": token_counts,
            "elapsed_seconds": time.monotonic() - start,
            "peak_allocated_gib": torch.cuda.max_memory_allocated() / 2**30,
        }
        write_json(meta_path, meta)
        print(f"{split}: saved {hidden.shape}; max input {max(token_counts)} tokens; "
              f"peak {meta['peak_allocated_gib']:.2f} GiB", flush=True)
        del hidden
    del model, tokenizer
    torch.cuda.empty_cache()


def metrics(truth, prediction):
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

    unsupported = truth != 0
    return {
        "accuracy": float(accuracy_score(truth, prediction)),
        "macro_f1": float(f1_score(truth, prediction, labels=[0, 1, 2], average="macro", zero_division=0)),
        "far": float(np.mean(prediction[unsupported] == 0)) if unsupported.any() else None,
        "confusion_matrix": confusion_matrix(truth, prediction, labels=[0, 1, 2]).tolist(),
        "label_order": MODES,
        "predicted_counts": {MODES[i]: int(np.sum(prediction == i)) for i in range(3)},
    }


def probe(args, run):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    train, y_train, train_meta = load_features(args, run, "train")
    val, y_val, val_meta = load_features(args, run, "val")
    if train.shape[1:] != val.shape[1:]:
        raise ValueError("Train/val activation dimensions differ")
    sweep, best = {}, None
    for layer in range(train.shape[1]):
        scaler = StandardScaler()
        x_train = scaler.fit_transform(train[:, layer].astype(np.float32))
        x_val = scaler.transform(val[:, layer].astype(np.float32))
        classifier = LogisticRegression(max_iter=2000, C=1.0, solver="lbfgs", random_state=args.seed)
        classifier.fit(x_train, y_train)
        result = metrics(y_val, classifier.predict(x_val))
        sweep[str(layer)] = {"val_acc": result["accuracy"], "val_f1": result["macro_f1"]}
        print(f"H L{layer:02d}: val_acc={result['accuracy']:.4f} val_f1={result['macro_f1']:.4f}", flush=True)
        if best is None or result["accuracy"] > best["val_acc"]:
            best = {"layer": layer, "val_acc": result["accuracy"], "classifier": classifier, "scaler": scaler}
    results = run / "results"
    results.mkdir(parents=True, exist_ok=True)
    write_json(results / "layer_probe_hidden.json", sweep)
    best["train_spec"] = train_meta["spec"]
    best["val_spec"] = val_meta["spec"]
    best["seed"] = args.seed
    with (results / "best_hidden_probe.pkl").open("wb") as f:
        pickle.dump(best, f)
    print(f"Selected L{best['layer']} using validation accuracy only.", flush=True)


def router(args, run):
    from sklearn.calibration import CalibratedClassifierCV

    results = run / "results"
    with (results / "best_hidden_probe.pkl").open("rb") as f:
        best = pickle.load(f)
    train, _, train_meta = load_features(args, run, "train")
    val, y_val, val_meta = load_features(args, run, "val")
    test, y_test, test_meta = load_features(args, run, "test")
    if best["train_spec"] != train_meta["spec"] or best["val_spec"] != val_meta["spec"] or best["seed"] != args.seed:
        raise ValueError("Probe settings changed. Rerun the probe stage.")
    if train.shape[1:] != val.shape[1:] or train.shape[1:] != test.shape[1:]:
        raise ValueError("Activation dimensions differ across splits")
    layer, scaler = best["layer"], best["scaler"]
    calibrated = CalibratedClassifierCV(best["classifier"], cv="prefit", method="sigmoid")
    calibrated.fit(scaler.transform(val[:, layer].astype(np.float32)), y_val)
    x_test = scaler.transform(test[:, layer].astype(np.float32))
    prediction = calibrated.predict(x_test)
    probability = calibrated.predict_proba(x_test)
    summary = {
        "model": str(Path(args.model).resolve()), "template": args.template,
        "selected_layer": layer, "selection_metric": "validation accuracy",
        "calibration": "sigmoid, fitted on validation only",
        "n_train": len(train), "n_val": len(val), "n_test": len(test),
        "test": metrics(y_test, prediction),
        "sampling": json.loads((run / "data" / "manifest.json").read_text())["sampling"],
        "render_policy": RENDER_POLICY,
    }
    write_json(results / "router_metrics.json", summary)
    predictions = [{"id": rid, "true_mode": MODES[int(y)], "pred_mode": MODES[int(p)],
                    "probabilities": {mode: float(probability[i, j]) for j, mode in enumerate(MODES)}}
                   for i, (rid, y, p) in enumerate(zip(test_meta["spec"]["ids"], y_test, prediction))]
    write_json(results / "router_test_predictions.json", predictions)
    with (results / "router_hidden_dev.pkl").open("wb") as f:
        pickle.dump({"router": calibrated, "scaler": scaler, "layers": [layer],
                     "feature_type": "hidden_last_token", "template": args.template,
                     "train_mode": "train", "calibration": "sigmoid", "C": 1.0,
                     "model": summary["model"], "convention": test_meta["convention"]}, f)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["all", "prepare", "extract", "probe", "router"], default="all")
    parser.add_argument("--run_dir", type=Path, default=Path("runs/qwen2.5-3b-small"))
    parser.add_argument("--model", default=os.environ.get("KBA_MODEL"))
    parser.add_argument("--template", choices=["P0", "P1", "P2", "P3", "P4", "P5"], default="P0")
    parser.add_argument("--train_questions", type=int, default=200)
    parser.add_argument("--val_questions", type=int, default=95)
    parser.add_argument("--test_questions", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not args.model:
        parser.error("Use run_small_repro.sh, source configs/local.env, or pass --model.")
    run = args.run_dir if args.run_dir.is_absolute() else PROJECT / args.run_dir
    print(f"Run directory: {run}", flush=True)
    prepare(args, run)
    for stage, function in [("extract", extract), ("probe", probe), ("router", router)]:
        if args.stage in ["all", stage]:
            function(args, run)
    print(f"Completed stage {args.stage}.", flush=True)


if __name__ == "__main__":
    main()
