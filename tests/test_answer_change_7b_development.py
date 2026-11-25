import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('answer_change_7b_development',
                                              ROOT / 'scripts/answer_change_7b_development.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ExposedDevelopmentPlanTests(unittest.TestCase):
    def setUp(self):
        self.public = json.loads(module.SOURCE.read_text())

    def test_two_methods_have_identical_case_and_evidence(self):
        plan = module.tasks(self.public)
        self.assertEqual(len(plan), 8)
        for i in range(0, len(plan), 2):
            a, b = plan[i:i + 2]
            self.assertEqual(a['case'], b['case'])
            self.assertEqual(a['messages'][0], b['messages'][0])
            first = a['messages'][1]['content'].removesuffix('\n\n' + module.DIRECT)
            second = b['messages'][1]['content'].removesuffix('\n\n' + module.BY_VERSION)
            self.assertEqual(first, second)
            self.assertIn('Author-prepared scope statements', first)
            self.assertNotIn('ANSWER_Y', first)
            self.assertNotIn('ANSWER_N', first)
            self.assertNotIn('ASK_DATE', first)

    def test_rejects_wrong_scope_source_or_quote(self):
        self.public['profiles']['ssa']['scope_claims']['claims'][0]['quote'] = 'not present'
        with self.assertRaisesRegex(ValueError, 'scope quote differs'):
            module.tasks(self.public)

    def test_missing_case_is_not_silently_dropped(self):
        self.public['cases'] = [c for c in self.public['cases'] if c['id'] != 'ssa-D0']
        with self.assertRaisesRegex(ValueError, 'missing exposed case'):
            module.tasks(self.public)

    def test_existing_attempt_is_never_overwritten(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'attempt.json'
            module.write_new(path, {'first': True})
            with self.assertRaises(FileExistsError):
                module.write_new(path, {'first': False})
            self.assertEqual(json.loads(path.read_text()), {'first': True})

    def test_verify_accepts_consistent_fixture_and_rejects_tampering(self):
        import tempfile

        class Tokenizer:
            def apply_chat_template(self, messages, **kwargs):
                return 'rendered'

            def __call__(self, text, **kwargs):
                return {'input_ids': [1, 2]}

            def decode(self, tokens, **kwargs):
                return 'answer'

        plan = [{'id': 'example/direct', 'messages': [{'role': 'user', 'content': 'x'}]}]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = root / 'run'
            pack = root / 'pack'
            run.mkdir()
            pack.mkdir()
            module.write_new(pack / 'manifest.json', {'fixture': True})
            module.write_new(run / 'start.json', {'manifest_sha256': module.sha(pack / 'manifest.json')})
            module.write_new(run / '00.attempt.json', {'task': plan[0], 'rendered_prompt': 'rendered',
                                                       'input_token_ids': [1, 2]})
            module.write_new(run / '00.record.json', {'id': 'example/direct', 'output': 'answer',
                'generated_token_ids': [3, 4], 'eos_token_ids': [4], 'status': 'complete', 'seconds': 1})
            module.write_new(run / 'seal.json', {p.name: module.sha(p) for p in run.iterdir()})
            with patch.object(module, 'RUN', run), patch.object(module, 'PACK', pack), \
                 patch.object(module, 'check_prepared', return_value=({}, plan, Tokenizer())):
                module.verify()
                (run / '00.record.json').write_text('{}')
                with self.assertRaisesRegex(ValueError, 'seal mismatch'):
                    module.verify()

    def test_synthetic_collection_seals_success_and_preserves_truncation(self):
        import contextlib
        import sys
        import tempfile
        import types

        class Sequence:
            def __init__(self, values):
                self.values = values

            def __getitem__(self, key):
                return Sequence(self.values[key[1]])

            def tolist(self):
                return self.values

        class Tokenizer:
            pad_token_id = 0

            def apply_chat_template(self, messages, **kwargs):
                return 'rendered'

            def __call__(self, text, **kwargs):
                return {'input_ids': [1, 2]}

            def decode(self, ids, **kwargs):
                return 'answer'

        class Cuda:
            is_available = staticmethod(lambda: True)
            device_count = staticmethod(lambda: 1)
            is_bf16_supported = staticmethod(lambda: True)
            mem_get_info = staticmethod(lambda index: (20 * 1024**3, 24 * 1024**3))
            get_device_name = staticmethod(lambda index: 'synthetic')

        class FakeModel:
            generation_config = types.SimpleNamespace(eos_token_id=[4], bos_token_id=1)
            truncated = False

            def eval(self):
                return self

            def generate(self, **kwargs):
                return Sequence([1, 2] + ([3] * module.LIMIT if self.truncated else [3, 4]))

        fake_model = FakeModel()
        fake_torch = types.SimpleNamespace(cuda=Cuda(), bfloat16='bf16', long='long',
                     tensor=lambda *a, **kw: object(), ones_like=lambda x: x,
                     inference_mode=contextlib.nullcontext)
        fake_transformers = types.SimpleNamespace(
            AutoModelForCausalLM=types.SimpleNamespace(from_pretrained=lambda *a, **kw: fake_model),
            GenerationConfig=lambda **kwargs: kwargs)
        plan = [{'id': 'test/direct', 'messages': [{'role': 'user', 'content': 'x'}]}]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pack = root / 'pack'
            pack.mkdir()
            module.write_new(pack / 'manifest.json', {'fixture': True})
            with patch.object(module, 'PACK', pack), patch.object(module, 'RUN', root / 'ok'), \
                 patch.object(module, 'check_prepared', return_value=({'context': 1000}, plan, Tokenizer())), \
                 patch.dict(sys.modules, {'torch': fake_torch, 'transformers': fake_transformers}), \
                 patch.dict('os.environ', {'ANSWER_CHANGE_USER_EXECUTED': '1'}):
                module.collect()
                self.assertTrue((root / 'ok/seal.json').exists())
            fake_model.truncated = True
            with patch.object(module, 'PACK', pack), patch.object(module, 'RUN', root / 'truncated'), \
                 patch.object(module, 'check_prepared', return_value=({'context': 1000}, plan, Tokenizer())), \
                 patch.dict(sys.modules, {'torch': fake_torch, 'transformers': fake_transformers}), \
                 patch.dict('os.environ', {'ANSWER_CHANGE_USER_EXECUTED': '1'}):
                with self.assertRaisesRegex(ValueError, 'non-complete output'):
                    module.collect()
                self.assertTrue((root / 'truncated/00.attempt.json').exists())
                self.assertTrue((root / 'truncated/00.record.json').exists())
                self.assertFalse((root / 'truncated/seal.json').exists())


if __name__ == '__main__':
    unittest.main()
