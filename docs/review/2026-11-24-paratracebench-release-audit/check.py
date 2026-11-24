"""Inventory a fixed public ParaTraceBench release without executing its code."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess


REVISION = "f9cbea4eccaf492a2d27afbf7a1d02533ff566bd"
SPLITS = {"external": 567, "controlled": 140}
CASE_TAG = re.compile(r"((?:ANON|АНОН)-)\d+\b")
NUMBER = re.compile(r"\d+")


def blob(repository, path):
    return subprocess.check_output(["git", "-C", str(repository), "show", f"{REVISION}:{path}"])


def load_index(raw):
    rows = [json.loads(line) for line in raw.splitlines()]
    index = {row["case_id"]: row for row in rows}
    if len(index) != len(rows):
        raise ValueError("duplicate case IDs")
    return index


def package(rows, normalize):
    groups = defaultdict(set)
    for row in rows:
        fragments = tuple(normalize(fragment["text"]) for fragment in row["evidence_fragments"])
        groups[row["query"], fragments].add(row["expected_status"])
    return groups


def case_inventory(repository):
    inventories = {}
    split_keys = {}
    gold = {}
    maskers = {
        "exact": lambda value: value,
        "anonymous_case_tag_only": lambda value: CASE_TAG.sub(r"\1#", value),
        "all_digits": lambda value: NUMBER.sub("#", value),
    }
    for split, size in SPLITS.items():
        name = f"data/{split}/paratracebench_{split}_{size}.jsonl"
        raw = blob(repository, name)
        gold[split] = load_index(raw)
        if len(gold[split]) != size:
            raise ValueError(f"unexpected {split} row count")
        rows = list(gold[split].values())
        groups = {key: package(rows, masker) for key, masker in maskers.items()}
        inventories[split] = {
            "path": name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(rows),
            "distinct_query_strings": len({row["query"] for row in rows}),
            "provenance_source": Counter(row["provenance"]["source"] for row in rows),
            "source_doc_ids_per_case": Counter(
                len({fragment["source_doc_id"] for fragment in row["evidence_fragments"]}) for row in rows
            ),
            "expected_status": Counter(row["expected_status"] for row in rows),
            "visible_query_and_ordered_evidence": {
                key: {"distinct": len(items), "groups_with_multiple_statuses": sum(len(v) > 1 for v in items.values())}
                for key, items in groups.items()
            },
        }
        split_keys[split] = groups
    external = split_keys["external"]
    controlled = split_keys["controlled"]
    common = {mode: external[mode].keys() & controlled[mode].keys() for mode in maskers}
    overlap = {mode: len(keys) for mode, keys in common.items()}
    exact_status_agreements = sum(external["exact"][key] == controlled["exact"][key] for key in common["exact"])
    overlap["exact_shared_with_same_status"] = exact_status_agreements
    overlap["exact_shared_with_different_status"] = overlap["exact"] - exact_status_agreements
    return inventories, overlap, gold["external"]


def output_inventory(repository, gold):
    result = {}
    summary_path = "results/metrics/external_validation.csv"
    published = list(csv.DictReader(io.StringIO(blob(repository, summary_path).decode())))
    numerator_flags = (
        ("CLA", "has_contradiction", "conflict_localized"),
        ("NER", "has_contradiction", "non_explosive"),
        ("PHA", "has_priority", "priority_correct"),
        ("BRA", "has_update_pair", "belief_revision_correct"),
    )
    for line in published:
        method = line["method"]
        raw = blob(repository, f"outputs/raw/external/{method}.jsonl")
        normalized = blob(repository, f"outputs/normalized/external/{method}.jsonl")
        outputs = load_index(normalized)
        if outputs.keys() != gold.keys():
            raise ValueError(f"incomplete or extra rows for {method}")
        counts = {
            "n": len(outputs),
            "ASA_correct": sum(row["predicted_status"] == gold[case]["expected_status"] for case, row in outputs.items()),
        }
        for metric, inclusion, flag in numerator_flags:
            pool = [row for case, row in outputs.items() if gold[case]["annotation"][inclusion]]
            counts[f"{metric}_den"] = len(pool)
            counts[f"{metric}_correct"] = sum(bool(row["score_components"][flag]) for row in pool)
        result[method] = {
            "output_sha256": hashlib.sha256(normalized).hexdigest(),
            "raw_and_normalized_bytes_identical": raw == normalized,
            "distinct_answer_strings": len({row["answer"] for row in outputs.values()}),
            "counts": counts,
            "published_integer_count_differences": {
                key: {"recomputed": value, "published": int(line[key])}
                for key, value in counts.items() if value != int(line[key])
            },
        }
        if method == "b4_trace_based":
            levels = (("extracted_facts", "facts"), ("extracted_rules", "rules"),
                      ("conflicts", "conflicts"), ("priorities", "priorities"))
            result[method]["fields_exactly_matching_case_reference"] = {
                outcome: sum(row[outcome] == gold[case][reference] for case, row in outputs.items())
                for outcome, reference in levels
            }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path, help="local read-only copy of the public release Git objects")
    args = parser.parse_args()
    inventories, overlap, gold = case_inventory(args.repository)
    result = {
        "revision": REVISION,
        "case_inventories": inventories,
        "cross_split_shared_visible_input_keys": overlap,
        "output_inventory": output_inventory(args.repository, gold),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
