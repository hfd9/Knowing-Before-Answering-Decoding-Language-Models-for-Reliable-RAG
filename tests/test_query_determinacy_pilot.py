import importlib.util
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_material_audit as audit
import query_determinacy_pilot as pilot


class FakeTokenizer:
    pad_token_id = 0
    eos_token_id = 1

    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        return messages[0]['content'] + '<assistant>'

    def __call__(self, text, add_special_tokens, truncation):
        return {'input_ids': [ord(c) for c in text]}

    def decode(self, ids, skip_special_tokens):
        return ''.join(chr(x) for x in ids if x != 1)

    def __len__(self):
        return 200000


class MaterialTests(unittest.TestCase):
    @unittest.skipUnless(audit.MATERIAL.is_dir(), 'user-provided material directory is not available')
    def test_reference_and_pair_audit(self):
        result = audit.audit()
        self.assertEqual(result['questions'], 36)
        self.assertEqual(result['dual_pairs'], 36)
        self.assertEqual(result['single_source_checks'], 72)
        self.assertEqual(result['question_outcomes'], {'是': 12, '否': 12, '无法唯一确定': 12})

    def test_numeric_direction_and_boundary(self):
        text = '\n'.join([audit.DUAL_PREFIX, '来源甲：物体的重量登记值为18千克。',
                          '来源乙：物体的重量登记值为22千克。', '问题：物体的重量是否大于20千克？'])
        self.assertEqual(audit.branch_answers(text, '数值比较')[1], {'甲': '否', '乙': '是'})
        with self.assertRaisesRegex(ValueError, 'boundary'):
            audit.branch_answers(text.replace('20千克？', '18千克？'), '数值比较')
        with self.assertRaisesRegex(ValueError, 'another field'):
            audit.branch_answers(text.replace('问题：物体的重量', '问题：别的物体的重量'), '数值比较')

    @unittest.skipUnless(audit.MATERIAL.is_dir(), 'user-provided material directory is not available')
    def test_wrong_reference_is_detected_without_changing_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / 'materials'
            shutil.copytree(audit.MATERIAL, copied)
            key = copied / 'key.csv'
            text = key.read_text(encoding='utf-8-sig')
            self.assertIn(',是,是,是', text)
            key.write_text(text.replace(',是,是,是', ',是,是,否', 1), encoding='utf-8')
            with patch.object(audit, 'MATERIAL', copied):
                with self.assertRaisesRegex(ValueError, 'reference answer mismatch'):
                    audit.audit()


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = pilot.RUN
        pilot.RUN = Path(self.temp.name)
        for name in ('attempts', 'records'):
            (pilot.RUN / name).mkdir()
        (pilot.RUN / 'run.lock').touch()
        self.tok = FakeTokenizer()
        self.data = {'id1': '题目'}
        text, tokens = pilot.render(self.tok, self.data['id1'])
        self.manifest = {'count': 1, 'generation': {'eos_token_ids': [1]},
                         'items': [{'id': 'id1', 'prompt_sha256': pilot.digest('题目'.encode()),
                                    'rendered_sha256': pilot.digest(text.encode()),
                                    'token_ids_sha256': pilot.ids_hash(tokens), 'input_tokens': len(tokens)}]}
        pilot.write_new(pilot.RUN / 'manifest.json', self.manifest)

    def tearDown(self):
        pilot.RUN = self.old
        self.temp.cleanup()

    def attempt(self):
        path = pilot.RUN / 'attempts/000.json'
        pilot.write_new(path, {'index': 0, 'id': 'id1', 'manifest_sha256': pilot.file_hash(pilot.RUN / 'manifest.json')})
        return path

    def record(self, attempt, tokens):
        pilot.write_new(pilot.RUN / 'records/000.json', {'index': 0, 'id': 'id1',
                        'attempt_sha256': pilot.file_hash(attempt), 'generated_token_ids': tokens,
                        'generated_token_ids_sha256': pilot.ids_hash(tokens),
                        'output': self.tok.decode(tokens, skip_special_tokens=True)})

    def test_empty_prefix_and_valid_completion(self):
        self.assertEqual(pilot.read_state(self.manifest, self.tok, self.data)['state'], 'valid_prefix')
        attempt = self.attempt()
        self.record(attempt, [ord('是'), 1])
        self.assertEqual(pilot.read_state(self.manifest, self.tok, self.data)['state'], 'complete_unreviewed')

    def test_unfinished_attempt_blocks(self):
        self.attempt()
        with self.assertRaisesRegex(ValueError, 'unfinished attempt'):
            pilot.read_state(self.manifest, self.tok, self.data)

    def test_truncation_blocks_without_deletion(self):
        attempt = self.attempt()
        self.record(attempt, [ord('是')])
        with self.assertRaisesRegex(ValueError, 'truncated'):
            pilot.read_state(self.manifest, self.tok, self.data)
        self.assertTrue((pilot.RUN / 'records/000.json').exists())

    def test_changed_output_is_rejected(self):
        attempt = self.attempt()
        self.record(attempt, [ord('是'), 1])
        path = pilot.RUN / 'records/000.json'
        record = json.loads(path.read_text())
        record['output'] = '否'
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'token decoding'):
            pilot.read_state(self.manifest, self.tok, self.data)

    def test_cpu_fake_collection_writes_and_replays_journal(self):
        import torch
        import transformers

        class FakeModel:
            generation_config = SimpleNamespace(bos_token_id=1)

            def eval(self):
                return self

            def requires_grad_(self, flag):
                return self

            def generate(self, input_ids, **kwargs):
                return torch.cat((input_ids, torch.tensor([[ord('是'), 1]])), dim=1)

        tensor = torch.tensor

        def cpu_tensor(value, **kwargs):
            kwargs.pop('device', None)
            return tensor(value, **kwargs)

        with patch.object(pilot, 'validate_files'), patch.object(pilot, 'verify_device'), \
             patch.object(transformers.AutoModelForCausalLM, 'from_pretrained', return_value=FakeModel()), \
             patch.object(torch, 'tensor', side_effect=cpu_tensor), patch.object(torch.cuda, 'synchronize'):
            result = pilot.collect(self.manifest, self.tok, self.data)
        self.assertEqual(result['state'], 'complete_unreviewed')
        self.assertEqual(pilot.read_state(self.manifest, self.tok, self.data)['records'], 1)

    def test_all_144_fake_outputs_complete_and_replay(self):
        import torch
        import transformers

        class FakeModel:
            generation_config = SimpleNamespace(bos_token_id=1)

            def eval(self):
                return self

            def requires_grad_(self, flag):
                return self

            def generate(self, input_ids, **kwargs):
                return torch.cat((input_ids, torch.tensor([[ord('是'), 1]])), dim=1)

        self.data = {f'id{i:03d}': f'题{i}' for i in range(144)}
        self.manifest['count'] = 144
        self.manifest['items'] = []
        for item_id, prompt in self.data.items():
            text, tokens = pilot.render(self.tok, prompt)
            self.manifest['items'].append({'id': item_id, 'prompt_sha256': pilot.digest(prompt.encode()),
                                           'rendered_sha256': pilot.digest(text.encode()),
                                           'token_ids_sha256': pilot.ids_hash(tokens), 'input_tokens': len(tokens)})
        (pilot.RUN / 'manifest.json').write_bytes(pilot.canonical(self.manifest))
        tensor = torch.tensor

        def cpu_tensor(value, **kwargs):
            kwargs.pop('device', None)
            return tensor(value, **kwargs)

        with patch.object(pilot, 'validate_files'), patch.object(pilot, 'verify_device'), \
             patch.object(transformers.AutoModelForCausalLM, 'from_pretrained', return_value=FakeModel()), \
             patch.object(torch, 'tensor', side_effect=cpu_tensor), patch.object(torch.cuda, 'synchronize'), \
             contextlib.redirect_stdout(io.StringIO()):
            result = pilot.collect(self.manifest, self.tok, self.data)
        self.assertEqual((result['records'], result['attempts'], result['state']), (144, 144, 'complete_unreviewed'))
        self.assertEqual(pilot.read_state(self.manifest, self.tok, self.data)['records'], 144)


if __name__ == '__main__':
    unittest.main()
