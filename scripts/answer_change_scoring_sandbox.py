"""Synthetic-only aggregation of explicitly supplied labels; never scores model text.

The protocol is not frozen. This module intentionally does not load experiment data.
"""

from collections import Counter

STATUSES = {"completed", "truncated", "failed", "not_run"}
LABELS = {"yes", "no", "unknown"}


def tri_and(*labels):
    """Kleene AND: definite failure dominates unknown; all yes is success."""
    if not labels or any(label not in LABELS for label in labels):
        raise ValueError("expected one or more yes/no/unknown labels")
    if "no" in labels:
        return "no"
    return "unknown" if "unknown" in labels else "yes"


def metric_counts(status_labels):
    """Use completed outputs only. Bounds are uncertainty bounds, not intervals."""
    statuses = Counter()
    labels = Counter()
    for status, label in status_labels:
        if status not in STATUSES:
            raise ValueError("invalid status")
        statuses[status] += 1
        if status == "completed":
            if label not in LABELS:
                raise ValueError("completed output requires a tri-state label")
            labels[label] += 1
        elif label is not None:
            raise ValueError("non-completed output cannot have a complete-response label")
    n = statuses["completed"]
    return {
        "planned": sum(statuses.values()),
        "status_counts": {status: statuses[status] for status in sorted(STATUSES)},
        "yes": labels["yes"], "no": labels["no"], "unknown": labels["unknown"],
        "assessable": labels["yes"] + labels["no"],
        "completed_bound": None if not n else [labels["yes"] / n, (labels["yes"] + labels["unknown"]) / n],
    }


def compare_first_failure(groups):
    """Summarize selected triads; labels refer to human assessments, not model internals.

    Each group supplies old_correct, new_correct, missing_failure as tri-state
    labels. Status exclusions and reference eligibility are handled before this call.
    """
    cells = Counter()
    for group in groups:
        premise = tri_and(group["old_correct"], group["new_correct"])
        failure = group["missing_failure"]
        if failure not in LABELS:
            raise ValueError("invalid missing-failure label")
        cells[(premise, failure)] += 1
    return {"groups": sum(cells.values()), "cells": {
        premise: {failure: cells[(premise, failure)] for failure in sorted(LABELS)}
        for premise in sorted(LABELS)
    }}
