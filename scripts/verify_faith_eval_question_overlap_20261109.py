#!/usr/bin/env python3
"""Recount question overlap in a separate process using an inverted token index.

Shares the fixed remote reader, normalizer and local allowlist; does not save or
print candidate IDs, questions, answer passages, or per-item matches.
"""
from collections import defaultdict
import json

import pyarrow.parquet as pq
from faith_eval_metadata_counts_20261109 import RangeReader, SOURCES
from faith_eval_question_overlap_20261109 import allowed_baseline, fingerprints


def main():
    sides = {}
    for side, spec in SOURCES.items():
        url = (f"https://huggingface.co/datasets/{spec['dataset']}/resolve/"
               f"{spec['revision']}/data/test-00000-of-00001.parquet")
        with RangeReader(url) as handle:
            rows = pq.read_table(handle, columns=["qid", "subset", "question"], use_threads=False).to_pylist()
        assert len(rows) == spec["rows"]
        grouped = defaultdict(list)
        for row in rows:
            grouped[row["qid"]].append(row)
        sides[side] = grouped
    baseline = allowed_baseline()
    unique_old = set(fingerprints(q) for group in baseline.values() for q in group)
    exact_index = {value for value, _ in unique_old}
    token_index = defaultdict(set)
    old_by_index = list(unique_old)
    for i, (_, tokens) in enumerate(old_by_index):
        if len(tokens) >= 5:
            for token in tokens:
                token_index[token].add(i)
    common = sides["I"].keys() & sides["C"].keys()
    totals = {"strict":0, "normalized_equal":0, "exact":0, "near_or_exact":0, "short":0}
    for qid in common:
        a, b = sides["I"][qid], sides["C"][qid]
        if len(a) != 1 or len(b) != 1 or a[0]["subset"] != b[0]["subset"]:
            continue
        fa, fb = fingerprints(a[0]["question"]), fingerprints(b[0]["question"])
        variants = {fa, fb}
        totals["strict"] += 1
        totals["normalized_equal"] += fa[0] == fb[0]
        totals["short"] += any(len(x[1]) < 5 for x in variants)
        exact = any(v[0] in exact_index for v in variants)
        near = False
        for _, toks in variants:
            if len(toks) < 5:
                continue
            possible = set().union(*(token_index[t] for t in toks))
            for idx in possible:
                other = old_by_index[idx][1]
                # Compute union size without using the original aggregator.
                shared = len(toks.intersection(other))
                if 5 * shared >= 4 * (len(toks) + len(other) - shared):
                    near = True
                    break
        totals["exact"] += exact
        totals["near_or_exact"] += near or exact
    assert totals == {"strict":785, "normalized_equal":785, "exact":1, "near_or_exact":1, "short":28}
    print(json.dumps({"status":"passed_inverted_index_aggregation", **totals}, sort_keys=True))


if __name__ == "__main__":
    main()
