"""Matched support edits, restricted values, complete denominators and safe prefill lifecycle."""

import argparse
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import probe_support_expression as s
from test_controlled_evidence_pilot import Tokenizer, Scaler, Router


class SupportExpressionTests(unittest.TestCase):
    def test_50_cells_80_exact_replacements_keep_backgrounds_and_questions(self):
        spec,rows,edits,reviews=s.build()
        self.assertEqual((len(rows),len(edits),len(reviews)),(50,80,10))
        self.assertEqual(sum(r['source'] is not None for r in rows),10)
        self.assertEqual(sum(r['original_id'] in spec['smoke_bases'] for r in rows),12)
        self.assertEqual(rows,s.build()[1])
        index={r['id']:r for r in rows}
        for row in rows:
            base=next(r for r in rows if r['original_id']==row['original_id'] and r['cell']=='B')
            self.assertEqual(row['question'],base['question'])
            self.assertEqual(row['native_target_slots'],base['native_target_slots'])
            self.assertEqual(len(row['docs']),5)
            for i,text in enumerate(row['docs'],1):
                if i not in row['native_target_slots']:self.assertEqual(text,base['docs'][i-1])
        for edit in edits:
            row=index[edit['id']];base=next(r for r in rows if r['original_id']==row['original_id'] and r['cell']=='B')
            self.assertEqual(base['docs'][edit['doc_slot']-1][edit['start']:edit['end']],edit['before'])
            self.assertEqual(row['docs'][edit['doc_slot']-1],edit['after'])
            self.assertEqual(edit['after'][edit['quote_start']:edit['quote_end']],edit['positive_quote'])
        self.assertFalse(any(r['independent_gold'] for r in reviews))

    def test_value_switch_changes_only_same_literal_in_both_targets_four_bases(self):
        spec,rows,_,_=s.build();units={u['base_id']:u for u in spec['units']}
        for altered in [r for r in rows if r['value_level']=='alternate']:
            unit=units[altered['original_id']]
            original=next(r for r in rows if r['original_id']==altered['original_id'] and r['wording_level']==altered['wording_level'] and r['negative_level']=='positive' and r['value_level']=='authored')
            self.assertIn(altered['original_id'],['val_81','val_35','val_31','val_86'])
            for slot in altered['native_target_slots']:
                self.assertEqual(original['docs'][slot-1].replace(unit['authored_value'],unit['alternate_value']),altered['docs'][slot-1])
                self.assertNotIn(unit['authored_value'],altered['docs'][slot-1])
        self.assertFalse(any(r['value_level']=='alternate' for r in rows if r['original_id']=='val_3'))

    def test_negative_suffix_is_exact_addition_to_both_exhaustive_positive_cores(self):
        spec,rows,_,_=s.build();units={u['base_id']:u for u in spec['units']}
        negatives=[r for r in rows if r['negative_level']=='negative'];self.assertEqual(len(negatives),12)
        for row in negatives:
            original=next(r for r in rows if r['original_id']==row['original_id'] and r['wording_level']==row['wording_level'] and r['negative_level']=='positive' and r['value_level']=='authored')
            for slot in row['native_target_slots']:
                self.assertEqual(row['docs'][slot-1],original['docs'][slot-1]+' '+units[row['original_id']]['redundant_negative'])
            self.assertEqual(row['value_level'],'authored')

    def test_report_variable_support9_groups60_pairs_and_no_accuracy(self):
        spec,rows,_,_=s.build()
        records=[dict(r,input_tokens=100,origin='reused_endpoint' if r['source'] else 'new_forward',probe_pred='answer',probe_probabilities={'answer':.8,'refuse':.1,'conflict':.1}) for r in rows]
        report=s.summarize(spec,rows,records)
        self.assertEqual(len(report['paired']),60)
        self.assertEqual([v['n_pairs'] for v in report['contrasts'].values()],[10,6,4,6,6,4,4,10,10])
        self.assertEqual((report['new_forwards'],report['reused_endpoints']),(40,10))
        self.assertNotIn('accuracy',report)
        with self.assertRaises(ValueError):s.summarize(spec,rows,records[:-1])
        smoke_rows=[r for r in rows if r['original_id'] in spec['smoke_bases']]
        smoke_records=[r for r in records if r['original_id'] in spec['smoke_bases']]
        self.assertEqual(s.summarize(spec,smoke_rows,smoke_records)['cells'],12)

    def test_metadata_does_not_leak_to_prompt(self):
        row=s.build()[1][1];altered=dict(row,source={'SECRET':True},id='SECRET',cell='SECRET',wording_level='SECRET',value_level='SECRET',negative_level='SECRET')
        self.assertEqual(s.d.prompt(row,Tokenizer()),s.d.prompt(altered,Tokenizer()))

    def test_train_only_literal_counts_do_not_score_semantics(self):
        spec=s.build()[0];summary=s.train_lexical_summary(spec)
        self.assertEqual((summary['instances'],summary['base_questions']),(600,200))
        self.assertEqual(summary['source_sha256'],s.m.digest(s.TRAIN))
        self.assertEqual(summary['term_counts']['Christian Wulff']['answer']['document_rows'],0)
        self.assertEqual(summary['term_counts']['not']['answer']['document_rows'],107)
        self.assertIn('Does not establish proposition support',summary['limitation'])

    def test_gpu_busy_stops_before_load_and_full_requires_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=argparse.Namespace(run_dir=Path(tmp),model='unused',smoke=True)
            with patch.object(s.p.s,'assert_gpu_idle',side_effect=RuntimeError('GPU busy')),patch.object(s.e,'load_model',side_effect=AssertionError('Must not load')):
                with self.assertRaisesRegex(RuntimeError,'busy'):s.run(args,{},[dict(id='one',source=None)],None,None,{})
            self.assertEqual(s.e.read_json(Path(tmp)/'last_failure.json')['id'],'one')
            args.smoke=False
            with patch.object(s,'require_smoke',side_effect=ValueError('No valid smoke')),patch.object(s.e,'load_model',side_effect=AssertionError('Must not load')):
                with self.assertRaisesRegex(ValueError,'No valid smoke'):s.run(args,{},[],None,None,{})

    def test_real_tokenizer_frozen_probe_cache_gate_and_model_free_resume(self):
        model=s.e.read_json(s.f.DEFAULT/'protocol.json')['model']
        with tempfile.TemporaryDirectory() as tmp:
            args=argparse.Namespace(run_dir=Path(tmp),model=model,smoke=True)
            spec,rows,probe,tokenizer,_=s.prepare(args)
            self.assertEqual(len(rows),12);records=[]
            for row in rows:
                states=s.d.source_state(row,tokenizer,model) if row['source'] else np.ones((36,2048),dtype=np.float16)
                rel=f'features/{len(records):04d}.npy';s.e.save_array(args.run_dir/rel,states)
                record={k:row[k] for k in ['id','original_id','question_level','document_level','cell',*s.AXES]}
                record.update(origin='new_forward',capture_phase='decoder_prefill_without_generation',prompt_sha256=s.e.text_hash(s.d.prompt(row,tokenizer)),input_tokens=len(s.e.encode(tokenizer,s.d.prompt(row,tokenizer),'chat')['input_ids']),feature_file=rel,feature_sha256=s.m.digest(args.run_dir/rel),**s.d.prediction(probe,states))
                records.append(record)
            path=args.run_dir/'states.json';value=dict(protocol_sha256=s.m.digest(args.run_dir/'protocol.json'),records=records);s.e.repro.write_json(path,value)
            self.assertEqual(len(s.cache(args,rows,probe,tokenizer)),12)
            gate=s.gate(args,spec,rows,records,probe,tokenizer)
            self.assertEqual((len(gate['bridges']),gate['semantic_accuracy_gate']),(2,False))
            before={str(p.relative_to(args.run_dir)):p.read_bytes() for p in args.run_dir.rglob('*') if p.is_file()}
            s.prepare(args,write=False)
            self.assertEqual(before,{str(p.relative_to(args.run_dir)):p.read_bytes() for p in args.run_dir.rglob('*') if p.is_file()})
            with patch.object(s.e,'load_model',side_effect=AssertionError('Must not load on complete resume')):
                self.assertEqual(len(s.run(args,spec,rows,probe,tokenizer,{})),12)
            for key,bad_value in [('wording_level','WRONG'),('negative_level','WRONG'),('value_level','WRONG'),('probe_pred','WRONG'),('origin','reused_endpoint')]:
                bad=copy.deepcopy(value);bad['records'][0][key]=bad_value;s.e.repro.write_json(path,bad)
                with self.subTest(key=key),self.assertRaises(ValueError):s.cache(args,rows,probe,tokenizer)
            s.e.repro.write_json(path,value)
            i=next(i for i,r in enumerate(rows) if r['source']);feature=args.run_dir/records[i]['feature_file'];s.e.save_array(feature,np.load(feature)*2)
            with self.assertRaisesRegex(ValueError,'bridge failed'):s.gate(args,spec,rows,records,probe,tokenizer)
            (args.run_dir/'materials/semantic_review.json').write_text('[]')
            with self.assertRaisesRegex(ValueError,'artifact differs'):s.prepare(args,write=False)

    def test_launcher_stops_before_full_on_failed_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts=Path(tmp)/'scripts';scripts.mkdir()
            launcher=scripts/'run_probe_support_expression_review.sh';launcher.write_bytes((ROOT/'scripts'/launcher.name).read_bytes())
            (scripts/'run_probe_support_expression.sh').write_text('#!/bin/sh\nexit 7\n')
            result=subprocess.run(['sh',str(launcher)],capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertFalse((Path(tmp)/'runs/qwen2.5-3b-probe-support-expression-v1/launch/full.log').exists())


if __name__=='__main__':unittest.main()
