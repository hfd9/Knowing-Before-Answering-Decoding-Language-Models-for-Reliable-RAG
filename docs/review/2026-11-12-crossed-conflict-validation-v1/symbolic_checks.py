#!/usr/bin/env python3
"""Check a crossed symbolic design; no natural-language inputs or model access."""
from collections import Counter
from itertools import permutations

names = ("A", "B", "C")
values = ("x", "y", "z")
reference = dict(zip(names, values))
contexts = []
for perm in permutations(values):
    doc = dict(zip(names, perm))
    changed = {e for e in names if doc[e] != reference[e]}
    if len(changed) == 2:
        contexts.append((doc, changed))
assert len(contexts) == 3
rows = [(i, target, target in changed)
        for i, (_, changed) in enumerate(contexts) for target in names]
assert len(rows) == 9 and sum(y for _, _, y in rows) == 6
assert all(Counter(reference.values()) == Counter(doc.values()) for doc, _ in contexts)
same_doc_pairs = [(i, a, b) for i, (_, changed) in enumerate(contexts)
                  for a in sorted(changed) for b in names if b not in changed]
same_question_pairs = [(a, i, j) for a in names
                       for i, (_, changes_i) in enumerate(contexts) if a in changes_i
                       for j, (_, changes_j) in enumerate(contexts) if a not in changes_j]
assert len(same_doc_pairs) == len(same_question_pairs) == 6
assert all(len({e for e in names if contexts[i][0][e] != contexts[j][0][e]}) == 3
           for _, i, j in same_question_pairs)
by_doc = [[y for i, _, y in rows if i == j] for j in range(3)]
by_question = [[y for _, target, y in rows if target == t] for t in names]
best_doc_only = sum(max(sum(group), len(group) - sum(group)) for group in by_doc)
best_q_only = sum(max(sum(group), len(group) - sum(group)) for group in by_question)
assert best_doc_only == best_q_only == 6
print("contexts=3 rows=9 target_conflict=6 other_conflict=3")
print("same_document_opposite_target_pairs=6 same_question_opposite_context_pairs=6")
print("same_question_pairs_change_all_three_assignments=True")
print("optimal_doc_only_and_question_only_accuracy=6/9 each (unbalanced)")
print("pairwise_ranking_constant_within_group=0.5 (ties half)")
