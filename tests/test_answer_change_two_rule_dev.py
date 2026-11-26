import contextlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('two_rule_dev', ROOT / 'scripts/answer_change_two_rule_dev.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.protocol = m.load(m.DESIGN / 'protocol.json')
        self.public = m.load(m.MATERIAL / 'public.json')

    def test_24_ordered_tasks_and_equal_public_material(self):
        plan = m.build_plan(self.protocol, self.public)
        self.assertEqual(len(plan), 24)
        self.assertEqual(len({t['id'] for t in plan}), 24)
        for left, right in zip(plan[::2], plan[1::2], strict=True):
            self.assertEqual(left['case'], right['case'])
            self.assertEqual(left['messages'][0], right['messages'][0])
            l = left['messages'][1]['content'].removesuffix('\n\n' + self.protocol['direct'])
            r = right['messages'][1]['content'].removesuffix('\n\n' + self.protocol['by_version'])
            self.assertEqual(l, r)
            self.assertNotIn(left['case'], l)
            self.assertNotIn('independently_reviewed', l)
            self.assertNotIn('scope_claims', l)

    def test_missing_and_known_date_are_not_mislabeled(self):
        plan = m.build_plan(self.protocol, self.public)
        cases = {c['id']: c for c in self.public['cases']}
        for task in plan:
            text = task['messages'][1]['content']
            case = cases[task['case']]
            self.assertIn(case['facts_and_date_status'], text)
            self.assertIn(case['old_date'], text)
            self.assertIn(case['new_date'], text)
            self.assertIn(case['metadata'], text)
            for e in case['evidence']:
                self.assertIn(e['excerpt'], text)

    def test_invalid_counts_duplicates_or_budget_fail(self):
        with self.assertRaisesRegex(ValueError, 'wrong case count'):
            m.build_plan(self.protocol, {'cases': self.public['cases'][:-1]})
        dup = self.public['cases'][:-1] + [self.public['cases'][0]]
        with self.assertRaisesRegex(ValueError, 'duplicate case'):
            m.build_plan(self.protocol, {'cases': dup})
        with self.assertRaisesRegex(ValueError, 'protocol mismatch'):
            m.build_plan(self.protocol | {'max_new_tokens': 512}, self.public)

    def test_synthetic_complete_and_truncated_runs_preserve_records(self):
        class Sequence:
            def __init__(self, values): self.values = values
            def __getitem__(self, key): return Sequence(self.values[key[1]])
            def tolist(self): return self.values

        class Tokenizer:
            pad_token_id = 0
            def decode(self, tokens, **kwargs): return 'answer'

        class Cuda:
            is_available = staticmethod(lambda: True)
            device_count = staticmethod(lambda: 1)
            is_bf16_supported = staticmethod(lambda: True)
            mem_get_info = staticmethod(lambda i: (20 * 1024**3, 24 * 1024**3))
            get_device_name = staticmethod(lambda i: 'synthetic')

        class Model:
            generation_config = types.SimpleNamespace(eos_token_id=[4], bos_token_id=1)
            truncated = False
            def eval(self): return self
            def generate(self, **kwargs):
                return Sequence([1, 2] + ([3] * m.LIMIT if self.truncated else [3, 4]))

        fake_torch = types.SimpleNamespace(cuda=Cuda(), bfloat16='bf16', long='long',
            tensor=lambda *a, **kw: object(), ones_like=lambda x: x, inference_mode=contextlib.nullcontext)
        fake_transformers = types.SimpleNamespace(
            AutoModelForCausalLM=types.SimpleNamespace(from_pretrained=lambda *a, **kw: Model()),
            GenerationConfig=lambda **kwargs: kwargs)
        plan = m.build_plan(self.protocol, self.public)[:1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack, model = root / 'pack', root / 'model'
            pack.mkdir()
            model.mkdir()
            m.base.write_new(pack / 'manifest.json', {'fixture': True})
            m.base.write_new(model / 'generation_config.json', {'eos_token_id': [4]})
            for truncated in (False, True):
                Model.truncated = truncated
                run = root / ('truncated' if truncated else 'complete')
                with patch.object(m, 'RUN', run), patch.object(m, 'PACK', pack), \
                     patch.object(m.base, 'MODEL', model), \
                     patch.object(m, 'check_prepared', return_value=({'context': 2000}, plan, Tokenizer())), \
                     patch.object(m.base, 'render', return_value=('rendered', [1, 2])), \
                     patch.dict(sys.modules, {'torch': fake_torch, 'transformers': fake_transformers}), \
                     patch.dict('os.environ', {'ANSWER_CHANGE_USER_EXECUTED': '1'}):
                    if truncated:
                        with self.assertRaisesRegex(ValueError, 'non-complete output'):
                            m.collect()
                        self.assertFalse((run / 'seal.json').exists())
                        self.assertEqual(m.load(run / '00.record.json')['status'], 'truncated')
                    else:
                        m.collect()
                        m.verify()
                        (run / '00.record.json').write_text('{}')
                        with self.assertRaisesRegex(ValueError, 'seal mismatch'):
                            m.verify()
                    self.assertTrue((run / '00.attempt.json').exists())
                    with self.assertRaisesRegex(ValueError, 'run exists'):
                        m.collect()


if __name__ == '__main__':
    unittest.main()
