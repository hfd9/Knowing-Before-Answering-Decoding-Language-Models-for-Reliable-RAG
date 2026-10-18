"""CPU checks for label constraints, source separation and smoke/full gating."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import classification_semantic_baseline as s


class Tokenizer:
    eos_token_id = 2
    pad_token_id = 2
    words = {'answer': [3], 'refuse': [4, 5], 'conflict': [6]}

    def __call__(self, text, **kwargs):
        return {'input_ids': self.words[text]}

    def decode(self, tokens, skip_special_tokens=False):
        tokens = list(tokens)
        if skip_special_tokens:
            tokens = [t for t in tokens if t != 2]
        for word, ids in self.words.items():
            if tokens == ids:
                return word
        return 'INVALID'

    def apply_chat_template(self, messages, **kwargs):
        return json.dumps(messages, ensure_ascii=False)+'assistant'


class SemanticBaselineTests(unittest.TestCase):
    def setUp(self):
        self.config = s.e.read_json(s.PROMPTS)
        self.tokenizer = Tokenizer()
        self.grammar = s.LabelGrammar(self.tokenizer, [2])
        self.row = dict(id='val_0_answer', original_id='val_0', question='Target question?',
                        docs=['doc1', 'doc2', 'doc3', 'doc4', 'LAST_FULL_DOCUMENT ' * 3000],
                        true_mode='answer', label=0, gold_answer='PRIVATE_GOLD', split='val')

    def record(self, row, instruction):
        return dict(id=row['id'], original_id=row['original_id'], true_mode=row['true_mode'],
                    raw_output='answer', raw_output_sha256=s.e.text_hash('answer'),
                    generated_token_ids=[3,2], generated_tokens=2, pred_mode='answer', technical_valid=True,
                    strict_format_pass=True, hit_output_limit=False,
                    prompt_sha256=s.e.text_hash(s.old.render(row,instruction,self.tokenizer)))

    def test_native_chat_contains_all_docs_and_no_gold_or_label_metadata(self):
        for instruction in s.instructions(self.config).values():
            text = s.old.render(self.row,instruction,self.tokenizer)
            altered = dict(self.row, label=2, true_mode='conflict', gold_answer='OTHER_PRIVATE_GOLD')
            self.assertEqual(text, s.old.render(altered,instruction,self.tokenizer))
            self.assertNotIn('PRIVATE_GOLD', text)
            for doc in self.row['docs']:
                self.assertIn(doc, text)

    def test_grammar_allows_multitoken_label_but_requires_terminal_eos(self):
        self.assertEqual(set(self.grammar.allowed([])), {3,4,6})
        self.assertEqual(self.grammar.allowed([4]), [5])
        self.assertEqual(self.grammar.allowed([4,5]), [2])
        self.assertEqual(self.grammar.verdict([4,5,2]), 'refuse')
        self.assertIsNone(self.grammar.verdict([4,5]))
        self.assertIsNone(self.grammar.verdict([4,2]))
        self.assertIsNone(self.grammar.verdict([3,2,2]))
        with self.assertRaises(ValueError):
            self.grammar.allowed([9])

    def test_actual_tiny_qwen_cpu_generation_obeys_grammar(self):
        import torch
        from transformers import Qwen2Config, Qwen2ForCausalLM, GenerationConfig
        torch.set_num_threads(1)
        model = Qwen2ForCausalLM(Qwen2Config(vocab_size=16,hidden_size=16,intermediate_size=32,
                    num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=1,
                    max_position_embeddings=64,eos_token_id=2,pad_token_id=2)).eval()
        config = GenerationConfig(max_new_tokens=8, do_sample=False, num_beams=1,
                                  eos_token_id=[2],pad_token_id=2)
        with torch.inference_mode():
            output = model.generate(input_ids=torch.tensor([[7,8,9]]),
                      attention_mask=torch.ones((1,3),dtype=torch.long),
                      generation_config=config,prefix_allowed_tokens_fn=self.grammar.callback(3))
        tokens = output[0,3:].tolist()
        self.assertIn(self.grammar.verdict(tokens), s.e.MODES)
        self.assertLessEqual(len(tokens), self.grammar.maximum_tokens)

    def test_original_screening_thresholds_are_preserved_and_low_recall_fails(self):
        old = s.e.read_json(s.old.PROMPTS)['selection']
        for key in ['minimum_parse_coverage','minimum_strict_format_rate','minimum_recall_each_class',
                    'maximum_classification_false_answer_rate','primary_metric','tie_breakers']:
            self.assertEqual(old[key], self.config['selection'][key])
        metrics={name:dict(macro_f1=.9,parse_coverage=1.,strict_format_pass_rate=1.,
                    classification_false_answer_rate=.01,per_class={m:dict(recall=.9 if m!='conflict' else .1)
                                                                 for m in s.e.MODES})
                 for name in self.config['candidate_order']}
        self.assertEqual(s.old.select(metrics,self.config)['status'],'no_qualified_baseline')

    def test_cache_detects_tokens_prompt_identity_spec_and_raw_corruption(self):
        instruction=s.instructions(self.config)['semantic_rules'];spec={'protocol_sha256':'fixed'}
        record=self.record(self.row,instruction)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'predictions.json';good=dict(spec=spec,records=[record])
            s.e.repro.write_json(path,good)
            self.assertEqual(s.cached(path,spec,[self.row],instruction,self.tokenizer,self.grammar),[record])
            for field,value in [('generated_token_ids',[4,5,2]),('prompt_sha256','bad'),
                                ('original_id','wrong'),('raw_output','refuse'),('technical_valid',False)]:
                bad=copy.deepcopy(good);bad['records'][0][field]=value;s.e.repro.write_json(path,bad)
                with self.subTest(field=field),self.assertRaises(ValueError):
                    s.cached(path,spec,[self.row],instruction,self.tokenizer,self.grammar)
            s.e.repro.write_json(path,good)
            with self.assertRaises(ValueError):
                s.cached(path,{'protocol_sha256':'changed'},[self.row],instruction,self.tokenizer,self.grammar)

    def test_smoke_requires_all9_for_both_candidates_and_ignores_semantic_score(self):
        record=dict(technical_valid=True,strict_format_pass=True,hit_output_limit=False,pred_mode='refuse')
        methods={name:[dict(record) for _ in range(9)] for name in self.config['candidate_order']}
        self.assertEqual(s.smoke_gate([{}]*9,methods)['status'],'technical_smoke_passed')
        for bad in [{}, {'semantic_rules':methods['semantic_rules']},
                    dict(methods,semantic_examples=methods['semantic_examples'][:-1])]:
            with self.assertRaises(ValueError):s.smoke_gate([{}]*9,bad)
        methods['semantic_examples'][0]['technical_valid']=False
        with self.assertRaises(ValueError):s.smoke_gate([{}]*9,methods)

    def test_busy_gpu_reports_process_and_aborts(self):
        result=type('Result',(),dict(stdout='123, existing_job, 1024 MiB'))()
        with patch.object(s.subprocess,'run',return_value=result),self.assertRaisesRegex(RuntimeError,'123'):
            s.assert_gpu_idle()

    def test_launcher_never_starts_full_when_smoke_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);scripts=root/'scripts';scripts.mkdir()
            launch=scripts/'run_classification_semantic_baseline_review.sh'
            launch.write_bytes((ROOT/'scripts'/launch.name).read_bytes())
            (scripts/'run_classification_semantic_baseline.sh').write_text('#!/bin/sh\nprintf "mock smoke failure\\n"\nexit 7\n')
            result=subprocess.run(['sh',str(launch)],capture_output=True,text=True)
            self.assertEqual(result.returncode,7)
            self.assertIn('full run was not started',result.stderr)
            self.assertFalse((root/'runs/qwen2.5-3b-classification-semantic-v1/launch/full.log').exists())

    def test_diagnostic_uses_explicit_followup_labels_without_relabeling_predictions(self):
        # Equal counts prevent empty-class denominators; one auxiliary label differs from published.
        rows=[]
        for i,mode in enumerate(s.e.MODES):
            rows.append(dict(self.row,id=f'val_{i}_{mode}',original_id=f'val_{i}',true_mode=mode,
                             label=s.e.repro.LABEL_MAP[mode]))
        records=[dict(id=r['id'],true_mode=r['true_mode'],pred_mode=r['true_mode'],
                      strict_format_pass=True,hit_output_limit=False,raw_output=r['true_mode']) for r in rows]
        auxiliary={r['id']:dict(semantic_mode=s.e.MODES[(i+1)%3],confidence='high') for i,r in enumerate(rows)}
        with tempfile.TemporaryDirectory() as tmp:
            args=type('Args',(),dict(run_dir=Path(tmp),limit_questions=None))()
            methods={name:copy.deepcopy(records) for name in self.config['candidate_order']}
            with patch.object(s,'load_methods',return_value=methods),patch.object(s.old,'baseline',return_value=records),\
                 patch.object(s,'followup_reference',return_value=auxiliary),patch.object(s.e,'bootstrap_pair',return_value={}):
                report=s.analyze(args,rows,self.config,'hash',self.tokenizer,self.grammar)
            self.assertEqual(report['methods']['semantic_rules']['correct'],3)
            self.assertEqual(report['auxiliary_development_diagnosis']['methods']['semantic_rules']['correct'],0)
            self.assertEqual(records[0]['true_mode'],rows[0]['true_mode'])


if __name__=='__main__':unittest.main()
