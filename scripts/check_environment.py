"""Verify dependencies, local weights, CUDA and the project's probe APIs."""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path

import accelerate
import matplotlib
import numpy as np
import pandas
import scipy
import sentencepiece
import torch
import transformers
import yaml
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("KBA_MODEL"))
    parser.add_argument("--load-model", action="store_true")
    args = parser.parse_args()

    for name in ["torch", "transformers", "accelerate", "numpy", "scipy",
                 "scikit-learn", "matplotlib", "pandas", "tqdm", "safetensors",
                 "sentencepiece", "PyYAML"]:
        print(f"{name}: {importlib.metadata.version(name)}", flush=True)

    # Check the exact legacy classifier APIs used by 3.py and 6.py.
    rng = np.random.default_rng(42)
    train = rng.normal(size=(60, 8))
    labels = np.tile(np.arange(3), 20)
    scaler = StandardScaler().fit(train)
    train = scaler.transform(train)
    clf = LogisticRegression(multi_class="multinomial", max_iter=1000).fit(train, labels)
    calibrated = CalibratedClassifierCV(clf, cv="prefit", method="sigmoid")
    calibrated.fit(train, labels)
    probabilities = calibrated.predict_proba(train)
    assert probabilities.shape == (60, 3)
    assert np.isfinite(probabilities).all()
    assert np.allclose(probabilities.sum(axis=1), 1)
    print("Linear probe and sigmoid calibration APIs: OK", flush=True)

    print(f"CUDA runtime: {torch.version.cuda}; available: {torch.cuda.is_available()}", flush=True)
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is unavailable in this execution context.")
    print(f"GPU: {torch.cuda.get_device_name(0)}; BF16: {torch.cuda.is_bf16_supported()}", flush=True)
    tensor = torch.randn(128, 128, device="cuda", dtype=torch.bfloat16)
    assert torch.isfinite(tensor @ tensor.T).all().item()
    del tensor
    torch.cuda.synchronize()
    print("CUDA BF16 matrix multiplication: OK", flush=True)

    if not args.model:
        raise SystemExit("Pass --model or source configs/local.env to set KBA_MODEL.")
    path = Path(args.model)
    config = AutoConfig.from_pretrained(path, local_files_only=True)
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    index = path / "model.safetensors.index.json"
    if index.exists():
        shards = set(json.loads(index.read_text())["weight_map"].values())
        missing = [name for name in shards if not (path / name).is_file()]
        if missing:
            raise SystemExit(f"Missing weight shards: {missing}")
    elif not list(path.glob("*.safetensors")) and not list(path.glob("pytorch_model*.bin")):
        raise SystemExit(f"No local weights found in {path}")
    print(f"Local model: {path}\nArchitecture: {config.model_type}; layers: {config.num_hidden_layers}; "
          f"hidden size: {config.hidden_size}", flush=True)

    if args.load_model:
        # Use the original scripts' dtype and eager-attention requirements.
        torch.cuda.reset_peak_memory_stats()
        model = AutoModelForCausalLM.from_pretrained(
            path, local_files_only=True, dtype=torch.bfloat16,
            device_map={"": 0}, attn_implementation="eager",
        ).eval()
        model.requires_grad_(False)
        mlp_vectors = {}

        def make_hook(layer):
            def capture(_module, _inputs, output):
                mlp_vectors[layer] = output[0, -1].detach().float().cpu()
            return capture

        hooks = [block.mlp.register_forward_hook(make_hook(layer))
                 for layer, block in enumerate(model.model.layers)]
        prompt = "Document: The archive opened in 1998.\nQuestion: When did the archive open?\nAnswer:"
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        try:
            with torch.inference_mode():
                output = model(**inputs, output_hidden_states=True, output_attentions=True, use_cache=False)
        finally:
            for hook in hooks:
                hook.remove()
        hidden = torch.stack([state[0, -1].float() for state in output.hidden_states[1:]])
        assert hidden.shape == (config.num_hidden_layers, config.hidden_size)
        assert torch.isfinite(hidden).all().item()
        assert len(output.attentions) == config.num_hidden_layers
        assert all(attn is not None and torch.isfinite(attn).all().item() for attn in output.attentions)
        assert len(mlp_vectors) == config.num_hidden_layers
        assert all(vector.shape == (config.hidden_size,) and torch.isfinite(vector).all().item()
                   for vector in mlp_vectors.values())
        del output, hidden
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=16, do_sample=False,
                                       pad_token_id=tokenizer.eos_token_id)
        response = tokenizer.decode(generated[0, inputs.input_ids.shape[1]:], skip_special_tokens=True)
        print(f"Hidden states, MLP hooks, eager attention and generation: OK\nGenerated text: {response!r}", flush=True)
        print(f"Peak allocated GPU memory: {torch.cuda.max_memory_allocated() / 2**30:.2f} GiB", flush=True)
    print("Environment verification passed.", flush=True)


if __name__ == "__main__":
    main()
