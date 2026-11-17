import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import query_determinacy_model_world_replay as old
import query_determinacy_oracle_run as oracle
import query_determinacy_paraphrase_branch_candidate as candidate
import query_determinacy_world_extract_parser as parser
import query_determinacy_world_paraphrase_material as material


class ParaphraseBranchCandidateTests(unittest.TestCase):
    def test_all_exposed_questions_match_existing_branch_prompts(self):
        count = 0
        for row in material.build():
            for item in oracle.inputs().values():
                if item['case'] != row['case'] or item['condition'] != row['condition']:
                    continue
                lines = item['prompt'].splitlines()
                lines[1] = row['prompt'].splitlines()[1]
                self.assertEqual(candidate.branch_prompts('\n'.join(lines), row['expected']),
                                 old.prompts_from_candidates(item['prompt'], row['expected']))
                count += 1
        self.assertEqual(count, 72)

    def test_predictions_not_corrected_and_unrecognized_inputs_rejected(self):
        row = next(x for x in material.build() if x['case'] == 'H01' and x['condition'] == 'dual_sources')
        item = next(x for x in oracle.inputs().values() if x['case'] == row['case'] and x['condition'] == row['condition'])
        lines = item['prompt'].splitlines()
        lines[1] = row['prompt'].splitlines()[1]
        prompt = '\n'.join(lines)
        branches = candidate.branch_prompts(prompt, ['999', '888'])
        self.assertIn('确定为999个单位', branches[0])
        self.assertIn('确定为888个单位', branches[1])
        with self.assertRaises(ValueError):
            candidate.branch_prompts(prompt.replace('二者均有可能', '只有甲可能'), ['999', '888'])
        with self.assertRaises(ValueError):
            candidate.branch_prompts(prompt, ['999', '999'])
        with self.assertRaises(ValueError):
            candidate.branch_prompts(prompt, ['999个单位', '888'])
        self.assertEqual(parser.parse('[999, 888]'), ('invalid', None))
        cache = {item['prompt'] for item in oracle.inputs().values()}
        self.assertTrue(all(branch not in cache for branch in branches))


if __name__ == '__main__':
    unittest.main()
