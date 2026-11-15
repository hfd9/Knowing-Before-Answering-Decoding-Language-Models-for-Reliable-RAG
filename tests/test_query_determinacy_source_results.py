from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import query_determinacy_source_results as result


class SourceResultsTests(unittest.TestCase):
    def test_complete_case_mapping_and_prior_correction(self):
        x=result.analyze()
        self.assertEqual((x['new_source_files'],x['old_source_files'],len(x['cases'])),(34,388,8))
        self.assertEqual(x['cases']['G04']['original_alternatives'],'X')
        self.assertEqual(x['counts']['category/original_alternatives'],{'U':3,'X':1})
        self.assertEqual(x['counts']['category/swap_labels'],{'N':1,'T':1,'X':2})


if __name__=='__main__':unittest.main()
