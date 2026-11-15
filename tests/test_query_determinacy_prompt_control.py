import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import query_determinacy_prompt_control as control


class FakeTokenizer:
    pad_token_id=0
    eos_token_id=1
    def apply_chat_template(self,messages,tokenize,add_generation_prompt):return messages[0]['content']+'<assistant>'
    def __call__(self,text,add_special_tokens,truncation):return {'input_ids':[ord(c) for c in text]}
    def decode(self,ids,skip_special_tokens):return ''.join(chr(x) for x in ids if x!=1)
    def __len__(self):return 200000


class PromptControlTests(unittest.TestCase):
    def test_variants_preserve_all_prior_fields_and_only_replace_suffix(self):
        original={x['id']:x for x in map(json.loads,control.OLD_MATERIAL.read_text(encoding='utf-8').splitlines())}
        transformed=control.inputs()
        self.assertEqual(len(transformed),144)
        for row in transformed.values():
            before=original[row['source_id']]
            self.assertEqual(row['prompt'],before['prompt'][:-len(control.OLD_SUFFIX)]+control.SUFFIXES[row['instruction_variant']])
            for key in ('case','family','query','condition','world_a','world_b','world_answers','expected'):
                self.assertEqual(row[key],before[key])
        self.assertEqual({r['source_id'] for r in transformed.values()},set(original))

    def test_changed_prompt_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'material.jsonl';rows=control.rows();rows[0]['prompt']+='篡改'
            p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
            with patch.object(control,'MATERIAL',p):
                with self.assertRaisesRegex(ValueError,'does not match'):control.inputs()

    def test_simulated_144_runs_preserve_failure_and_never_retry(self):
        import torch
        import transformers
        class FakeModel:
            generation_config=SimpleNamespace(bos_token_id=1)
            calls=0
            def eval(self):return self
            def requires_grad_(self,flag):return self
            def generate(self,input_ids,**kwargs):
                self.calls+=1
                tokens=[ord('否')]*384 if self.calls==7 else [ord('是'),1]
                return torch.cat((input_ids,torch.tensor([tokens],dtype=torch.long)),dim=1)
        data=control.inputs();tok=FakeTokenizer();items=[]
        for row in control.base.ordered(data):
            text,ids=control.base.core.render(tok,row['prompt'])
            items.append({'id':row['id'],'prompt_sha256':control.base.core.digest(row['prompt'].encode()),
                          'rendered_sha256':control.base.core.digest(text.encode()),'token_ids_sha256':control.base.core.ids_hash(ids),
                          'input_tokens':len(ids)})
        manifest={'count':144,'items':items,'smoke_count':4,'generation':{'eos_token_ids':[1]}}
        model=FakeModel()
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)
            for name in ('attempts','records','automatic_failures'):(run/name).mkdir()
            (run/'run.lock').touch();control.base.core.write_new(run/'manifest.json',manifest)
            tensor=torch.tensor
            def cpu_tensor(value,**kwargs):kwargs.pop('device',None);return tensor(value,**kwargs)
            with patch.object(control.base,'RUN',run),patch.object(control.base,'validate_files'), \
                 patch.object(control.base.core,'verify_device'), \
                 patch.object(transformers.AutoModelForCausalLM,'from_pretrained',return_value=model), \
                 patch.object(torch,'tensor',side_effect=cpu_tensor),patch.object(torch.cuda,'synchronize'), \
                 contextlib.redirect_stdout(io.StringIO()):
                state=control.base.collect(manifest,tok,data)
                self.assertEqual((state['records'],len(state['technical_failures']),model.calls),(144,1,144))
                self.assertEqual(state['technical_failures'][0]['index'],6)
                self.assertEqual(control.base.read_state(manifest,tok,data)['state'],'complete_unreviewed')


if __name__=='__main__':unittest.main()
