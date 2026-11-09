#!/usr/bin/env python3
"""Count FaithEval qid/subset metadata only; never materialize or output text rows."""

import argparse
from collections import Counter, defaultdict
import io
import json
import re

import pyarrow.parquet as pq


SOURCES = {
    "I": {
        "dataset": "Salesforce/FaithEval-unanswerable-v1.0",
        "revision": "4a14e0e9860e270a8c9ff57c511821f4f50dce57",
        "rows": 2492,
    },
    "C": {
        "dataset": "Salesforce/FaithEval-inconsistent-v1.0",
        "revision": "e29508db3955db2c82a80a1f3c3aadc11f93fc3f",
        "rows": 1500,
    },
}


def count(left, right):
    """Aggregate complete columns; keep identifiers exclusively in memory."""
    by_side = {}
    for name, rows in (("I", left), ("C", right)):
        groups = defaultdict(Counter)
        for qid, subset in rows:
            if not isinstance(qid, str) or not qid.strip():
                raise ValueError("empty or non-string qid")
            if not isinstance(subset, str) or not subset.strip():
                raise ValueError("empty or non-string subset")
            groups[qid][subset] += 1
        subset_counts = Counter(subset for _, subset in rows)
        by_side[name] = {
            "groups": groups,
            "counts": {
                "rows": len(rows),
                "unique_qids": len(groups),
                "duplicate_qids": sum(sum(v.values()) > 1 for v in groups.values()),
                "duplicate_rows_beyond_first": len(rows) - len(groups),
                "qids_with_multiple_subsets": sum(len(v) > 1 for v in groups.values()),
                "rows_by_subset": dict(sorted(subset_counts.items())),
            },
        }
    a, b = by_side["I"]["groups"], by_side["C"]["groups"]
    common = a.keys() & b.keys()
    strict = [q for q in common if sum(a[q].values()) == sum(b[q].values()) == 1
              and next(iter(a[q])) == next(iter(b[q]))]
    subset_strict = Counter(next(iter(a[q])) for q in strict)
    mismatched = sum(not (a[q].keys() & b[q].keys()) for q in common)
    return {
        "I": by_side["I"]["counts"],
        "C": by_side["C"]["counts"],
        "intersection_unique_qids": len(common),
        "intersection_no_shared_subset_qids": mismatched,
        "intersection_strict_one_row_each_same_subset": len(strict),
        "intersection_strict_by_subset": dict(sorted(subset_strict.items())),
        "intersection_unresolved_or_duplicate_qids": len(common) - len(strict),
        "interpretation": "metadata matching only; not verified same question, semantic status, non-overlap or usable sample",
    }


def read_columns(path):
    table = pq.read_table(path, columns=["qid", "subset"], use_threads=False)
    return list(zip(table.column("qid").to_pylist(), table.column("subset").to_pylist()))


class RangeReader(io.RawIOBase):
    """Read only explicit HTTP byte ranges, never saving the remote file."""

    def __init__(self, url):
        import requests
        super().__init__()
        self._session = requests.Session()
        self._url = url
        self._pos = 0
        try:
            response = self._session.get(url, headers={"Range": "bytes=0-0"}, stream=True, timeout=30)
        except requests.RequestException:
            raise RuntimeError("HTTP range request failed") from None
        try:
            match = re.fullmatch(r"bytes 0-0/(\d+)", response.headers.get("Content-Range", ""))
            if response.status_code != 206 or not match or len(response.content) != 1:
                raise ValueError("server does not support exact HTTP range requests")
            self._size = int(match.group(1))
            self._url = response.url
        finally:
            response.close()

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self._pos

    def seek(self, offset, whence=io.SEEK_SET):
        pos = offset if whence == io.SEEK_SET else self._pos + offset if whence == io.SEEK_CUR else self._size + offset
        if pos < 0:
            raise ValueError("negative file position")
        self._pos = pos
        return pos

    def read(self, size=-1):
        if self._pos >= self._size: return b""
        end = self._size if size is None or size < 0 else min(self._size, self._pos + size)
        if end <= self._pos: return b""
        first, last = self._pos, end - 1
        import requests
        try:
            response = self._session.get(self._url, headers={"Range": f"bytes={first}-{last}"}, stream=True, timeout=30)
        except requests.RequestException:
            raise RuntimeError("HTTP range request failed") from None
        try:
            expected = f"bytes {first}-{last}/{self._size}"
            if response.status_code != 206 or response.headers.get("Content-Range") != expected:
                raise ValueError("server returned an unexpected range")
            data = response.content
            if len(data) != end - first:
                raise ValueError("server returned an incomplete range")
            self._pos = end
            return data
        finally:
            response.close()

    def close(self):
        self._session.close()
        super().close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-i", help="local Parquet fixture for metadata-only counting")
    parser.add_argument("--local-c", help="local Parquet fixture for metadata-only counting")
    parser.add_argument("--remote", action="store_true", help="read pinned remote Parquet columns via HTTP range")
    args = parser.parse_args()
    if args.remote:
        if args.local_i or args.local_c:
            parser.error("choose remote or local fixtures")
        values = {}
        for side, spec in SOURCES.items():
            url = (f"https://huggingface.co/datasets/{spec['dataset']}/resolve/"
                   f"{spec['revision']}/data/test-00000-of-00001.parquet")
            with RangeReader(url) as handle:
                values[side] = read_columns(handle)
            if len(values[side]) != spec["rows"]:
                raise ValueError(f"unexpected {side} row count")
        result = count(values["I"], values["C"])
        result["sources"] = SOURCES
        result["full_file_sha256_verified"] = False
        result["read_scope"] = "Parquet qid and subset only; HTTP byte ranges may include neighboring bytes; no source files saved"
    else:
        if not args.local_i or not args.local_c:
            parser.error("provide both local fixtures or --remote")
        result = count(read_columns(args.local_i), read_columns(args.local_c))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
