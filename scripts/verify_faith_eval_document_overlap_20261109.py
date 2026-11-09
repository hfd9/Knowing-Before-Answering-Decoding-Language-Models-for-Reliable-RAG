#!/usr/bin/env python3
"""Independent aggregation of document-shingle collision flags in memory.

Shares the original source reader, fixed reference whitelist and normalizer;
uses separately implemented string shingles, inverted index and integer tests.
No source identifiers, texts, or candidate-level flags are printed or saved.
"""
from collections import Counter, defaultdict
import json

from faith_eval_metadata_counts_20261109 import SOURCES
from faith_eval_document_overlap_20261109 import normalize, read_remote_columns, reference_docs


def grams(tokens):
    return frozenset(" ".join(tokens[i:i+8]) for i in range(len(tokens)-7))


def main():
    references = {}
    for group, docs in reference_docs().items():
        for doc in docs:
            tok = normalize(doc)
            if len(tok) >= 16:
                references.setdefault(tok, set()).add(group)
    records = [(tok, grams(tok)) for tok in references]
    inv = defaultdict(set)
    for idx, (_, gs) in enumerate(records):
        for g in gs:
            inv[g].add(idx)
    sides = {}
    for side, spec in SOURCES.items():
        url = (f"https://huggingface.co/datasets/{spec['dataset']}/resolve/"
               f"{spec['revision']}/data/test-00000-of-00001.parquet")
        rows = read_remote_columns(url)
        assert len(rows) == spec["rows"]
        grouped = defaultdict(list)
        for row in rows:
            grouped[row["qid"]].append(row)
        sides[side] = grouped
    counts = Counter()
    for qid in sides["I"].keys() & sides["C"].keys():
        left, right = sides["I"][qid], sides["C"][qid]
        if len(left) != 1 or len(right) != 1 or left[0]["subset"] != right[0]["subset"]:
            continue
        counts["qids"] += 1
        seen_near = False
        seen_equal = False
        seen_containment = False
        for side, row in (("I", left[0]), ("C", right[0])):
            tok = normalize(row["context"])
            if len(tok) < 16:
                counts[f"short_{side}"] += 1
                continue
            gs = grams(tok)
            possible = set().union(*(inv[g] for g in gs)) if gs else set()
            flag_near = False
            flag_equal = False
            flag_containment = False
            target = " " + " ".join(tok) + " "
            for idx in possible:
                oldtok, oldgs = records[idx]
                oldtext = " " + " ".join(oldtok) + " "
                if oldtok == tok: flag_equal = True
                if oldtext in target or target in oldtext: flag_containment = True
                if len(gs) >= 9 and len(oldgs) >= 9 and 5 * len(gs & oldgs) >= 4 * min(len(gs), len(oldgs)):
                    flag_near = True
            counts[f"near_{side}"] += flag_near
            counts[f"equal_{side}"] += flag_equal
            counts[f"contain_{side}"] += flag_containment
            seen_near |= flag_near
            seen_equal |= flag_equal
            seen_containment |= flag_containment
        counts["near_qids"] += seen_near
        counts["equal_qids"] += seen_equal
        counts["contain_qids"] += seen_containment
    expected = {"qids":785, "short_I":6, "short_C":0, "near_I":1, "near_C":1, "near_qids":1,
                "equal_I":0, "equal_C":0, "equal_qids":0,
                "contain_I":0, "contain_C":0, "contain_qids":0}
    for key, value in expected.items():
        assert counts[key] == value, key
    print(json.dumps({"status":"passed_independent_shingle_aggregation", **expected}, sort_keys=True))


if __name__ == "__main__":
    main()
