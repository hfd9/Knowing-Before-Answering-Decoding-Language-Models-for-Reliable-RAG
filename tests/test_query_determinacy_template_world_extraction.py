from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import query_determinacy_template_world_extraction as extraction
import query_determinacy_template_world_replay as replay
import query_determinacy_oracle_run as run


class TemplateWorldExtractionTests(unittest.TestCase):
    def setUp(self):
        self.items=run.inputs()
        self.source=next(r for r in self.items.values() if r['condition']=='dual_sources' and r['family']=='number')
        self.categorical=next(r for r in self.items.values() if r['condition']=='dual_alternatives' and r['family']=='category')

    def test_all_72_source_inputs_reconstruct_cached_branches(self):
        rows,summary=replay.replay()
        self.assertEqual(len(rows),72)
        self.assertEqual(summary['dual_sources']['combined'],{'correct':33,'overreserve':3})
        self.assertEqual(summary['dual_alternatives']['combined'],{'correct':33,'overreserve':3})

    def test_unrecognized_or_nonexhaustive_sources_fail_closed(self):
        prompt=self.source['prompt']
        bad=[prompt.replace('两种情况都有可能','可能还有其他情况'),
             prompt.replace('资料甲称','资料一称'),
             prompt.replace('没有其他信息可区分哪份资料正确','资料乙总是正确'),
             prompt.replace('。\n问题：','。还有一份额外资料。\n问题：')]
        for text in bad:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):extraction.branch_prompts(text)

    def test_atomic_axiom_and_single_values_must_match(self):
        p=self.categorical['prompt']
        with self.assertRaises(ValueError):extraction.branch_prompts(p.replace('不同代码互不相同','不同代码可能相同'))
        a,b=self.source['world_a'],self.source['world_b']
        replacement=self.source['prompt'].replace(f'{b}个单位',f'{a}个单位')
        with self.assertRaises(ValueError):extraction.branch_prompts(replacement)


if __name__=='__main__':unittest.main()
