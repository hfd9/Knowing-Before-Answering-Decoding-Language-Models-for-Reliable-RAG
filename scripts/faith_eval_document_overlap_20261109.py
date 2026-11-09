#!/usr/bin/env python3
"""Read-only in-memory document collision screening; emit aggregate counts only.

No candidate IDs, context, source files, matches, labels or samples are saved.
The pre-existing 380 local-ID list is read only to test namespace comparability;
the sealed original test archive and held-out question/document text stay closed.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

import pyarrow.parquet as pq

from faith_eval_metadata_counts_20261109 import RangeReader, SOURCES
from faith_eval_question_overlap_20261109 import MANIFEST, EXPECTED_MANIFEST, sha

ROOT = Path(__file__).resolve().parents[1]
SEALED_INDEX = ROOT / "runs/qwen2.5-3b-classification-grid/audit.json"
SEALED_INDEX_SHA = "a41da49e25a8c306fcf6c23f63bcd17b7bf8b93939f3c7e1ac717572002f32ce"
TRANSFER = ROOT / "runs/qwen2.5-3b-semantic-transfer-materials-v5/materials/inputs.json"
TRANSFER_SHA = "2b0ed2bde91624a7eab2eec38c66f4d2d9c2f875760ca7d49995c847c512ae97"


def normalize(text):
    if not isinstance(text, str):
        raise ValueError("context must be a string")
    tokens = re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold())
    return tuple(tokens)


def shingles(tokens):
    return frozenset(tuple(tokens[i:i + 8]) for i in range(max(0, len(tokens) - 7)))


def reference_docs():
    if sha(MANIFEST) != EXPECTED_MANIFEST:
        raise ValueError("fixed manifest changed")
    manifest = json.loads(MANIFEST.read_text())
    groups = {}
    for group, split, count, bases in (("train200", "train", 600, 200),
                                       ("val95", "val", 285, 95),
                                       ("diagnostic100", "test", 300, 100)):
        path = ROOT / f"runs/qwen2.5-3b-small/data/instances_{split}.jsonl"
        info = manifest["splits"][split]
        if sha(path) != info["sha256"] or info["n_questions"] != bases:
            raise ValueError("old fixed selection changed")
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if len(rows) != count or len({r["original_id"] for r in rows}) != bases:
            raise ValueError("old sampled data changed")
        groups[group] = [doc for row in rows for doc in row["docs"]]
    if sha(TRANSFER) != TRANSFER_SHA:
        raise ValueError("old transfer materials hash changed")
    rows = json.loads(TRANSFER.read_text())
    if len(rows) != 240 or len({r["original_id"] for r in rows}) != 30:
        raise ValueError("old transfer materials changed")
    groups["transfer30"] = [doc for row in rows for doc in row["docs"]]
    return groups


def build_index(groups):
    documents = {}
    short_by_group = Counter()
    for group, texts in groups.items():
        for text in texts:
            tokens = normalize(text)
            if len(tokens) < 16:
                short_by_group[group] += 1
                continue
            documents.setdefault(tokens, set()).add(group)
    refs = [(tokens, shingles(tokens), frozenset(labels)) for tokens, labels in documents.items()]
    index = defaultdict(set)
    for i, (_, grams, _) in enumerate(refs):
        if len(grams) >= 9:
            for gram in grams:
                index[gram].add(i)
    return refs, index, dict(sorted(short_by_group.items()))


def flags(text, refs, index):
    tokens = normalize(text)
    if len(tokens) < 16:
        return {"short": True, "equal": set(), "contain": set(), "shingle": set()}
    text_norm = " " + " ".join(tokens) + " "
    grams = shingles(tokens)
    overlap = Counter()
    for gram in grams:
        overlap.update(index.get(gram, ()))
    equal, contain, similar = set(), set(), set()
    # Repetitive references may have fewer than nine distinct shingles and
    # are absent from the index; still check exact equality/containment.
    indices = set(overlap) | {i for i, (_, old_grams, _) in enumerate(refs) if len(old_grams) < 9}
    for idx in indices:
        shared = overlap[idx]
        old_tokens, old_grams, groups = refs[idx]
        old_norm = " " + " ".join(old_tokens) + " "
        if old_tokens == tokens:
            equal.update(groups)
        if old_norm in text_norm or text_norm in old_norm:
            contain.update(groups)
        if len(grams) >= 9 and len(old_grams) >= 9 and shared >= math.ceil(0.8 * min(len(grams), len(old_grams))):
            similar.update(groups)
    return {"short": False, "equal": equal, "contain": contain, "shingle": similar}


def read_remote_columns(url):
    """Retry transient HTTP failures; no incomplete result is returned."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    last_error = None
    for _ in range(3):
        try:
            with RangeReader(url) as handle:
                retry = Retry(total=2, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))
                handle._session.mount("https://", HTTPAdapter(max_retries=retry))
                # ParquetFile avoids dataset scanner worker threads on an I/O error.
                return pq.ParquetFile(handle).read(columns=["qid", "subset", "context"], use_threads=False).to_pylist()
        except RuntimeError as exc:
            last_error = exc
    raise RuntimeError("remote column read failed after three attempts") from last_error


def main():
    if sha(SEALED_INDEX) != SEALED_INDEX_SHA:
        raise ValueError("sealed-ID audit index changed")
    audit = json.loads(SEALED_INDEX.read_text())
    sealed_ids = set(audit["unseen_confirmation_original_ids"])
    if len(sealed_ids) != 380 or any(not re.fullmatch(r"test_\d+", x) for x in sealed_ids):
        raise ValueError("sealed-ID index format or count changed")
    sides = {}
    for side, spec in SOURCES.items():
        url = (f"https://huggingface.co/datasets/{spec['dataset']}/resolve/"
               f"{spec['revision']}/data/test-00000-of-00001.parquet")
        rows = read_remote_columns(url)
        if len(rows) != spec["rows"]:
            raise ValueError("unexpected row count")
        groups = defaultdict(list)
        for row in rows:
            if not isinstance(row["qid"], str) or not row["qid"].strip():
                raise ValueError("invalid qid")
            groups[row["qid"]].append(row)
        sides[side] = groups
    ids = sides["I"].keys() & sides["C"].keys()
    strict = [(k, sides["I"][k][0], sides["C"][k][0]) for k in ids
              if len(sides["I"][k]) == len(sides["C"][k]) == 1
              and sides["I"][k][0]["subset"] == sides["C"][k][0]["subset"]]
    if len(strict) != 785:
        raise ValueError("strict intersection changed")
    refs, index, short_refs = build_index(reference_docs())
    totals = Counter()
    by_side = {"I": Counter(), "C": Counter()}
    by_old_group = {k: Counter() for k in ("train200", "val95", "diagnostic100", "transfer30")}
    for _, a, b in strict:
        seen = {"equal": set(), "contain": set(), "shingle": set()}
        for side, row in (("I", a), ("C", b)):
            x = flags(row["context"], refs, index)
            by_side[side]["short_contexts"] += int(x["short"])
            for kind in seen:
                seen[kind].update(x[kind])
                by_side[side][kind + "_contexts"] += int(bool(x[kind]))
        for kind, groups in seen.items():
            totals[kind + "_qids"] += int(bool(groups))
            for group in by_old_group:
                by_old_group[group][kind + "_qids"] += int(group in groups)
    qid_formats = Counter("hex32" if re.fullmatch(r"[0-9a-f]{32}", qid) else "other" for qid, _, _ in strict)
    result = {"strict_qids": len(strict), "candidate_qid_format_counts": dict(qid_formats),
              "sealed_index": {"local_id_count": len(sealed_ids), "local_id_format": "test_numeric",
                               "literal_id_overlap": sum(qid in sealed_ids for qid, _, _ in strict),
                               "limitation": "different identifier namespaces; no question or document comparison against the sealed 380"},
              "reference_unique_documents_at_least_16_words": len(refs),
              "reference_short_document_occurrences_by_group": short_refs,
              "by_candidate_side": {k: dict(v) for k, v in by_side.items()},
              "qid_flag_counts": dict(totals), "qid_flag_counts_by_old_group": {k: dict(v) for k, v in by_old_group.items()},
              "method": "NFKC casefold unicode word tokens; minimum 16 tokens; normalized whole-context equality or containment; >=80% shorter-set unique 8-token shingle containment with >=9 shingles; flags only",
              "transfer_material_sha256": sha(TRANSFER), "sealed_question_or_document_text_accessed": False,
              "source_contexts_saved": False, "candidate_identifiers_or_flags_saved": False,
              "full_remote_sha256_verified": False}
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
