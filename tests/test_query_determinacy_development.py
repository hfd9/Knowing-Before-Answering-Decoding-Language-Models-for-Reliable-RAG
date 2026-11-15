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
import query_determinacy_dev_audit as audit
import query_determinacy_dev_material as material
import query_determinacy_dev_run as run


class FakeTokenizer:
    pad_token_id=0
    eos_token_id=1
    def apply_chat_template(self,messages,tokenize,add_generation_prompt):return messages[0]['content']+'<assistant>'
    def __call__(self,text,add_special_tokens,truncation):return {'input_ids':[ord(c) for c in text]}
    def decode(self,ids,skip_special_tokens):return ''.join(chr(x) for x in ids if x!=1)
    def __len__(self):return 200000


class DevelopmentTests(unittest.TestCase):
    def test_real_material_and_independent_parser(self):
        self.assertEqual(audit.audit()['rows'],72)
        self.assertEqual(material.construct(),[json.loads(s) for s in audit.MATERIAL.read_text(encoding='utf-8').splitlines()])

    def test_tampered_reference_and_world_answers_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'material.jsonl'; original=material.construct()
            for field,value in [('expected','N'),('world_answers',['N','N'])]:
                rows=[dict(r) for r in original];rows[0][field]=value
                path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
                with self.assertRaises(ValueError):audit.audit(path)

    def test_72_simulations_retain_failure_and_do_not_retry(self):
        import torch
        import transformers
        class FakeModel:
            generation_config=SimpleNamespace(bos_token_id=1)
            calls=0
            def eval(self):return self
            def requires_grad_(self,flag):return self
            def generate(self,input_ids,**kwargs):
                self.calls+=1
                tokens=[ord('是')]*384 if self.calls==5 else [ord('否'),1]
                return torch.cat((input_ids,torch.tensor([tokens],dtype=torch.long)),dim=1)
        data=run.inputs();tok=FakeTokenizer(); items=[]
        for row in run.ordered(data):
            text,ids=run.core.render(tok,row['prompt'])
            items.append({'id':row['id'],'prompt_sha256':run.core.digest(row['prompt'].encode()),
                          'rendered_sha256':run.core.digest(text.encode()),'token_ids_sha256':run.core.ids_hash(ids),
                          'input_tokens':len(ids)})
        manifest={'count':72,'items':items,'smoke_count':4,'generation':{'eos_token_ids':[1]}}
        model=FakeModel()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            for name in ('attempts','records','automatic_failures'):(path/name).mkdir()
            (path/'run.lock').touch();run.core.write_new(path/'manifest.json',manifest)
            tensor=torch.tensor
            def cpu_tensor(value,**kwargs):
                kwargs.pop('device',None);return tensor(value,**kwargs)
            with patch.object(run,'RUN',path),patch.object(run,'validate_files'),patch.object(run.core,'verify_device'), \
                 patch.object(transformers.AutoModelForCausalLM,'from_pretrained',return_value=model), \
                 patch.object(torch,'tensor',side_effect=cpu_tensor),patch.object(torch.cuda,'synchronize'), \
                 contextlib.redirect_stdout(io.StringIO()):
                state=run.collect(manifest,tok,data)
                self.assertEqual((state['records'],len(state['technical_failures']),model.calls),(72,1,72))
                self.assertEqual(state['technical_failures'][0]['index'],4)
                self.assertEqual(run.read_state(manifest,tok,data)['state'],'complete_unreviewed')
                (path/'automatic_failures/004.json').unlink()
                with self.assertRaisesRegex(ValueError,'receipt'):run.read_state(manifest,tok,data)

    def test_unfinished_attempt_blocks_and_smoke_failure_stays_blocked(self):
        data=run.inputs();tok=FakeTokenizer();row=run.ordered(data)[0]
        text,ids=run.core.render(tok,row['prompt'])
        item={'id':row['id'],'prompt_sha256':run.core.digest(row['prompt'].encode()),
              'rendered_sha256':run.core.digest(text.encode()),'token_ids_sha256':run.core.ids_hash(ids),'input_tokens':len(ids)}
        manifest={'count':1,'items':[item],'smoke_count':4,'generation':{'eos_token_ids':[1]}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(run,'RUN',Path(tmp)):
            path=Path(tmp)
            for name in ('attempts','records','automatic_failures'):(path/name).mkdir()
            (path/'run.lock').touch();run.core.write_new(path/'manifest.json',manifest)
            ap=path/'attempts/000.json';run.core.write_new(ap,{'index':0,'id':item['id'],'manifest_sha256':run.core.file_hash(path/'manifest.json')})
            with self.assertRaisesRegex(ValueError,'unfinished'):run.read_state(manifest,tok,data)
            tokens=[ord('是')]*384
            run.core.write_new(path/'records/000.json',{'index':0,'id':item['id'],'attempt_sha256':run.core.file_hash(ap),
                'generated_token_ids':tokens,'generated_token_ids_sha256':run.core.ids_hash(tokens),'output':'是'*384})
            run.core.write_new(path/'automatic_failures/000.json',run.receipt(0,item,'truncated_or_unexpected_stop'))
            self.assertEqual(run.read_state(manifest,tok,data)['state'],'blocked_smoke_failure')


if __name__=='__main__':unittest.main()
