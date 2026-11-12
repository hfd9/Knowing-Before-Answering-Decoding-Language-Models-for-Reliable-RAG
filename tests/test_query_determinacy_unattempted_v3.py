import contextlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_pilot as core
import query_determinacy_unattempted_v3 as v3


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


class ContinuationTests(unittest.TestCase):
    def test_manifest_excludes_every_attempted_item(self):
        items = [{'id': f'id{i:03d}', 'input_tokens': 10} for i in range(143)]
        old = {'items': items, 'count': 143, 'generation': {'max_new_tokens': 384},
               'implementation_sha256': {}}
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'old.json'
            archive.write_bytes(core.canonical(old))
            with patch.object(v3, 'snapshot_v2', return_value=(old, {'test': 'hash'})), \
                 patch.object(v3.prior, 'build_manifest', return_value=old), \
                 patch.object(v3.prior, 'ARCHIVE', archive):
                result = v3.build_manifest()
        self.assertEqual([x['id'] for x in result['items']], [x['id'] for x in items[16:]])
        self.assertEqual(len(result['prior_v2']['attempted_ids']), 16)
        self.assertEqual(result['count'], 127)

    def test_stop_review_continue_without_retry_and_replay_127(self):
        import torch
        import transformers

        class FakeModel:
            generation_config = SimpleNamespace(bos_token_id=1)
            calls = 0

            def eval(self):
                return self

            def requires_grad_(self, flag):
                return self

            def generate(self, input_ids, **kwargs):
                self.calls += 1
                generated = [ord('是')] * 384 if self.calls == 1 else [ord('否'), 1]
                return torch.cat((input_ids, torch.tensor([generated])), dim=1)

        model = FakeModel()
        tok = FakeTokenizer()
        data = {f'id{i:03d}': f'题{i}' for i in range(127)}
        items = []
        for item_id, prompt in data.items():
            text, ids = core.render(tok, prompt)
            items.append({'id': item_id, 'prompt_sha256': core.digest(prompt.encode()),
                          'rendered_sha256': core.digest(text.encode()),
                          'token_ids_sha256': core.ids_hash(ids), 'input_tokens': len(ids)})
        manifest = {'count': 127, 'items': items, 'generation': {'eos_token_ids': [1]}}
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            for name in ('attempts', 'records', 'decisions'):
                (run / name).mkdir()
            (run / 'run.lock').touch()
            core.write_new(run / 'manifest.json', manifest)
            tensor = torch.tensor

            def cpu_tensor(value, **kwargs):
                kwargs.pop('device', None)
                return tensor(value, **kwargs)

            with patch.object(v3, 'RUN', run), patch.object(core, 'validate_files'), \
                 patch.object(core, 'verify_device'), \
                 patch.object(transformers.AutoModelForCausalLM, 'from_pretrained', return_value=model), \
                 patch.object(torch, 'tensor', side_effect=cpu_tensor), patch.object(torch.cuda, 'synchronize'), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, 'technical failure saved'):
                    v3.collect(manifest, tok, data)
                state = v3.read_state(manifest, tok, data)
                self.assertEqual((state['state'], state['records']), ('blocked_technical_failure', 1))
                with self.assertRaisesRegex(ValueError, 'unreviewed technical failure'):
                    v3.collect(manifest, tok, data)
                v3.acknowledge(state)
                result = v3.collect(manifest, tok, data)
                self.assertEqual((result['state'], result['records'], result['reviewed_failures']),
                                 ('complete_unreviewed', 127, 1))
                self.assertEqual(model.calls, 127)
                receipt = run / 'decisions/000.json'
                receipt.write_text('{}')
                with self.assertRaisesRegex(ValueError, 'receipt mismatch'):
                    v3.read_state(manifest, tok, data)


if __name__ == '__main__':
    unittest.main()
