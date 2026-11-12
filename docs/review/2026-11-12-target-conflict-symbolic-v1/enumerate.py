#!/usr/bin/env python3
"""Enumerate symbolic relations; no natural-language dataset or model access."""
from collections import Counter
from itertools import permutations
import json

entities = ("A", "B", "C")
values = ("x", "y", "z")
doc1 = dict(zip(entities, values))
rows = []
for values2 in permutations(values):
    doc2 = dict(zip(entities, values2))
    for target in entities:
        conflicting = [e for e in entities if doc1[e] != doc2[e]]
        condition = "target" if target in conflicting else ("other" if conflicting else "none")
        rows.append({"target": target, "doc2": values2, "conflicting": conflicting,
                     "condition": condition, "n_conflicting": len(conflicting),
                     "document_bag_equal": Counter(doc1.keys()) + Counter(doc1.values()) ==
                                           Counter(doc2.keys()) + Counter(doc2.values())})
counts = Counter((r["condition"], r["n_conflicting"]) for r in rows)
assert len(rows) == 18 and all(r["document_bag_equal"] for r in rows)
assert counts == {("none", 0): 3, ("other", 2): 3, ("target", 2): 6,
                  ("target", 3): 6}
for target in entities:
    subset = [r for r in rows if r["target"] == target]
    assert sum(r["condition"] == "other" and r["n_conflicting"] == 2 for r in subset) == 1
    assert sum(r["condition"] == "target" and r["n_conflicting"] == 2 for r in subset) == 2
print(json.dumps({"status": "passed", "rows": rows,
                  "counts": {f"{a}:{b}": n for (a, b), n in sorted(counts.items())}}, indent=2))
