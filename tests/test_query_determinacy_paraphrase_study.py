import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import query_determinacy_paraphrase_study as study


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.items = {x['id']: x for x in study.build()}
        self.cache = study.cached_branches()
        self.direct = next(x for x in self.items.values() if x['kind'] == 'direct' and x['case'] == 'H01')

    def test_planned_counts_and_correct_reversed_cache(self):
        self.assertEqual(sum(x['kind'] == 'extract' for x in self.items.values()), 24)
        self.assertEqual(sum(x['kind'] == 'direct' for x in self.items.values()), 72)
        bg = self.items[self.direct['background_id']]
        forward = study.resolve(json.dumps(bg['expected']), self.direct['prompt'], self.cache)
        reversed_ = study.resolve(json.dumps(bg['expected'][::-1]), self.direct['prompt'], self.cache)
        self.assertEqual(forward['reason'], 'cached_branches')
        self.assertEqual(forward['code'], reversed_['code'])

    def test_failing_extraction_and_cache_are_not_filled_with_reference(self):
        p = self.direct['prompt']
        self.assertEqual(study.resolve('[1,2]', p, self.cache)['reason'], 'extraction_invalid')
        self.assertEqual(study.resolve('[]', p, self.cache, complete=False)['code'], 'T')
        self.assertEqual(study.resolve('["999", "888"]', p, self.cache)['reason'], 'branch_cache_miss')
        self.assertEqual(study.resolve('["x", "y"]', p, self.cache)['reason'], 'branch_input_invalid')
        bg = self.items[self.direct['background_id']]
        branches = study.branch.branch_prompts(p, bg['expected'])
        mutated = dict(self.cache, **{branches[0]: '无法确定'})
        self.assertEqual(study.resolve(json.dumps(bg['expected']), p, mutated)['code'], 'X')

    def test_planned_denominator_and_failure_fanout(self):
        records = {key: {'output': json.dumps(item['expected']) if item['kind'] == 'extract' else '是'}
                   for key, item in self.items.items()}
        bg = self.direct['background_id']
        records[bg]['output'] = '[1,2]'
        with patch.object(study, 'cached_branches', return_value=self.cache):
            rows, summary = study.evaluate(self.items, records, {self.direct['id']})
        self.assertEqual(len(rows), 72)
        self.assertEqual(sum(r['combined']['reason'] == 'extraction_invalid' for r in rows), 3)
        self.assertEqual(next(r for r in rows if r['id'] == self.direct['id'])['direct'], 'T')
        for item in summary['by_condition'].values():
            self.assertEqual(item['n'], 36)
            self.assertEqual(sum(item['combined'].values()), 36)
            self.assertEqual(sum(item['direct'].values()), 36)
        self.assertEqual(sum(item['n'] for item in summary['extraction'].values()), 24)
        self.assertEqual(sum(item['n'] for item in summary['by_condition_query'].values()), 72)


if __name__ == '__main__':
    unittest.main()
