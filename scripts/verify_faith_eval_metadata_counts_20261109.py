#!/usr/bin/env python3
"""Independently count pinned qid/subset columns with an in-memory SQL join."""
import json
import sqlite3

from faith_eval_metadata_counts_20261109 import RangeReader, SOURCES, read_columns


def main():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE metadata (side TEXT NOT NULL, qid TEXT NOT NULL, subset TEXT NOT NULL)")
    for side, spec in SOURCES.items():
        url = (f"https://huggingface.co/datasets/{spec['dataset']}/resolve/"
               f"{spec['revision']}/data/test-00000-of-00001.parquet")
        with RangeReader(url) as handle:
            rows = read_columns(handle)
        if len(rows) != spec["rows"] or any(not isinstance(q, str) or not q.strip() or
                                            not isinstance(s, str) or not s.strip() for q, s in rows):
            raise ValueError("invalid metadata")
        db.executemany("INSERT INTO metadata VALUES (?, ?, ?)", ((side, q, s) for q, s in rows))
    stats = {}
    for side in ("I", "C"):
        row_count, distinct_count = db.execute(
            "SELECT count(*),count(DISTINCT qid) FROM metadata WHERE side=?", (side,)).fetchone()
        duplicated = db.execute("SELECT count(*) FROM (SELECT qid FROM metadata WHERE side=? GROUP BY qid HAVING count(*)>1)", (side,)).fetchone()[0]
        distribution = dict(db.execute("SELECT subset,count(*) FROM metadata WHERE side=? GROUP BY subset ORDER BY subset", (side,)))
        stats[side] = {"rows": row_count, "unique_qids": distinct_count, "duplicate_qids": duplicated, "rows_by_subset": distribution}
    common = db.execute("SELECT count(*) FROM (SELECT qid FROM metadata WHERE side='I' INTERSECT SELECT qid FROM metadata WHERE side='C')").fetchone()[0]
    strict_query = """WITH singles AS (
      SELECT side,qid,min(subset) AS subset FROM metadata GROUP BY side,qid HAVING count(*)=1
    ) SELECT i.subset,count(*) FROM singles i JOIN singles c ON i.qid=c.qid AND i.subset=c.subset
      WHERE i.side='I' AND c.side='C' GROUP BY i.subset ORDER BY i.subset"""
    strict = dict(db.execute(strict_query))
    assert stats["I"]["rows"] == 2492 and stats["I"]["unique_qids"] == 2491 and stats["I"]["duplicate_qids"] == 1
    assert stats["C"]["rows"] == 1500 and stats["C"]["unique_qids"] == 1500 and stats["C"]["duplicate_qids"] == 0
    assert common == sum(strict.values()) == 785
    assert strict == {"BioASQ":76,"DROP":71,"HotpotQA":86,"NaturalQuestionsShort":76,"NewsQA":72,
                      "RACE":92,"SQuAD":81,"SearchQA":70,"TextbookQA":95,"TriviaQA-web":66}
    print(json.dumps({"status":"passed_sql_independent_aggregation", "common":common,
                      "strict":sum(strict.values()), "strict_by_subset":strict,
                      "unique_I":stats["I"]["unique_qids"], "unique_C":stats["C"]["unique_qids"]}, sort_keys=True))
    db.close()


if __name__ == "__main__":
    main()
