from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import query_determinacy_model_world_replay as replay
import query_determinacy_oracle_run as oracle
import query_determinacy_world_extract_results as results


class ModelWorldReplayTests(unittest.TestCase):
    def test_results_and_two_endpoints_conserve_planned_denominators(self):
        self.assertEqual(results.analyze()['records'],24)
        rows,summary=replay.replay()
        self.assertEqual((len(rows),len({r['world_extraction_id'] for r in rows})),(72,24))
        for group in summary.values():
            self.assertEqual(group['n'],36)
            self.assertEqual(sum(group['combined'].values()),36)
            self.assertEqual(sum(group['direct'].values()),36)
        failed=[r for r in rows if r['reason']=='extraction_invalid']
        self.assertEqual(len(failed),3)
        self.assertEqual({r['case'] for r in failed},{'H05'})

    def test_generated_branches_use_predicted_values_without_gold_correction(self):
        item=next(x for x in oracle.inputs().values() if x['case']=='H01' and x['condition']=='dual_sources')
        branches=replay.prompts_from_candidates(item['prompt'],['999','888'])
        self.assertIn('确定为999个单位',branches[0])
        self.assertIn('确定为888个单位',branches[1])
        with self.assertRaises(ValueError):replay.prompts_from_candidates(item['prompt'],['999','999'])
        with self.assertRaises(ValueError):replay.prompts_from_candidates(item['prompt'],['99个单位','88'])


if __name__=='__main__':unittest.main()
