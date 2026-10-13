"""CPU checks of evidence provenance, val isolation and interruption recovery."""

import argparse
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import validation_evidence_audit as audit


class Tokenizer:
    def apply_chat_template(self,messages,**kwargs):
        return json.dumps(messages,ensure_ascii=False)+'assistant'

    def __call__(self,text,**kwargs):
        return {'input_ids':list(range(len(text)))}


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.config = audit.e.read_json(audit.CONFIG)
        self.tokenizer = Tokenizer()
        self.row = dict(id='val_1_answer',original_id='val_1',split='val',true_mode='answer',label=0,
                        question='When did Cedar open?', gold_answer='SECRET_GOLD',
                        docs=['Cedar opened in 2001.', 'Cedar opened in 2004.', 'third', 'fourth', '<script>last</script>'])
        self.proposal = dict(semantic_mode='answer',required_facts='Opening year',missing_facts='',
                             reason='The year is supplied.',citations=[dict(doc_id=1,quote='opened in 2001')])

    def record(self,row=None):
        row = row or self.row
        raw = json.dumps(self.proposal)
        prompt = audit.render(row,self.config,self.tokenizer)
        return dict(id=row['id'],original_id=row['original_id'],raw_output=raw,
                    raw_output_sha256=audit.e.text_hash(raw),prompt_sha256=audit.e.text_hash(prompt),
                    input_tokens=len(prompt),generated_tokens=100,hit_output_limit=False,
                    draft=audit.parse_draft(raw,row['docs']))

    def test_model_prompt_has_all_documents_without_labels_or_gold(self):
        text=audit.render(self.row,self.config,self.tokenizer)
        self.assertEqual(text,audit.render(dict(self.row,true_mode='refuse',label=1,gold_answer='OTHER'),self.config,self.tokenizer))
        self.assertNotIn('SECRET_GOLD',text)
        for doc in self.row['docs']:
            self.assertIn(doc,json.loads(text[:-len('assistant')])[1]['content'])

    def test_strict_json_quotes_and_truncation_keep_invalid_unknown(self):
        good=json.dumps(self.proposal)
        self.assertEqual(audit.parse_draft(good,self.row['docs'])['semantic_mode'],'answer')
        cases=['```json\n'+good+'\n```',good+' explanation', '{"semantic_mode":"answer","semantic_mode":"refuse"}']
        for change in [dict(citations=[dict(doc_id=1,quote='invented')]),
                       dict(citations=[dict(doc_id=True,quote='opened in 2001')]),
                       dict(semantic_mode='conflict'),dict(semantic_mode='refuse'),
                       dict(missing_facts='another required premise'),dict(reason='')]:
            cases.append(json.dumps(dict(self.proposal,**change)))
        for raw in cases:
            with self.subTest(raw=raw):
                result=audit.parse_draft(raw,self.row['docs'])
                self.assertEqual(result['semantic_mode'],'unknown')
                self.assertEqual(result['status'],'invalid')
        self.assertEqual(audit.parse_draft(good,self.row['docs'],True)['errors'],['output_limit_without_eos'])
        conflict=dict(self.proposal,semantic_mode='conflict',citations=[dict(doc_id=1,quote='2001'),dict(doc_id=2,quote='2004')])
        self.assertEqual(audit.parse_draft(json.dumps(conflict),self.row['docs'])['semantic_mode'],'conflict')

    def test_sources_read_only_validation_and_reject_changed_data(self):
        rows=[dict(self.row,id='val_1_'+mode,true_mode=mode,label=i) for i,mode in enumerate(audit.e.MODES)]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'data').mkdir();(root/'activations').mkdir()
            path=root/'data/instances_val.jsonl'
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            audit.e.repro.write_json(root/'data/manifest.json',dict(splits={'val':dict(sha256=audit.e.repro.digest_file(path),n_instances=3)}))
            audit.e.repro.write_json(root/'activations/meta_P0_val.json',dict(spec={'fixed':True}))
            args=argparse.Namespace(reference=root,model='/tmp/mock',limit_questions=None)
            with patch.object(audit.e.repro,'feature_spec',return_value={'fixed':True}):
                self.assertEqual(len(audit.sources(args)[0]),3)
                path.write_text(path.read_text()+'\n')
                with self.assertRaises(ValueError):audit.sources(args)
            self.assertFalse((root/'data/instances_test.jsonl').exists())

    def test_blind_packet_does_not_include_drafts_or_published_labels_and_never_overwrites_ratings(self):
        with tempfile.TemporaryDirectory() as directory:
            args=argparse.Namespace(run_dir=Path(directory))
            mapping,digest=audit.prepare_review(args,[self.row],'fixed')
            page=(args.run_dir/'review/public/evidence_blind.html').read_text()
            self.assertNotIn(self.row['id'],page)
            self.assertNotIn('SECRET_GOLD',page)
            self.assertIn('&lt;script&gt;last&lt;/script&gt;',page)
            self.assertNotIn('<script>last</script>',page)
            template=args.run_dir/'review/public/ratings_template.csv'
            ratings=audit.load_ratings(template,mapping,digest,[self.row])
            self.assertEqual(ratings[self.row['id']]['semantic_mode'],'unknown')
            human=args.run_dir/'review/ratings.csv';human.write_text('human work')
            audit.prepare_review(args,[self.row],'fixed')
            self.assertEqual(human.read_text(),'human work')

    def test_human_rating_batch_identity_and_quotes_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            args=argparse.Namespace(run_dir=Path(directory))
            mapping,digest=audit.prepare_review(args,[self.row],'fixed')
            rating=dict.fromkeys(audit.RATING_FIELDS,'')
            rating.update(review_id=next(iter(mapping)),packet_sha256=digest,semantic_mode='answer',
                          reviewer='human',reason='Support read in document 1.',doc_id_1='1',quote_1='opened in 2001')
            path=args.run_dir/'ratings.csv'
            def save(value):path.write_text(audit.csv_text([value],audit.RATING_FIELDS))
            save(rating);self.assertEqual(audit.load_ratings(path,mapping,digest,[self.row])[self.row['id']]['reviewer'],'human')
            for change in [dict(packet_sha256='other'),dict(review_id='other'),dict(reviewer=''),dict(quote_1='invented'),dict(semantic_mode='conflict')]:
                save(dict(rating,**change))
                with self.subTest(change=change),self.assertRaises(ValueError):audit.load_ratings(path,mapping,digest,[self.row])

    def test_checkpoint_rejects_corruption_before_resuming(self):
        spec={'fixed':True};record=self.record()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'predictions.json'
            good=dict(spec=spec,records=[record])
            audit.e.repro.write_json(path,good)
            self.assertEqual(len(audit.cached(path,spec,[self.row],self.config,self.tokenizer)),1)
            for key,value in [('raw_output','changed'),('prompt_sha256','changed'),('generated_tokens',513),
                              ('input_tokens',1),('hit_output_limit',True),('draft',{})]:
                bad=copy.deepcopy(good);bad['records'][0][key]=value
                audit.e.repro.write_json(path,bad)
                with self.subTest(key=key),self.assertRaises(ValueError):audit.cached(path,spec,[self.row],self.config,self.tokenizer)

    def test_legacy_cache_without_per_output_hash_is_bound_to_prior_whole_file_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);baseline=root/'grid/chat8/val/predictions.json'
            audit.e.repro.write_json(baseline,{'legacy':'saved'})
            audit.e.repro.write_json(baseline.parents[2]/'protocol.json',{'fixed':'grid'})
            prior=root/'prior';config=audit.e.read_json(audit.search.PROMPTS)
            protocol=dict(split='val',model='/tmp/mock',selected_ids=[self.row['id']],configuration=config,
                          legacy_validation_sha256=audit.e.repro.digest_file(baseline),
                          legacy_protocol_sha256=audit.e.repro.digest_file(baseline.parents[2]/'protocol.json'))
            audit.e.repro.write_json(prior/'protocol.json',protocol)
            args=argparse.Namespace(prior=prior,baseline=baseline,model='/tmp/mock')
            legacy=dict(id=self.row['id'],original_id=self.row['original_id'],raw_output='refuse',pred_mode='refuse')
            candidate=dict(legacy,raw_output_sha256=audit.e.text_hash('refuse'))
            with patch.object(audit.search,'baseline',return_value=[legacy]),patch.object(audit.search,'cached',return_value=[candidate]):
                methods=audit.prior_methods(args,[self.row],[self.row],self.tokenizer)
                self.assertEqual(len(methods),4)
                baseline.write_text('changed legacy artifact')
                with self.assertRaises(ValueError):audit.prior_methods(args,[self.row],[self.row],self.tokenizer)

    def test_analysis_never_imports_model_proposals_into_explicit_review(self):
        with tempfile.TemporaryDirectory() as directory:
            args=argparse.Namespace(run_dir=Path(directory),ratings=None)
            mapping,digest=audit.prepare_review(args,[self.row],'fixed')
            methods={'legacy':[dict(id=self.row['id'],pred_mode='refuse',raw_output='refuse')]}
            audit.analyze(args,[self.row],[self.record()],methods,mapping,digest,'fixed')
            report=audit.e.read_json(args.run_dir/'reports/diagnosis.json')
            self.assertIsNone(report['separate_review'])
            self.assertEqual(report['model_drafts']['semantic_mode_counts'],{'answer':1})
            args.ratings=args.run_dir/'review/public/ratings_template.csv'
            audit.analyze(args,[self.row],[self.record()],methods,mapping,digest,'fixed')
            report=audit.e.read_json(args.run_dir/'reports/diagnosis.json')
            self.assertEqual(report['separate_review']['semantic_mode_counts'],{'unknown':1})
            self.assertEqual(report['status'],'separate_review_partial_or_ambiguous')
            self.assertEqual(audit.load_ratings(args.ratings,mapping,digest,[self.row])[self.row['id']]['semantic_mode'],'unknown')

    def test_interruption_resumes_saved_prefix_and_complete_cache_needs_no_gpu(self):
        rows=[dict(self.row,id='val_1_'+mode,true_mode=mode,label=i) for i,mode in enumerate(audit.e.MODES)]
        calls=[];failed=[False]
        def generate(model,tok,row,config):
            calls.append(row['id'])
            if len(calls)==2 and not failed[0]:
                failed[0]=True;raise RuntimeError('simulated interruption')
            return self.record(row)
        with tempfile.TemporaryDirectory() as directory:
            args=argparse.Namespace(run_dir=Path(directory),model='/tmp/mock')
            spec={'protocol_sha256':'fixed'}
            with patch.object(audit.search,'assert_gpu_idle') as idle,patch.object(audit.e,'load_model',return_value=object()) as load,patch.object(audit,'generate',side_effect=generate),redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):audit.infer(args,rows,self.config,self.tokenizer,spec)
                self.assertEqual(audit.e.read_json(args.run_dir/'last_failure.json')['saved_outputs'],1)
                records=audit.infer(args,rows,self.config,self.tokenizer,spec)
                self.assertEqual(len(records),3)
                self.assertEqual(calls.count(rows[0]['id']),1)
                idle.reset_mock();load.reset_mock()
                self.assertEqual(len(audit.infer(args,rows,self.config,self.tokenizer,spec)),3)
                idle.assert_not_called();load.assert_not_called()

    def test_smoke_is_structure_gate_and_unknown_remains_in_full_denominator(self):
        record=self.record()
        unknown=dict(record,draft=dict(status='invalid',semantic_mode='unknown',errors=['invalid_json']))
        self.assertEqual(audit.smoke_gate([record,record,unknown],3,self.config)['valid'],2)
        with self.assertRaises(ValueError):audit.smoke_gate([record,unknown,unknown],3,self.config)
        rows=[self.row,dict(self.row,id='val_2_answer')]
        methods={'old':[dict(id=rows[0]['id'],pred_mode='refuse'),dict(id=rows[1]['id'],pred_mode=None)]}
        report=audit.diagnostic_summary(rows,{rows[0]['id']:'answer',rows[1]['id']:'unknown'},methods)
        self.assertEqual(report['population'],2)
        counts=report['prior_method_diagnostics']['old']
        self.assertEqual(counts['full_denominator'],2)
        self.assertEqual(counts['audit_unknown'],1)
        self.assertEqual(counts['invalid_outputs'],1)
        self.assertEqual(counts['refuse_with_audit_answer'],1)


if __name__=='__main__':unittest.main()
