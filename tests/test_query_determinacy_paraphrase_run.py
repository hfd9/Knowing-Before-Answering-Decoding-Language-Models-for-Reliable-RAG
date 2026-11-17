import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import query_determinacy_paraphrase_run as run


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


class RunTests(unittest.TestCase):
    def simulated(self, failure_index):
        import torch
        import transformers
        class FakeModel:
            generation_config = SimpleNamespace(bos_token_id=1)
            calls = 0
            def eval(self): return self
            def requires_grad_(self, flag): return self
            def generate(self, input_ids, **kwargs):
                self.calls += 1
                tokens = [ord('否')] * 384 if self.calls - 1 == failure_index else [ord('是'), 1]
                return torch.cat((input_ids, torch.tensor([tokens], dtype=torch.long)), dim=1)
        data = run.inputs()
        tok = FakeTokenizer()
        items = []
        for row in run.ordered(data):
            text, ids = run.base.core.render(tok, row['prompt'])
            items.append({'id': row['id'], 'prompt_sha256': run.base.core.digest(row['prompt'].encode()),
                          'rendered_sha256': run.base.core.digest(text.encode()),
                          'token_ids_sha256': run.base.core.ids_hash(ids), 'input_tokens': len(ids)})
        manifest = {'count': 96, 'items': items, 'smoke_count': 4, 'generation': {'eos_token_ids': [1]}}
        model = FakeModel()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            for name in ('attempts', 'records', 'automatic_failures'):
                (path / name).mkdir()
            (path / 'run.lock').touch()
            run.base.core.write_new(path / 'manifest.json', manifest)
            tensor = torch.tensor
            def cpu_tensor(value, **kwargs):
                kwargs.pop('device', None)
                return tensor(value, **kwargs)
            with patch.object(run.base, 'RUN', path), patch.object(run.base, 'validate_files'), \
                 patch.object(run.base.core, 'verify_device'), \
                 patch.object(transformers.AutoModelForCausalLM, 'from_pretrained', return_value=model), \
                 patch.object(torch, 'tensor', side_effect=cpu_tensor), patch.object(torch.cuda, 'synchronize'), \
                 contextlib.redirect_stdout(io.StringIO()):
                if failure_index < 4:
                    with self.assertRaisesRegex(ValueError, 'smoke'):
                        run.base.collect(manifest, tok, data)
                    state = run.base.read_state(manifest, tok, data)
                    self.assertEqual(state['state'], 'blocked_smoke_failure')
                    self.assertEqual(model.calls, failure_index + 1)
                else:
                    state = run.base.collect(manifest, tok, data)
                    self.assertEqual((state['records'], model.calls), (96, 96))
                    self.assertEqual(state['state'], 'complete_unreviewed')
                self.assertEqual(len(state['technical_failures']), 1)
                self.assertEqual(state['technical_failures'][0]['index'], failure_index)

    def test_complete_run_preserves_technical_failure(self):
        self.simulated(7)

    def test_smoke_failure_stops(self):
        self.simulated(1)


if __name__ == '__main__':
    unittest.main()
