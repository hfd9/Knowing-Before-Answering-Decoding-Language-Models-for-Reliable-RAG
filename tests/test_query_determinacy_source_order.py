import contextlib
import io
import json
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import query_determinacy_source_order as source


class FakeTokenizer:
    pad_token_id=0
    eos_token_id=1
    def apply_chat_template(self,messages,tokenize,add_generation_prompt):return messages[0]['content']+'<assistant>'
    def __call__(self,text,add_special_tokens,truncation):return {'input_ids':[ord(c) for c in text]}
    def decode(self,ids,skip_special_tokens):return ''.join(chr(x) for x in ids if x!=1)
    def __len__(self):return 200000


def extract(prompt):
    m=re.search(r'资料([甲乙])称(.*?)为(.*?)；资料([甲乙])称其为(.*?)。',prompt)
    if not m:raise ValueError('cannot parse source pair')
    return {m[1]:m[3],m[4]:m[5]},m[1],m[2]


class SourceOrderTests(unittest.TestCase):
    def test_source_transformations_preserve_intended_worlds_and_query(self):
        old={r['id']:r for r in map(json.loads,source.original.MATERIAL.read_text(encoding='utf-8').splitlines())}
        for row in source.inputs().values():
            prior=old[row['source_id']];before,first,subject=extract(prior['prompt']);after,newfirst,newsubject=extract(row['prompt'])
            self.assertEqual(subject,newsubject)
            self.assertEqual(set(before.values()),set(after.values()))
            self.assertEqual(prior['prompt'].splitlines()[2:],row['prompt'].splitlines()[2:])
            self.assertEqual(prior['expected'],row['expected'])
            if row['source_variant']=='swap_labels':
                self.assertEqual(after,{'甲':before['乙'],'乙':before['甲']})
                self.assertNotEqual(first,newfirst)
            else:
                self.assertEqual(after,before)
                self.assertNotEqual(first,newfirst)

    def test_tampered_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'material.jsonl';rows=source.transform();rows[0]['expected']='Y'
            path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
            with patch.object(source,'MATERIAL',path):
                with self.assertRaisesRegex(ValueError,'mismatch'):source.inputs()

    def test_sixteen_simulated_generations_keep_technical_failure(self):
        import torch
        import transformers
        class FakeModel:
            generation_config=SimpleNamespace(bos_token_id=1)
            calls=0
            def eval(self):return self
            def requires_grad_(self,flag):return self
            def generate(self,input_ids,**kwargs):
                self.calls+=1;tokens=[ord('否')]*384 if self.calls==8 else [ord('是'),1]
                return torch.cat((input_ids,torch.tensor([tokens],dtype=torch.long)),dim=1)
        data=source.inputs();tok=FakeTokenizer();items=[]
        for row in source.ordered(data):
            text,ids=source.base.core.render(tok,row['prompt'])
            items.append({'id':row['id'],'prompt_sha256':source.base.core.digest(row['prompt'].encode()),
                          'rendered_sha256':source.base.core.digest(text.encode()),'token_ids_sha256':source.base.core.ids_hash(ids),
                          'input_tokens':len(ids)})
        manifest={'count':16,'items':items,'smoke_count':4,'generation':{'eos_token_ids':[1]}}
        model=FakeModel()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            for name in ('attempts','records','automatic_failures'):(path/name).mkdir()
            (path/'run.lock').touch();source.base.core.write_new(path/'manifest.json',manifest)
            tensor=torch.tensor
            def cpu_tensor(value,**kwargs):kwargs.pop('device',None);return tensor(value,**kwargs)
            with patch.object(source.base,'RUN',path),patch.object(source.base,'validate_files'), \
                 patch.object(source.base.core,'verify_device'), \
                 patch.object(transformers.AutoModelForCausalLM,'from_pretrained',return_value=model), \
                 patch.object(torch,'tensor',side_effect=cpu_tensor),patch.object(torch.cuda,'synchronize'), \
                 contextlib.redirect_stdout(io.StringIO()):
                state=source.base.collect(manifest,tok,data)
                self.assertEqual((state['records'],len(state['technical_failures']),model.calls),(16,1,16))
                self.assertEqual(state['technical_failures'][0]['index'],7)
                self.assertEqual(source.base.read_state(manifest,tok,data)['state'],'complete_unreviewed')


if __name__=='__main__':unittest.main()
