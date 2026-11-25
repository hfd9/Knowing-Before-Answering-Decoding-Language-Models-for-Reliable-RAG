import importlib.util
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('followup', ROOT / 'scripts/answer_change_7b_followup.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FollowupPlanTests(unittest.TestCase):
    def fake_rows(self):
        rows = []
        for i in range(8):
            case = 'ssa-S0' if i < 4 else 'spouse-D0'
            task = {'id': f'{case}/route{i}', 'case': case, 'route': f'route{i}',
                    'messages': [{'role': 'user', 'content': 'original'}]}
            rows.append(({'task': task, 'input_token_ids': [1, 2]},
                         {'output': f'first {i}', 'generated_token_ids': [3, 4]}))
        return rows

    def test_each_date_starts_from_same_original_history(self):
        plan = m.make_plan(self.fake_rows())
        self.assertEqual(len(plan), 16)
        self.assertEqual(len({x['id'] for x in plan}), 16)
        for old, new in zip(plan[::2], plan[1::2], strict=True):
            self.assertEqual(old['messages'][:-1], new['messages'][:-1])
            self.assertEqual(old['first_generated_ids'], new['first_generated_ids'])
            self.assertEqual([old['day'], new['day']], list(m.DAYS))
            self.assertEqual(old['kind'], 'unsolicited_date')
            self.assertEqual([x['role'] for x in old['messages']], ['user', 'assistant', 'user'])
            self.assertEqual(len(old['messages']), 3)

    def test_invalid_date_case_and_incomplete_source_are_rejected(self):
        with self.assertRaises(ValueError):
            m.followup('ssa-S0', '2030-01-01')
        with self.assertRaises(ValueError):
            m.followup('unknown', m.DAYS[0])
        with self.assertRaises(ValueError):
            m.make_plan(self.fake_rows()[:-1])

    def test_prefix_mismatch_and_context_overflow_are_rejected(self):
        task = m.make_plan(self.fake_rows())[0]
        old_render = m.first.render
        try:
            m.first.render = lambda tokenizer, messages: ('rendered', [1, 2, 3, 4, 5])
            self.assertEqual(m.render_checked(None, task, 1000)[1], [1, 2, 3, 4, 5])
            with self.assertRaisesRegex(ValueError, 'context exceeded'):
                m.render_checked(None, task, 512)
            m.first.render = lambda tokenizer, messages: ('rendered', [1, 2, 9, 4, 5])
            with self.assertRaisesRegex(ValueError, 'token history mismatch'):
                m.render_checked(None, task, 1000)
        finally:
            m.first.render = old_render

    def test_synthetic_collection_preserves_truncation_and_refuses_existing_run(self):
        import contextlib
        import json
        import tempfile
        import types

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
            truncated = True
            def eval(self): return self
            def generate(self, **kwargs):
                return Sequence([1, 2] + ([3] * m.LIMIT if self.truncated else [3, 4]))

        fake_torch = types.SimpleNamespace(cuda=Cuda(), bfloat16='bf16', long='long',
            tensor=lambda *a, **kw: object(), ones_like=lambda x: x, inference_mode=contextlib.nullcontext)
        fake_transformers = types.SimpleNamespace(
            AutoModelForCausalLM=types.SimpleNamespace(from_pretrained=lambda *a, **kw: Model()),
            GenerationConfig=lambda **kwargs: kwargs)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack, model, run = root / 'pack', root / 'model', root / 'run'
            pack.mkdir()
            model.mkdir()
            m.first.write_new(pack / 'manifest.json', {'fixture': True})
            m.first.write_new(model / 'generation_config.json', {'eos_token_id': [4]})
            task = m.make_plan(self.fake_rows())[0]
            with patch.object(m, 'RUN', run), patch.object(m, 'PACK', pack), \
                 patch.object(m.first, 'MODEL', model), \
                 patch.object(m, 'check_prepared', return_value=({'context': 1000}, [task], Tokenizer())), \
                 patch.object(m, 'render_checked', return_value=('rendered', [1, 2])), \
                 patch.dict(sys.modules, {'torch': fake_torch, 'transformers': fake_transformers}), \
                 patch.dict('os.environ', {'ANSWER_CHANGE_USER_EXECUTED': '1'}):
                with self.assertRaisesRegex(ValueError, 'non-complete output'):
                    m.collect()
                self.assertEqual(json.loads((run / '00.record.json').read_text())['status'], 'truncated')
                self.assertTrue((run / '00.attempt.json').exists())
                self.assertFalse((run / 'seal.json').exists())
                with self.assertRaisesRegex(ValueError, 'run exists'):
                    m.collect()
            Model.truncated = False
            run = root / 'complete'
            with patch.object(m, 'RUN', run), patch.object(m, 'PACK', pack), \
                 patch.object(m.first, 'MODEL', model), \
                 patch.object(m, 'check_prepared', return_value=({'context': 1000}, [task], Tokenizer())), \
                 patch.object(m, 'render_checked', return_value=('rendered', [1, 2])), \
                 patch.dict(sys.modules, {'torch': fake_torch, 'transformers': fake_transformers}), \
                 patch.dict('os.environ', {'ANSWER_CHANGE_USER_EXECUTED': '1'}):
                m.collect()
                m.verify()
                (run / '00.record.json').write_text('{}')
                with self.assertRaisesRegex(ValueError, 'seal mismatch'):
                    m.verify()


if __name__ == '__main__':
    unittest.main()
