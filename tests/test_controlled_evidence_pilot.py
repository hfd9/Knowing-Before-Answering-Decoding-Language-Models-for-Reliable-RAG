"""Matched edits, cache integrity, causal timing and offline pilot integration."""

import argparse
import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import controlled_evidence_materials as m
import controlled_evidence_pilot as p
import verify_controlled_evidence_pilot as verifier


class Scaler:
    def transform(self,x):return x


class Router:
    classes_=np.array([0,1,2])
    def predict_proba(self,x):return np.array([[.2,.6,.2]]*len(x))


class Tokenizer:
    eos_token_id=2
    pad_token_id=0
    labels={'answer':[3],'refuse':[4,5],'conflict':[6]}
    def __call__(self,text,**kwargs):
        if kwargs.get('return_tensors')=='pt':
            import torch
            from transformers import BatchEncoding
            return BatchEncoding(dict(input_ids=torch.tensor([[7,8,9]]),attention_mask=torch.ones((1,3),dtype=torch.long)))
        return dict(input_ids=self.labels.get(text,[7,8,9]))
    def apply_chat_template(self,messages,**kwargs):return json.dumps(messages,ensure_ascii=False)+'assistant'
    def decode(self,tokens,skip_special_tokens=False):
        tokens=list(tokens)
        if skip_special_tokens:tokens=[t for t in tokens if t!=2]
        for word,ids in self.labels.items():
            if tokens==ids:return word
        return 'generated' if tokens else ''


class ControlledEvidenceTests(unittest.TestCase):
    def test_materials_all40_are_matched_balanced_and_have_exact_citations(self):
        spec,rows,judgments,provenance=m.build()
        self.assertEqual(len(rows),40)
        self.assertEqual(len(judgments),40)
        self.assertEqual(len(provenance),10)
        self.assertEqual(sum(len(r['docs']) for r in rows),200)
        lookup={r['id']:r for r in rows}
        for rating in judgments:
            self.assertEqual(rating['semantic_mode'],lookup[rating['id']]['true_mode'])
            for cite in rating['citations']:
                doc=lookup[rating['id']]['docs'][cite['doc_id']-1]
                self.assertEqual(doc[cite['start']:cite['end']],cite['quote'])
        self.assertEqual(m.build()[1],rows)
        for group in provenance:
            self.assertEqual(len(group['source_doc_slots']),3)
            group_rows={r['condition']:r for r in rows if r['original_id']==group['original_id']}
            self.assertEqual(len({r['question'] for r in group_rows.values()}),1)
            for condition in 'ICD':
                reconstructed=copy.deepcopy(group_rows['S']['docs'])
                for slot in range(1,6):
                    changes=[c for c in group['edits_from_S'][condition] if c['doc_id']==slot]
                    for change in reversed(changes):
                        old=reconstructed[slot-1]
                        self.assertEqual(old[change['before_start']:change['before_end']],change['before'])
                        reconstructed[slot-1]=old[:change['before_start']]+change['after']+old[change['before_end']:]
                self.assertEqual(reconstructed,group_rows[condition]['docs'])

    def test_source_and_declarative_edit_tampering_are_rejected(self):
        spec=m.read(m.SPEC)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.jsonl';source.write_text('{}\n')
            with self.assertRaisesRegex(ValueError,'hash'):m.build(source_path=source)
            spec['units'][0]['remove']='not in the target'
            path=Path(tmp)/'spec.json';path.write_text(m.json_text(spec))
            with self.assertRaises(ValueError):m.build(spec_path=path)

    def test_render_keeps_all_documents_and_excludes_labels_and_judgments(self):
        row=m.build()[1][0];tokenizer=Tokenizer()
        for task in ['free_answer','classification']:
            text=p.render(row,task,tokenizer)
            for doc in row['docs']:self.assertIn(doc,json.loads(text[:-9])[1]['content'])
            altered=dict(row,id='HIDDEN_ID',condition='HIDDEN_CONDITION',true_mode='HIDDEN_LABEL',label=99,review='HIDDEN_REVIEW')
            self.assertEqual(text,p.render(altered,task,tokenizer))
            self.assertNotIn('HIDDEN_',text)

    def test_main30_and_control10_and_unknown_denominators_are_separate(self):
        rows=m.build()[1];free=[];labels=[]
        for row in rows:
            prediction=row['true_mode'] if row['condition']!='D' else 'refuse'
            free.append(dict(id=row['id'],original_id=row['original_id'],condition=row['condition'],true_mode=row['true_mode'],
                             probe_pred=prediction,probe_probabilities={mode:.8 if mode==prediction else .1 for mode in p.e.MODES},
                             raw_output='A concrete answer',hit_output_limit=False))
            labels.append(dict(id=row['id'],pred_mode=row['true_mode'],true_mode=row['true_mode']))
        result=p.summarize(rows,free,labels,{})
        self.assertEqual(result['main']['instances'],30)
        self.assertEqual(result['main']['probe']['correct'],30)
        self.assertEqual(result['control']['instances'],10)
        self.assertEqual(result['control']['same_probe_count'],0)
        self.assertEqual(result['unknown_behavior_rows'],40)
        rate=result['main']['behavior']['rates']['all_refuse_substantive_answer_rate']
        self.assertEqual((rate['denominator'],rate['unknown'],rate['lower_bound'],rate['upper_bound']),(10,10,0,1))
        self.assertIsNone(rate['rate'])
        self.assertEqual(result['control']['behavior_invariance']['has_substantive_answer']['unknown_pairs'],10)
        annotations={('chat',r['id']):dict(has_substantive_answer=True) for r in rows if r['condition']=='I'}
        scored=p.summarize(rows,free,labels,annotations)
        self.assertEqual(scored['main']['behavior']['rates']['refuse_probe_refuse_then_answer_rate']['rate'],1)
        self.assertEqual(scored['unknown_behavior_rows'],40)

    def test_smoke_is_technical_only_and_rejects_empty_or_truncated(self):
        rows=[dict(condition=c) for c in 'SICD']
        free=[dict(raw_output='Some answer',ended_with_eos=True,hit_output_limit=False,probe_decision_pre_first_token=True) for _ in rows]
        labels=[dict(pred_mode='refuse',technical_valid=True,strict_format_pass=True,ended_with_eos=True,hit_output_limit=False) for _ in rows]
        self.assertFalse(p.technical_gate(rows,free,labels)['semantic_accuracy_gate'])
        bad=copy.deepcopy(free);bad[0]['raw_output']=''
        with self.assertRaises(ValueError):p.technical_gate(rows,bad,labels)
        bad=copy.deepcopy(free);bad[1]['hit_output_limit']=True
        with self.assertRaises(ValueError):p.technical_gate(rows,bad,labels)

    def test_cached_state_text_identity_and_probe_tampering_fail(self):
        row=m.build()[1][0];tokenizer=Tokenizer();grammar=p.s.LabelGrammar(tokenizer,[2])
        probe=dict(layer=28,scaler=Scaler(),router=Router())
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);p.e.repro.write_json(base/'protocol.json',{})
            h=np.ones((36,2048),dtype=np.float16)
            p.e.save_array(base/'free_answer/features/0000.npy',h)
            record={k:row[k] for k in ['id','original_id','condition','true_mode']}
            record.update(prompt_sha256=p.e.text_hash(p.render(row,'free_answer',tokenizer)),input_tokens=3,
                          generated_token_ids=[3,2],generated_tokens=2,raw_output='answer',raw_output_sha256=p.e.text_hash('answer'),
                          ended_with_eos=True,hit_output_limit=False,feature_file='features/0000.npy',
                          feature_sha256=m.digest(base/'free_answer/features/0000.npy'),**p.predict_probe(probe,h))
            value=dict(spec=p.checkpoint_spec(base,'free_answer'),records=[record])
            path=base/'free_answer/predictions.json';p.e.repro.write_json(path,value)
            self.assertEqual(len(p.cache(base,'free_answer',[row],tokenizer,grammar,probe,'')),1)
            for field,new in [('condition','wrong'),('input_tokens',4),('raw_output','changed'),
                              ('generated_token_ids',[3,2,3]),('probe_pred','answer'),('feature_sha256','bad')]:
                bad=copy.deepcopy(value);bad['records'][0][field]=new;p.e.repro.write_json(path,bad)
                with self.subTest(field=field),self.assertRaises(ValueError):p.cache(base,'free_answer',[row],tokenizer,grammar,probe,'')
            p.e.repro.write_json(path,value);p.e.save_array(base/'free_answer/features/0000.npy',np.zeros_like(h))
            with self.assertRaises(ValueError):p.cache(base,'free_answer',[row],tokenizer,grammar,probe,'')
            classified=dict(record,pred_mode='answer',technical_valid=True,strict_format_pass=True)
            class_value=dict(spec=p.checkpoint_spec(base,'classification'),records=[classified])
            classified['prompt_sha256']=p.e.text_hash(p.render(row,'classification',tokenizer))
            class_path=base/'classification/predictions.json';p.e.repro.write_json(class_path,class_value)
            self.assertEqual(len(p.cache(base,'classification',[row],tokenizer,grammar,probe,'')),1)
            classified['pred_mode']='refuse';p.e.repro.write_json(class_path,class_value)
            with self.assertRaises(ValueError):p.cache(base,'classification',[row],tokenizer,grammar,probe,'')

    def test_actual_tiny_cpu_model_runs_probe_once_before_first_logits(self):
        import torch
        from transformers import Qwen2Config,Qwen2ForCausalLM
        torch.set_num_threads(1)
        model=Qwen2ForCausalLM(Qwen2Config(vocab_size=16,hidden_size=16,intermediate_size=32,num_hidden_layers=3,
                            num_attention_heads=2,num_key_value_heads=1,max_position_embeddings=256,
                            eos_token_id=2,pad_token_id=0,bos_token_id=1)).eval()
        events=[];original=p.predict_probe
        def predict(probe,states):events.append('probe');return original(probe,states)
        handle=model.lm_head.register_forward_pre_hook(lambda *args:events.append('logits'))
        try:
            with patch.object(p,'predict_probe',side_effect=predict),patch('torch.cuda.reset_peak_memory_stats'),\
                 patch('torch.cuda.synchronize'),patch('torch.cuda.max_memory_allocated',return_value=0):
                record,h=p.generate_free(model,Tokenizer(),m.build()[1][0],dict(layer=1,scaler=Scaler(),router=Router()),p.s.LabelGrammar(Tokenizer(),[2]))
            self.assertEqual(events[0],'probe');self.assertEqual(events.count('probe'),1)
            self.assertEqual(h.shape,(3,16));self.assertTrue(record['probe_decision_pre_first_token'])
        finally:handle.remove()

    def test_launcher_stops_before_full_if_smoke_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts=Path(tmp)/'scripts';scripts.mkdir()
            launch=scripts/'run_controlled_evidence_pilot_review.sh';launch.write_bytes((ROOT/'scripts'/launch.name).read_bytes())
            (scripts/'run_controlled_evidence_pilot.sh').write_text('#!/bin/sh\nexit 7\n')
            result=subprocess.run(['sh',str(launch)],capture_output=True,text=True)
            self.assertEqual(result.returncode,7);self.assertIn('full run was not started',result.stderr)
            self.assertFalse((Path(tmp)/'runs/qwen2.5-3b-controlled-evidence-pilot-v1/launch/full.log').exists())

    def test_busy_gpu_guard_aborts_before_loading_and_missing_smoke_blocks_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=argparse.Namespace(run_dir=Path(tmp),model='unused')
            with patch.object(p.s,'assert_gpu_idle',side_effect=RuntimeError('GPU busy PID123')),\
                 patch.object(p.e,'load_model',side_effect=AssertionError('Must not load')):
                with self.assertRaisesRegex(RuntimeError,'PID123'):p.infer(args,[{}],None,None,None)
            self.assertEqual(m.read(Path(tmp)/'last_failure.json')['stage'],'model_load_or_gpu_guard')
            with patch.object(p,'SMOKE',Path(tmp)/'missing'):
                with self.assertRaisesRegex(ValueError,'smoke launcher'):p.require_full_smoke(args,{},None,None,None)

    def test_real_tokenizer_probe_offline_smoke_export_replay_and_resume(self):
        # Synthetic outputs only, in a temporary directory. Never loads the3B model.
        model_path=m.read(p.PROBE_SOURCE/'protocol.json')['model']
        with tempfile.TemporaryDirectory() as tmp:
            args=argparse.Namespace(run_dir=Path(tmp)/'pilot',model=model_path,smoke=True,annotations=None)
            rows,probe,tokenizer,grammar,protocol,_=p.prepare(args)
            self.assertEqual(verifier.verify(args.run_dir,prepared_only=True)['status'],'prepared_verified_not_started')
            def generated(row,task):
                raw='Evidence is insufficient.' if task=='free_answer' else 'refuse'
                tokens=tokenizer(raw,add_special_tokens=False)['input_ids']+[grammar.eos_ids[0]]
                record={k:row[k] for k in ['id','original_id','condition','true_mode']}
                record.update(prompt_sha256=p.e.text_hash(p.render(row,task,tokenizer)),
                              input_tokens=len(p.e.encode(tokenizer,p.render(row,task,tokenizer),'chat')['input_ids']),
                              raw_output=raw,raw_output_sha256=p.e.text_hash(raw),generated_token_ids=tokens,generated_tokens=len(tokens),
                              ended_with_eos=True,hit_output_limit=False,elapsed_seconds=0.,peak_allocated_gib=0.,
                              completed_at='2026-10-18T00:00:00+00:00')
                return record
            def free_result(model,tok,row,pr,gr):
                h=np.ones((36,2048),dtype=np.float16)
                return dict(generated(row,'free_answer'),**p.predict_probe(pr,h)),h
            def class_result(model,tok,row,instruction,gr):
                return dict(generated(row,'classification'),pred_mode='refuse',technical_valid=True,strict_format_pass=True)
            with patch.object(p.s,'assert_gpu_idle'),patch.object(p.e,'load_model',return_value=object()),\
                 patch.object(p,'generate_free',side_effect=free_result),patch.object(p.s,'generate',side_effect=class_result):
                p.infer(args,rows,probe,tokenizer,grammar)
            report=p.analyze(args,rows,probe,tokenizer,grammar)
            self.assertEqual(report['main']['instances'],3);self.assertEqual(report['control']['instances'],1)
            self.assertEqual(report['unknown_behavior_rows'],4)
            self.assertEqual(verifier.verify(args.run_dir)['status'],'verified_complete')
            with patch.object(p,'SMOKE',args.run_dir):
                p.require_full_smoke(args,dict(protocol,smoke=False),probe,tokenizer,grammar)
                changed=copy.deepcopy(protocol);changed['implementation_sha256']['scripts/controlled_evidence_pilot.py']='bad'
                with self.assertRaises(ValueError):p.require_full_smoke(args,changed,probe,tokenizer,grammar)
            hashes={str(path.relative_to(args.run_dir)):m.digest(path) for path in args.run_dir.rglob('*') if path.is_file()}
            with patch.object(p.e,'load_model',side_effect=AssertionError('Cache resume must not load model')):
                p.infer(args,rows,probe,tokenizer,grammar)
            p.analyze(args,rows,probe,tokenizer,grammar)
            self.assertEqual(hashes,{str(path.relative_to(args.run_dir)):m.digest(path) for path in args.run_dir.rglob('*') if path.is_file()})
            template=args.run_dir/'review/annotations_template.csv'
            with template.open(newline='') as f:values=list(csv.DictReader(f))
            values[0].update(has_substantive_answer='yes',reviewer='synthetic_test_only')
            with (args.run_dir/'annotations.csv').open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(values[0]),lineterminator='\r\n');writer.writeheader();writer.writerows(values)
            p.analyze(args,rows,probe,tokenizer,grammar)
            self.assertEqual(len(list((args.run_dir/'reports/history').rglob('pilot.json'))),1)
            self.assertEqual(len(list((args.run_dir/'review/annotation_snapshots').glob('*.csv'))),1)
            self.assertEqual(next((args.run_dir/'review/annotation_snapshots').glob('*.csv')).read_bytes(),
                             (args.run_dir/'annotations.csv').read_bytes())
            self.assertEqual(verifier.verify(args.run_dir)['status'],'verified_complete')
            path=args.run_dir/'materials/inputs.json';path.write_text('[]')
            with self.assertRaisesRegex(ValueError,'Material differs'):verifier.verify(args.run_dir)


if __name__=='__main__':unittest.main()
