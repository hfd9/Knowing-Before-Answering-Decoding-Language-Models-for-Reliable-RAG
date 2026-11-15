from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import query_determinacy_oracle_results as results


class OracleResultsTests(unittest.TestCase):
    def test_saved_results_replay_without_losing_denominators(self):
        r=results.analyze()
        self.assertEqual((r['source_files'],r['records'],r['questions'],r['invalid_formats']),(289,144,36,0))
        self.assertEqual(sum(x['n'] for x in r['summary'].values()),36)
        for group in r['summary'].values():
            for method in ('combined','dual_sources','dual_alternatives'):
                self.assertEqual(sum(group[method].values()),group['n'])


if __name__=='__main__':unittest.main()
