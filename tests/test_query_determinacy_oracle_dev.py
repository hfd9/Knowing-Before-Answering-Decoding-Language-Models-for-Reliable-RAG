import contextlib
import io
import itertools
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import query_determinacy_oracle_audit as audit
import query_determinacy_oracle_evaluate as evaluator
import query_determinacy_oracle_parser as parser
import query_determinacy_oracle_run as run


class FakeTokenizer:
    pad_token_id=0
    eos_token_id=1
    def apply_chat_template(self,messages,tokenize,add_generation_prompt):return messages[0]['content']+'<assistant>'
    def __call__(self,text,add_special_tokens,truncation):return {'input_ids':[ord(c) for c in text]}
    def decode(self,ids,skip_special_tokens):return ''.join(chr(x) for x in ids if x!=1)
    def __len__(self):return 200000


class OracleDevelopmentTests(unittest.TestCase):
    def test_material_and_exact_parser(self):
        self.assertEqual(audit.audit(),{'count':144,'cases':12,'questions':36})
        for text,expected in [('是','Y'),(' 否。 ','N'),('无法确定！','U'),('答案是：是','X'),('是但不确定','X'),('','X')]:
            self.assertEqual(parser.parse(text),expected)
        self.assertEqual(parser.parse('是',technical_complete=False),'T')

    def test_all_branch_states_propagate(self):
        for a,b in itertools.product('YNUXT',repeat=2):
            result=parser.combine(a,b)
            if 'T' in (a,b):self.assertEqual(result,'T')
            elif a not in 'YN' or b not in 'YN':self.assertEqual(result,'X')
            elif a==b:self.assertEqual(result,a)
            else:self.assertEqual(result,'U')

    def test_full_evaluation_and_failed_branch(self):
        data=run.inputs();words={'Y':'是','N':'否','U':'无法确定'}
        records={key:{'id':key,'output':words[row['expected']]} for key,row in data.items()}
        rows,summary=evaluator.evaluate(data,records,set())
        self.assertEqual(len(rows),36)
        self.assertEqual(sum(x['n'] for x in summary.values()),36)
        self.assertTrue(all(x['combined_class']=='correct' for x in rows))
        one=next(row for row in rows if row['query']=='split')
        records[one['single_a_id']]['output']='是但不确定'
        changed,_=evaluator.evaluate(data,records,set())
        self.assertEqual(next(r for r in changed if r['case']==one['case'] and r['query']==one['query'])['combined'],'X')
        failed,_=evaluator.evaluate(data,records,{one['single_b_id']})
        self.assertEqual(next(r for r in failed if r['case']==one['case'] and r['query']==one['query'])['combined'],'T')

    def test_144_simulated_generations_and_failure_journal(self):
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
        data=run.inputs();tok=FakeTokenizer();items=[]
        for row in run.base.ordered(data):
            text,ids=run.base.core.render(tok,row['prompt'])
            items.append({'id':row['id'],'prompt_sha256':run.base.core.digest(row['prompt'].encode()),
                          'rendered_sha256':run.base.core.digest(text.encode()),'token_ids_sha256':run.base.core.ids_hash(ids),
                          'input_tokens':len(ids)})
        manifest={'count':144,'items':items,'smoke_count':4,'generation':{'eos_token_ids':[1]}}
        model=FakeModel()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            for name in ('attempts','records','automatic_failures'):(path/name).mkdir()
            (path/'run.lock').touch();run.base.core.write_new(path/'manifest.json',manifest)
            tensor=torch.tensor
            def cpu_tensor(value,**kwargs):kwargs.pop('device',None);return tensor(value,**kwargs)
            with patch.object(run.base,'RUN',path),patch.object(run.base,'validate_files'), \
                 patch.object(run.base.core,'verify_device'), \
                 patch.object(transformers.AutoModelForCausalLM,'from_pretrained',return_value=model), \
                 patch.object(torch,'tensor',side_effect=cpu_tensor),patch.object(torch.cuda,'synchronize'), \
                 contextlib.redirect_stdout(io.StringIO()):
                state=run.base.collect(manifest,tok,data)
                self.assertEqual((state['records'],len(state['technical_failures']),model.calls),(144,1,144))
                self.assertEqual(state['technical_failures'][0]['index'],7)
                self.assertEqual(run.base.read_state(manifest,tok,data)['state'],'complete_unreviewed')


if __name__=='__main__':unittest.main()
