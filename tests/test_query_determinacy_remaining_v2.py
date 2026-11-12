import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_pilot as core
import query_determinacy_remaining_v2 as v2


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


class RemainingTests(unittest.TestCase):
    def test_build_excludes_only_original_first(self):
        items = [{'id': f'id{i:03d}', 'input_tokens': 10} for i in range(144)]
        old = {'schema': 'original', 'items': items, 'count': 144,
               'generation': {'max_new_tokens': 128}, 'implementation_sha256': {}}
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'old.json'
            archive.write_bytes(core.canonical(old))
            with patch.object(v2, 'V1_ARCHIVE', archive), patch.object(v2, 'verify_v1', return_value=old), \
                 patch.object(core, 'build_manifest', return_value=old):
                new = v2.build_manifest()
        self.assertEqual([x['id'] for x in new['items']], [x['id'] for x in items[1:]])
        self.assertEqual(new['original_run']['attempted_id'], 'id000')
        self.assertEqual(new['generation']['max_new_tokens'], 384)

    def test_143_fake_outputs_and_truncation_stop(self):
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

        tok = FakeTokenizer()
        data = {f'id{i:03d}': f'题{i}' for i in range(1, 144)}
        items = []
        for item_id, prompt in data.items():
            rendered, ids = core.render(tok, prompt)
            items.append({'id': item_id, 'prompt_sha256': core.digest(prompt.encode()),
                          'rendered_sha256': core.digest(rendered.encode()),
                          'token_ids_sha256': core.ids_hash(ids), 'input_tokens': len(ids)})
        manifest = {'count': 143, 'items': items, 'generation': {'eos_token_ids': [1]}}
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            (run / 'attempts').mkdir()
            (run / 'records').mkdir()
            (run / 'run.lock').touch()
            core.write_new(run / 'manifest.json', manifest)
            tensor = torch.tensor

            def cpu_tensor(value, **kwargs):
                kwargs.pop('device', None)
                return tensor(value, **kwargs)

            with patch.object(v2, 'RUN', run), patch.object(core, 'validate_files'), \
                 patch.object(core, 'verify_device'), \
                 patch.object(transformers.AutoModelForCausalLM, 'from_pretrained', return_value=FakeModel()), \
                 patch.object(torch, 'tensor', side_effect=cpu_tensor), patch.object(torch.cuda, 'synchronize'), \
                 contextlib.redirect_stdout(io.StringIO()):
                result = v2.collect(manifest, tok, data)
                self.assertEqual((result['records'], result['attempts']), (143, 143))
                self.assertEqual(result['original_truncated_unscored'], 1)
                self.assertEqual(v2.read_state(manifest, tok, data)['state'], 'complete_unreviewed')
                record_path = run / 'records/000.json'
                record = json.loads(record_path.read_text())
                record['generated_token_ids'] = [ord('是')] * 384
                record['generated_token_ids_sha256'] = core.ids_hash(record['generated_token_ids'])
                record['output'] = tok.decode(record['generated_token_ids'], skip_special_tokens=True)
                record_path.write_bytes(core.canonical(record))
                with self.assertRaisesRegex(ValueError, 'truncated'):
                    v2.read_state(manifest, tok, data)
                self.assertTrue(record_path.exists())


if __name__ == '__main__':
    unittest.main()
