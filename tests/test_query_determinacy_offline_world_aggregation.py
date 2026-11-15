import itertools
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import query_determinacy_offline_world_aggregation as aggregation


class AggregationTests(unittest.TestCase):
    def test_all_pairs_never_turn_missing_branches_into_certainty(self):
        for a,b in itertools.product('YNUXT',repeat=2):
            actual=aggregation.combine(a,b)
            if 'T' in (a,b):self.assertEqual(actual,'T')
            elif a not in 'YN' or b not in 'YN':self.assertEqual(actual,'X')
            elif a==b:self.assertEqual(actual,a)
            else:self.assertEqual(actual,'U')

    def test_full_paired_aggregation_replays_saved_summary(self):
        rows,summary=aggregation.evaluate()
        self.assertEqual(len(rows),48)
        path=ROOT/'docs/review/2026-11-15-query-determinacy-offline-world-aggregation-v1/summary.json'
        self.assertEqual(summary,json.loads(path.read_text()))
        self.assertEqual(summary['plain']['combined'],{'correct':23,'wrong':1})
        self.assertEqual(summary['decompose']['combined'],{'correct':19,'unknown':2,'technical_missing':3})


if __name__=='__main__':unittest.main()
