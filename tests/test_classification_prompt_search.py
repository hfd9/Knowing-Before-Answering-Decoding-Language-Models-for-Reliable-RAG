"""Selection safeguards, cache integrity and independent-review gates; CPU only."""

import copy
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import classification_prompt_search as search


class Tokenizer:
    def apply_chat_template(self, messages, **kwargs):
        return json.dumps(messages, ensure_ascii=False) + 'assistant'


class PromptSearchTests(unittest.TestCase):
    def setUp(self):
        self.config = search.e.read_json(search.PROMPTS)
        self.row = dict(id='val_1_answer', original_id='val_1', question='Which year?',
                        true_mode='answer', label=0, gold_answer='SECRET_GOLD',
                        docs=['opening: 2001', 'first', 'second', 'third', 'last evidence ' * 8000])

    def metrics(self, f1=.8, far=.1, recall=.7):
        return dict(macro_f1=f1, classification_false_answer_rate=far,
                    parse_coverage=1., strict_format_pass_rate=1.,
                    per_class={m: dict(recall=recall) for m in search.e.MODES})

    def test_render_ignores_labels_and_gold_and_keeps_all_evidence(self):
        tokenizer=Tokenizer()
        for name in self.config['candidate_order']:
            text=search.render(self.row,self.config['instructions'][name],tokenizer)
            changed=dict(self.row,true_mode='conflict',label=2,gold_answer='OTHER_SECRET')
            self.assertEqual(text,search.render(changed,self.config['instructions'][name],tokenizer))
            self.assertNotIn('SECRET_GOLD',text)
            for doc in self.row['docs']:self.assertIn(doc,text)

    def test_high_score_with_failed_class_recall_is_not_a_qualified_baseline(self):
        metrics={name:self.metrics(.95) for name in self.config['candidate_order']}
        for value in metrics.values():value['per_class']['conflict']['recall']=.01
        selection=search.select(metrics,self.config)
        self.assertIsNone(selection['selected_candidate'])
        self.assertEqual(selection['status'],'no_qualified_baseline')

    def test_selection_uses_f1_then_false_answer_rate_then_fixed_order(self):
        metrics={'definitions':self.metrics(.8,.12),'decision_order':self.metrics(.8,.1),
                 'illustrations':self.metrics(.75,.05)}
        self.assertEqual(search.select(metrics,self.config)['selected_candidate'],'decision_order')
        metrics['definitions']=self.metrics(.8,.1)
        self.assertEqual(search.select(metrics,self.config)['selected_candidate'],'definitions')

    def test_format_or_false_answer_failures_exclude_candidates(self):
        metrics={name:self.metrics() for name in self.config['candidate_order']}
        metrics['definitions']['strict_format_pass_rate']=.98
        metrics['decision_order']['classification_false_answer_rate']=.3
        self.assertEqual(search.select(metrics,self.config)['eligible_candidates'],['illustrations'])

    def test_checkpoint_detects_raw_output_prompt_and_spec_corruption(self):
        tokenizer=Tokenizer();instruction=self.config['instructions']['definitions'];spec={'protocol':'fixed'}
        record=dict(id=self.row['id'],true_mode='answer',raw_output='answer',
                    raw_output_sha256=search.e.text_hash('answer'),generated_tokens=2,
                    prompt_sha256=search.e.text_hash(search.render(self.row,instruction,tokenizer)),
                    pred_mode='answer',strict_format_pass=True)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'predictions.json'
            good=dict(spec=spec,records=[record])
            search.e.repro.write_json(path,good)
            self.assertEqual(len(search.cached(path,spec,[self.row],instruction,tokenizer)),1)
            for mutation in ['raw_output','prompt_sha256','spec','generated_tokens']:
                bad=copy.deepcopy(good)
                if mutation=='spec':bad['spec']={'protocol':'other'}
                elif mutation=='generated_tokens':bad['records'][0][mutation]=9
                else:bad['records'][0][mutation]='tampered'
                search.e.repro.write_json(path,bad)
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                    search.cached(path,spec,[self.row],instruction,tokenizer)

    def test_missing_or_mismatched_review_gate_prevents_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'public').mkdir();(root/'coordinator').mkdir()
            with patch.object(search,'REVIEW',root):
                with self.assertRaises(ValueError):search.review_gate()
                (root/'public/protocol.json').write_text('{}')
                search.e.repro.write_json(root/'coordinator/readiness.json',dict(
                    status='independent_review_verified',evidence_items=300,behavior_items=234,
                    packet_sha256='wrong',ratings_sha256={},background_exposure_disclosed=True))
                with self.assertRaises(ValueError):search.review_gate()

    def test_busy_gpu_prevents_model_loading(self):
        result=type('Result',(),{'stdout':'123, active_model, 1024 MiB'})()
        with patch.object(search.subprocess,'run',return_value=result):
            with self.assertRaises(RuntimeError):search.assert_gpu_idle()

    def test_disclosed_coordinator_supplement_has_complete_coverage_and_unchanged_ratings(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'public').mkdir();(root/'coordinator').mkdir()
            (root/'public/protocol.json').write_text('{}')
            ratings=root/'ratings.csv';ratings.write_text('saved ratings')
            ready=dict(status='review_verified_with_coordinator_supplement', evidence_items=300,
                       behavior_items=234,second_review_behavior_items=232,
                       coordinator_supplement_behavior_items=2,
                       reviewer_independence='Two coordinator scores are not independent; background exposed.',
                       packet_sha256=search.e.repro.digest_file(root/'public/protocol.json'),
                       ratings_sha256={'ratings.csv':search.e.repro.digest_file(ratings)},
                       background_exposure_disclosed=True)
            with patch.object(search,'REVIEW',root),patch.object(search,'ROOT',root):
                search.e.repro.write_json(root/'coordinator/readiness.json',ready)
                self.assertEqual(search.review_gate()['second_review_behavior_items'],232)
                for changes in [{'coordinator_supplement_behavior_items':1},
                                {'background_exposure_disclosed':False},
                                {'reviewer_independence':''}]:
                    search.e.repro.write_json(root/'coordinator/readiness.json',dict(ready,**changes))
                    with self.subTest(changes=changes),self.assertRaises(ValueError):search.review_gate()
                search.e.repro.write_json(root/'coordinator/readiness.json',ready)
                ratings.write_text('changed after verification')
                with self.assertRaises(ValueError):search.review_gate()

    def test_interrupted_inference_resumes_without_regenerating_saved_instance(self):
        tokenizer=Tokenizer()
        rows=[dict(self.row,id='val_1_'+mode,true_mode=mode,label=i)
              for i,mode in enumerate(search.e.MODES)]
        calls=[]
        fail_once=[True]
        def fake_generate(model,tok,row,instruction):
            key=(instruction,row['id']);calls.append(key)
            if len(calls)==2 and fail_once[0]:
                fail_once[0]=False
                raise RuntimeError('simulated interruption')
            raw=row['true_mode']
            return dict(id=row['id'],true_mode=row['true_mode'],original_id=row['original_id'],
                        raw_output=raw,raw_output_sha256=search.e.text_hash(raw),
                        prompt_sha256=search.e.text_hash(search.render(row,instruction,tok)),
                        generated_tokens=2,pred_mode=raw,strict_format_pass=True,hit_output_limit=False)
        with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
            stack.enter_context(patch.object(sys,'argv',['search','--model','/tmp/mock-model','--run_dir',directory]))
            stack.enter_context(patch.object(search,'sources',return_value=(rows,{})))
            stack.enter_context(patch.object(search,'protocol',return_value={'frozen':'protocol'}))
            stack.enter_context(patch.object(search,'preflight',return_value={'cpu':'mocked'}))
            stack.enter_context(patch.object(search,'review_gate',return_value={'review':'mocked'}))
            stack.enter_context(patch.object(search,'assert_gpu_idle'))
            stack.enter_context(patch.object(search.e,'load_model',return_value=object()))
            stack.enter_context(patch.object(search,'generate',side_effect=fake_generate))
            stack.enter_context(patch.object(search,'analyze'))
            stack.enter_context(patch('transformers.AutoTokenizer.from_pretrained',return_value=tokenizer))
            with redirect_stdout(io.StringIO()),self.assertRaises(RuntimeError):search.main()
            first=Path(directory)/'definitions/predictions.json'
            self.assertEqual(len(search.e.read_json(first)['records']),1)
            self.assertEqual(search.e.read_json(Path(directory)/'last_failure.json')['saved_before_failure'],1)
            with redirect_stdout(io.StringIO()):search.main()
            saved_key=(self.config['instructions']['definitions'],rows[0]['id'])
            self.assertEqual(calls.count(saved_key),1)
            for name in self.config['candidate_order']:
                self.assertEqual(len(search.e.read_json(Path(directory)/name/'predictions.json')['records']),3)
            self.assertEqual(search.e.read_json(Path(directory)/'progress.json')['status'],'analysis_complete')


if __name__=='__main__':unittest.main()
