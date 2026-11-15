from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import query_determinacy_fresh_results as result


class FreshResultsTests(unittest.TestCase):
    def test_counts_preserve_uncertainty_and_technical_failures(self):
        self.assertEqual(result.category({'reference':'U','commitment':'N'}),'unsupported_choice')
        self.assertEqual(result.category({'reference':'N','commitment':'U'}),'overreserve')
        self.assertEqual(result.category({'reference':'U','commitment':'X'}),'unknown')
        self.assertEqual(result.category({'reference':'Y','commitment':'T'}),'technical_missing')

    def test_full_run_and_pair_denominators(self):
        x=result.analyze()
        self.assertEqual((x['source_files'],x['review_rows'],x['technical_failures'],x['paired_inputs']),(388,192,3,96))
        for name,counts in x['pair_transitions_plain_to_decompose'].items():
            self.assertEqual(sum(counts.values()),{'single':48,'dual_determinate':32,'dual_split':16}[name])

if __name__=='__main__':unittest.main()
