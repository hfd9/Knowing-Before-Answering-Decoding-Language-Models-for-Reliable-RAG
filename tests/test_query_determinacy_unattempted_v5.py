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
import query_determinacy_unattempted_v5 as v5

core = v5.core


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


class AutomaticContinuationTests(unittest.TestCase):
    def test_manifest_excludes_prior_attempts(self):
        items = [{'id': f'id{i:03d}', 'input_tokens': 10} for i in range(127)]
        old = {'items': items, 'count': 127, 'generation': {'max_new_tokens': 384},
               'implementation_sha256': {}}
        with patch.object(v5, 'snapshot_previous', return_value=(old, {'manifest': 'hash'})):
            result = v5.build_manifest()
        self.assertEqual([x['id'] for x in result['items']], [x['id'] for x in items[4:]])
        self.assertEqual(len(result['prior_v4']['attempted_ids']), 4)
        self.assertEqual(result['count'], 123)

    def test_123_generations_auto_classify_two_failures_without_retry(self):
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
                generated = ([ord('是')] * 384 if self.calls == 1 else
                             [] if self.calls == 3 else [ord('否'), 1])
                return torch.cat((input_ids, torch.tensor([generated], dtype=torch.long)), dim=1)

        model, tok = FakeModel(), FakeTokenizer()
        data = {f'id{i:03d}': f'题{i}' for i in range(123)}
        items = []
        for item_id, prompt in data.items():
            text, ids = core.render(tok, prompt)
            items.append({'id': item_id, 'prompt_sha256': core.digest(prompt.encode()),
                          'rendered_sha256': core.digest(text.encode()),
                          'token_ids_sha256': core.ids_hash(ids), 'input_tokens': len(ids)})
        manifest = {'count': 123, 'items': items, 'generation': {'eos_token_ids': [1]}}
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp)
            for name in ('attempts', 'records', 'automatic_failures'):
                (run / name).mkdir()
            (run / 'run.lock').touch()
            core.write_new(run / 'manifest.json', manifest)
            tensor = torch.tensor

            def cpu_tensor(value, **kwargs):
                kwargs.pop('device', None)
                return tensor(value, **kwargs)

            with patch.object(v5, 'RUN', run), patch.object(core, 'validate_files'), \
                 patch.object(core, 'verify_device'), \
                 patch.object(transformers.AutoModelForCausalLM, 'from_pretrained', return_value=model), \
                 patch.object(torch, 'tensor', side_effect=cpu_tensor), patch.object(torch.cuda, 'synchronize'), \
                 contextlib.redirect_stdout(io.StringIO()):
                result = v5.collect(manifest, tok, data)
                self.assertEqual((result['records'], result['technically_complete'], len(result['technical_failures'])), (123, 121, 2))
                self.assertEqual([x['status'] for x in result['technical_failures']], ['truncated_or_unexpected_stop', 'empty'])
                self.assertEqual(model.calls, 123)
                self.assertEqual(v5.read_state(manifest, tok, data)['state'], 'complete_unreviewed')
                (run / 'automatic_failures/000.json').unlink()
                with self.assertRaisesRegex(ValueError, 'lacks automatic receipt'):
                    v5.read_state(manifest, tok, data)


if __name__ == '__main__':
    unittest.main()
