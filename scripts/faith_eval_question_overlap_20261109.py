#!/usr/bin/env python3
"""Aggregate question-only overlap with explicitly exposed project materials.

No result IDs, question text, context, answers, candidate selections or per-row
matches are written or printed. The sealed source archive is never opened.
"""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import re
import unicodedata

import pyarrow.parquet as pq

from faith_eval_metadata_counts_20261109 import RangeReader, SOURCES

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "runs/qwen2.5-3b-small/data/manifest.json"
EXPECTED_MANIFEST = "3fc899266cfad2009dc3f9baa42050fe37a822eb448afea6b2b3f347fbee3a24"
MATERIALS = ROOT / "prompts/semantic_transfer_materials_v5.json"
GROUPS = ("train200", "val95", "diagnostic100", "transfer30")


def normalized(text):
    if not isinstance(text, str):
        raise ValueError("question must be a string")
    tokens = re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold())
    if not tokens:
        raise ValueError("question cannot be empty")
    return " ".join(tokens)


def fingerprints(text):
    value = normalized(text)
    return value, frozenset(value.split())


def aggregate(candidates, baseline):
    """Only aggregate question pairs; finite exact and Jaccard match candidates."""
    if set(baseline) != set(GROUPS):
        raise ValueError("baseline groups do not match fixed allowlist")
    old = {key: set(map(fingerprints, vals)) for key, vals in baseline.items()}
    details = defaultdict(Counter)
    group_counts = {key: Counter() for key in GROUPS}
    total = Counter()
    for subset, question_i, question_c in candidates:
        if not isinstance(subset, str) or not subset.strip():
            raise ValueError("subset required")
        variants = set(map(fingerprints, (question_i, question_c)))
        normalized_equal = normalized(question_i) == normalized(question_c)
        exact_any = False
        near_any = False
        short = any(len(tokens) < 5 for _, tokens in variants)
        for group, references in old.items():
            exact = any(v[0] == w[0] for v in variants for w in references)
            near = any(len(v[1]) >= 5 and len(w[1]) >= 5 and
                       len(v[1] & w[1]) / len(v[1] | w[1]) >= 0.8
                       for v in variants for w in references)
            group_counts[group]["exact"] += int(exact)
            group_counts[group]["near_including_exact"] += int(near or exact)
            exact_any |= exact
            near_any |= near
        for c in (total, details[subset]):
            c["strict_qids"] += 1
            c["question_normalized_equal"] += int(normalized_equal)
            c["question_normalized_different"] += int(not normalized_equal)
            c["exact_any_group"] += int(exact_any)
            c["near_or_exact_any_group"] += int(near_any or exact_any)
            c["either_question_under_five_unique_tokens"] += int(short)
    return {"total": dict(total), "by_subset": {k: dict(v) for k, v in sorted(details.items())},
            "by_existing_group": {k: dict(v) for k, v in group_counts.items()},
            "baseline_unique_normalized_questions": {k: len(v) for k, v in old.items()},
            "method": "NFKC, casefold, Unicode word-token equality; Jaccard >= 0.8 and >=5 unique tokens per side; exploratory candidate flags only"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def allowed_baseline():
    if sha(MANIFEST) != EXPECTED_MANIFEST:
        raise ValueError("fixed manifest changed")
    manifest = json.loads(MANIFEST.read_text())
    choices = (("train200", "train", 600, 200), ("val95", "val", 285, 95),
               ("diagnostic100", "test", 300, 100))
    result = {}
    for name, split, nrows, nbases in choices:
        path = ROOT / f"runs/qwen2.5-3b-small/data/instances_{split}.jsonl"
        spec = manifest["splits"][split]
        if sha(path) != spec["sha256"] or spec["n_questions"] != nbases:
            raise ValueError("fixed sampled data hash or base count changed")
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if len(rows) != nrows or len({r["original_id"] for r in rows}) != nbases:
            raise ValueError("sampled data row or base count changed")
        result[name] = [r["question"] for r in rows]
    units = json.loads(MATERIALS.read_text())["units"]
    if len(units) != 30 or len({u["original_id"] for u in units}) != 30:
        raise ValueError("transfer author material count changed")
    result["transfer30"] = [u["question"] for u in units]
    return result


def remote_aggregate():
    remote = {}
    for side, spec in SOURCES.items():
        url = (f"https://huggingface.co/datasets/{spec['dataset']}/resolve/"
               f"{spec['revision']}/data/test-00000-of-00001.parquet")
        with RangeReader(url) as handle:
            table = pq.read_table(handle, columns=["qid", "subset", "question"], use_threads=False)
        rows = table.to_pylist()
        if len(rows) != spec["rows"]:
            raise ValueError("unexpected remote row count")
        groups = defaultdict(list)
        for row in rows:
            if not isinstance(row["qid"], str) or not row["qid"].strip():
                raise ValueError("invalid qid")
            groups[row["qid"]].append(row)
        remote[side] = groups
    candidates = []
    for qid in remote["I"].keys() & remote["C"].keys():
        left, right = remote["I"][qid], remote["C"][qid]
        if len(left) == len(right) == 1 and left[0]["subset"] == right[0]["subset"]:
            candidates.append((left[0]["subset"], left[0]["question"], right[0]["question"]))
    if len(candidates) != 785:
        raise ValueError("strict metadata intersection changed")
    result = aggregate(candidates, allowed_baseline())
    result.update({"scope":"aggregate-only question overlap; no qids, candidates, texts or full files saved",
                   "full_file_sha256_verified":False, "heldout_380_accessed":False,
                   "context_and_answers_read":False,
                   "transfer_material_sha256":sha(MATERIALS), "sources":SOURCES})
    return result


if __name__ == "__main__":
    print(json.dumps(remote_aggregate(), ensure_ascii=False, sort_keys=True, indent=2))
