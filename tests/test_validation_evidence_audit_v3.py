"""Verify grammar enforcement, real HF generation, provenance and cache integrity."""

import copy
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from evidence_decision_grammar import DecisionGrammar
import validation_evidence_audit_v3 as v3


class CharacterTokenizer:
    eos_token_id = 0
    pad_token_id = 0

    def __call__(self, text, **kwargs):
        return {'input_ids':[ord(c) for c in text]}

    def decode(self, tokens, skip_special_tokens=False):
        return ''.join(chr(t) for t in tokens if not skip_special_tokens or t != 0)

    def apply_chat_template(self, messages, **kwargs):
        return json.dumps(messages,ensure_ascii=False)+'assistant'


def decision_tokens(tokenizer, mode, ids):
    pieces = [f'{{"semantic_mode":"{mode}","citation_ids":[']
    for i, key in enumerate(ids):
        if i:
            pieces.append(',')
        pieces.append(json.dumps(key))
    pieces.append(']}')
    return [t for piece in pieces for t in tokenizer(piece,add_special_tokens=False)['input_ids']]


class V3Tests(unittest.TestCase):
    def setUp(self):
        self.config = v3.e.read_json(v3.CONFIG)
        self.tokenizer = CharacterTokenizer()
        self.row = dict(id='val_1_answer',original_id='val_1',question='When did Cedar open?',
                        docs=['Cedar opened in 2001.','Cedar opened in 2004.','Third document.',
                              'Fourth document.','Fifth document.'],true_mode='SECRET_LABEL',gold_answer='SECRET_GOLD')
        self.spans = v3.citation_spans(self.row['docs'])

    def test_all_modes_and_multi_citations_are_valid_generated_paths(self):
        grammar = DecisionGrammar(self.tokenizer,self.spans,[0])
        choices = [('answer',['D1.S1']),('answer',['D1.S1','D2.S1','D3.S1','D4.S1']),
                   ('conflict',['D1.S1','D2.S1']),('refuse',[]),('unknown',[])]
        for mode, ids in choices:
            with self.subTest(mode=mode,ids=ids):
                tokens = decision_tokens(self.tokenizer,mode,ids)
                prefix = []
                for token in tokens:
                    self.assertNotIn(0,grammar.allowed(prefix))
                    self.assertIn(token,grammar.allowed(prefix))
                    prefix.append(token)
                self.assertEqual(grammar.allowed(prefix),[0])
                self.assertTrue(grammar.complete(prefix+[0]))
                raw = self.tokenizer.decode(tokens)
                result = v3.parse_draft(raw,self.row['docs'])
                self.assertEqual(result['semantic_mode'],mode)
                self.assertEqual(result['status'],'valid_structure')
                self.assertLessEqual(len(tokens)+1,grammar.maximum_tokens)

    def test_eos_malformed_keys_nonexistent_ids_and_same_doc_conflict_rejected(self):
        grammar = DecisionGrammar(self.tokenizer,self.spans,[0])
        for raw in ['{}','{"semantic_mode":"garbage"}',
                    '{"semantic_mode":"answer","citation_ids":["D9.S9"]}',
                    '{"semantic_mode":"conflict","citation_ids":["D1.S1","D1.S1"]}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                grammar.allowed(self.tokenizer(raw)['input_ids'])
        self.assertNotIn(0,grammar.allowed([]))
        self.assertNotIn(0,grammar.allowed(self.tokenizer('{')['input_ids']))
        self.assertEqual(v3.parse_draft('```json\n{}\n```',self.row['docs'])['status'],'invalid')
        good='{"semantic_mode":"refuse","citation_ids":[]}'
        self.assertEqual(v3.parse_draft(good,self.row['docs'],True)['semantic_mode'],'unknown')

    def test_spans_preserve_unicode_whitespace_offsets_and_full_prompt(self):
        docs = ['  Café\nopened  in 2001. '+('word\t'*60),'Second.', '3','4','5']
        spans = v3.citation_spans(docs)
        for span in spans:
            self.assertEqual(span['quote'],docs[span['doc_id']-1][span['start']:span['end']])
        self.assertEqual(len({s['span_id'] for s in spans}),len(spans))
        messages=v3.messages(dict(self.row,docs=docs),self.config)
        for doc in docs:
            self.assertIn(doc,messages[1]['content'])
        self.assertNotIn('SECRET_',json.dumps(messages))
        self.assertIn(self.row['question'],messages[1]['content'])

    def test_parser_rejects_duplicate_keys_and_invalid_reference_constraints(self):
        bad = ['{"semantic_mode":"refuse","semantic_mode":"answer","citation_ids":[]}',
               '{"semantic_mode":"answer","citation_ids":[]}',
               '{"semantic_mode":"refuse","citation_ids":["D1.S1"]}',
               '{"semantic_mode":"conflict","citation_ids":["D1.S1"]}',
               '{"semantic_mode":"answer","citation_ids":[true]}']
        for raw in bad:
            with self.subTest(raw=raw):
                self.assertEqual(v3.parse_draft(raw,self.row['docs'])['status'],'invalid')

    def record(self):
        rationale='The necessary opening year is stated.'
        tokens=decision_tokens(self.tokenizer,'answer',['D1.S1'])+[0]
        raw=self.tokenizer.decode(tokens,skip_special_tokens=True)
        first=v3.render(self.row,self.config,self.tokenizer)
        second=v3.render_decision(self.row,self.config,self.tokenizer,rationale)
        return dict(id=self.row['id'],original_id=self.row['original_id'],rationale=rationale,
                    rationale_sha256=v3.e.text_hash(rationale),rationale_token_ids=[ord(c) for c in rationale]+[0],
                    raw_output=raw,raw_output_sha256=v3.e.text_hash(raw),decision_token_ids=tokens,
                    prompt_sha256=v3.e.text_hash(first),decision_prompt_sha256=v3.e.text_hash(second),
                    input_tokens=len(first),decision_input_tokens=len(second),
                    generated_tokens=len(rationale)+1+len(tokens),hit_output_limit=False,
                    draft=v3.parse_draft(raw,self.row['docs']))

    def test_cache_validates_both_stages_tokens_prompts_and_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'predictions.json'
            spec={'protocol_sha256':'fixed'}
            record=self.record()
            def write(value):
                v3.e.repro.write_json(path,dict(spec=spec,records=[value]))
            write(record)
            self.assertEqual(v3.cached(path,spec,[self.row],self.config,self.tokenizer),[record])
            for field, value in [('rationale','changed'),('decision_prompt_sha256','broken'),
                                 ('rationale_token_ids',[1]),('decision_token_ids',[1]),
                                 ('hit_output_limit',True),('generated_tokens',1),('draft',{})]:
                bad=copy.deepcopy(record);bad[field]=value;write(bad)
                with self.subTest(field=field), self.assertRaises(ValueError):
                    v3.cached(path,spec,[self.row],self.config,self.tokenizer)

    def test_hf_generate_enforces_grammar_with_tiny_cpu_qwen(self):
        import torch
        from transformers import Qwen2Config,Qwen2ForCausalLM,GenerationConfig
        torch.manual_seed(42)
        model=Qwen2ForCausalLM(Qwen2Config(vocab_size=128,hidden_size=16,intermediate_size=32,
                                        num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=1,
                                        max_position_embeddings=512,eos_token_id=0,pad_token_id=0))
        model.eval()
        grammar=DecisionGrammar(self.tokenizer,self.spans,[0])
        with torch.inference_mode():
            output=model.generate(input_ids=torch.tensor([[1,2,3]]),attention_mask=torch.ones(1,3,dtype=torch.long),
                                  generation_config=GenerationConfig(max_new_tokens=grammar.maximum_tokens,
                                    do_sample=False,eos_token_id=0,pad_token_id=0),
                                  prefix_allowed_tokens_fn=grammar.callback(3))
        tokens=output[0,3:].tolist()
        self.assertTrue(grammar.complete(tokens))
        result=v3.parse_draft(self.tokenizer.decode(tokens,skip_special_tokens=True),self.row['docs'])
        self.assertEqual(result['status'],'valid_structure')

    def test_real_local_tokenizer_segments_roundtrip_and_budget(self):
        model=Path('/large_disk/wf/研究代码/RAG/OpenDecoder/checkpoint/Qwen2.5-3B-Instruct')
        if not model.exists():
            self.skipTest('Local offline tokenizer not installed')
        from transformers import AutoTokenizer
        tokenizer=AutoTokenizer.from_pretrained(model,local_files_only=True)
        grammar=DecisionGrammar(tokenizer,self.spans,[tokenizer.eos_token_id])
        for mode, ids in [('answer',['D1.S1','D2.S1']),('conflict',['D1.S1','D2.S1']),('refuse',[]),('unknown',[])]:
            tokens=decision_tokens(tokenizer,mode,ids)
            for i, token in enumerate(tokens):
                self.assertIn(token,grammar.allowed(tokens[:i]))
            self.assertTrue(grammar.complete(tokens))
            self.assertEqual(v3.parse_draft(tokenizer.decode(tokens),self.row['docs'])['semantic_mode'],mode)
        self.assertLessEqual(grammar.maximum_tokens,128)

    def test_launcher_stops_before_formal_if_gate_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);scripts=base/'scripts';scripts.mkdir()
            launcher=scripts/'run_validation_evidence_audit_v3_review.sh'
            launcher.write_text((ROOT/'scripts'/launcher.name).read_text())
            (scripts/'run_validation_evidence_audit_v3.sh').write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$KBA_TEST_TRACE"\n'
                'echo simulated_stage\ncase "$*" in *smoke-gate*) exit 3 ;; *) exit 0 ;; esac\n')
            process=subprocess.run(['sh',str(launcher)],env=dict(os.environ,KBA_TEST_TRACE=str(base/'trace')),
                                   capture_output=True,text=True)
            self.assertEqual(process.returncode,3)
            self.assertEqual(len((base/'trace').read_text().splitlines()),2)
            self.assertIn('full run was not started',process.stderr)
            self.assertIn('simulated_stage',process.stderr)


if __name__=='__main__':
    unittest.main()
