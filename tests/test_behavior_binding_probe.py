"""Recovery, exact input identity and retrospective joint analysis; no3B GPU calls."""

from contextlib import ExitStack, redirect_stdout
import copy
import csv
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'scripts'))
import behavior_binding_probe as study


class ProbeSupplementTests(unittest.TestCase):
    def setUp(self):
        self.rows = study.source.ordered_rows(study.read(study.source.DEFAULT / 'materials/inputs.json'),
                                            study.read(study.source.SPEC))
        with (ROOT / (study.behavior.PREFIX+'-cells.csv')).open(newline='') as stream:
            self.joined = list(csv.DictReader(stream))

    def fixture(self, run):
        protocol = dict(model='cpu-fixture-no-model',feature_shape=[36,2048],
                        capture_phase='retrospectively_recomputed_input_prefill_without_generation')
        study.save(run / 'protocol.json',protocol)
        identities = [dict(id=r['id'],prompt_sha256='fixture',input_tokens=1,
                           input_token_ids_sha256='fixture-token') for r in self.rows]
        study.save(run / 'preflight.json',dict(prompts=identities))
        study.save(run / 'source/behavior_rows.json',self.joined)
        study.save(run / 'source/preserved.json',{})
        return protocol

    @staticmethod
    def prediction(probe, states):
        # Deliberately wrong for all I: technical smoke must not screen semantic performance.
        return dict(probe_pred='answer',probe_probabilities=dict(answer=.7,refuse=.2,conflict=.1),
                    probe_layer_zero_based=28)

    def simulation(self, interrupt_at=None, invalid_at=None):
        calls = []
        stack = ExitStack()
        def capture(model, tokenizer, row):
            if interrupt_at is not None and len(calls)==interrupt_at:
                raise RuntimeError('Simulated interrupted forward')
            index = len(calls)
            calls.append(row['id'])
            states = np.ones((36,2048),dtype=np.float16)
            if invalid_at is not None and index == invalid_at:
                states[0,0] = np.nan
            return states,.01
        stack.enter_context(patch.object(study,'capture_prefill',side_effect=capture))
        stack.enter_context(patch.object(study,'predict',side_effect=self.prediction))
        loader = stack.enter_context(patch.object(study.e,'load_model',return_value=object()))
        stack.enter_context(patch.object(study.pilot.s,'assert_gpu_idle'))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return stack,calls,loader

    def records(self):
        records = []
        for row in self.rows:
            expected = 'answer' if row['condition']=='S' else 'refuse'
            record = dict(**{k:row[k] for k in study.META},probe_pred=expected,
                probe_probabilities={k:(.8 if k==expected else .1) for k in study.MODES},
                feature_sha256='fixture',prompt_sha256='fixture',
                capture_phase='retrospectively_recomputed_input_prefill_without_generation')
            records.append(record)
        return records

    def test_all48_complete_replay_and_resume_without_model_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            protocol = self.fixture(run)
            stack,calls,loader = self.simulation()
            with stack:
                study.collect(run,self.rows,protocol,None,None)
                report = study.finish(run,self.rows,protocol,None)
                self.assertEqual((len(calls),loader.call_count),(48,1))
                self.assertEqual(report['author_reference_confusion']['I']['answer'],24)
                self.assertEqual(report['citation_field']['unknown'],48)
                self.assertEqual(report['I_behavior_by_probe']['refuse']['eligible'],0)
                self.assertIsNone(report['I_behavior_by_probe']['refuse']['point'])
                study.collect(run,self.rows,protocol,None,None)
                before = {str(p):study.digest(p) for p in run.rglob('*') if p.is_file()}
                study.finish(run,self.rows,protocol,None,verify=True)
                self.assertEqual(before,{str(p):study.digest(p) for p in run.rglob('*') if p.is_file()})
                self.assertEqual((len(calls),loader.call_count),(48,1))
                self.assertFalse(study.read(run/'smoke_gate.json')['semantic_accuracy_gate'])

    def test_committed_prefix_resumes_only_remaining_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            protocol = self.fixture(run)
            # Simulate a normal process stop immediately after the durable states.json commit.
            original_save = study.save
            def stop_after_commit(path,value,*args,**kwargs):
                original_save(path,value,*args,**kwargs)
                if Path(path).name=='states.json' and len(value['records'])==5:
                    raise KeyboardInterrupt()
            stack,calls,_ = self.simulation()
            with stack,patch.object(study,'save',side_effect=stop_after_commit):
                with self.assertRaises(KeyboardInterrupt):
                    study.collect(run,self.rows,protocol,None,None)
            self.assertEqual(len(calls),5)
            stack,resumed,loader = self.simulation()
            with stack:
                study.collect(run,self.rows,protocol,None,None)
                self.assertEqual(len(resumed),43)
                self.assertEqual(resumed,self.rows_ids()[5:])
                self.assertEqual(loader.call_count,1)

    def rows_ids(self):
        return [r['id'] for r in self.rows]

    def test_uncommitted_attempt_blocks_reload_and_duplicate_prefill(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            protocol = self.fixture(run)
            stack,calls,loader = self.simulation(interrupt_at=2)
            with stack:
                with self.assertRaisesRegex(RuntimeError,'interrupted'):
                    study.collect(run,self.rows,protocol,None,None)
                with self.assertRaisesRegex(ValueError,'Uncommitted'):
                    study.collect(run,self.rows,protocol,None,None)
                self.assertEqual((len(calls),loader.call_count),(2,1))

    def test_bad_feature_stops_before_smoke_can_continue(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            protocol = self.fixture(run)
            stack,calls,loader = self.simulation(invalid_at=3)
            with stack:
                with self.assertRaisesRegex(ValueError,'Invalid feature'):
                    study.collect(run,self.rows,protocol,None,None)
                self.assertEqual(len(calls),4)
                self.assertFalse((run/'smoke_gate.json').exists())
                with self.assertRaisesRegex(ValueError,'Uncommitted'):
                    study.collect(run,self.rows,protocol,None,None)
                self.assertEqual(loader.call_count,1)

    def test_cache_identity_probability_phase_and_feature_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            protocol = self.fixture(run)
            stack,calls,loader = self.simulation()
            with stack:
                study.collect(run,self.rows,protocol,None,None)
                original = study.read(run/'states.json')
                changes = [dict(condition='I'),dict(probe_pred='conflict'),
                    dict(probe_probabilities=dict(answer=.6,refuse=.3,conflict=.1)),
                    dict(capture_phase='during_original_generation'),dict(feature_file='../x.npy'),
                    dict(input_token_ids_sha256='changed'),dict(elapsed_seconds=float('nan'))]
                for change in changes:
                    data = copy.deepcopy(original)
                    data['records'][0].update(change)
                    study.save(run/'states.json',data)
                    with self.subTest(change=change),self.assertRaises(ValueError):
                        study.collect(run,self.rows,protocol,None,None)
                study.save(run/'states.json',original)
                (run/'features/0000.npy').write_bytes(b'corrupt')
                with self.assertRaisesRegex(ValueError,'hash'):
                    study.collect(run,self.rows,protocol,None,None)
                self.assertEqual((len(calls),loader.call_count),(48,1))

    def test_orphan_feature_refuses_first_model_load(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            protocol = self.fixture(run)
            study.e.save_array(run/'features/0000.npy',np.ones((36,2048),dtype=np.float16))
            stack,calls,loader = self.simulation()
            with stack,self.assertRaisesRegex(ValueError,'Orphan'):
                study.collect(run,self.rows,protocol,None,None)
            self.assertEqual((calls,loader.call_count),([],0))

    def test_incomplete_cache_cannot_make_joint_report(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            protocol = self.fixture(run)
            with self.assertRaisesRegex(ValueError,'All48'):
                study.finish(run,self.rows,protocol,None)
            self.assertFalse((run/'completion.json').exists())

    def test_joint_pairs_correct_reference_and_unknown_citation_preserved(self):
        report,cells,si,distractor,bases = study.summarize_joint(self.joined,self.records())
        self.assertEqual(report['all']['matches_author_reference'],48)
        self.assertEqual(report['S_to_I']['both_match'],24)
        self.assertEqual(report['S_to_I']['category_changes'],24)
        self.assertAlmostEqual(report['S_to_I']['mean_delta']['refuse'],.7)
        self.assertEqual(report['distractor_change']['category_changes'],0)
        self.assertEqual(report['all_four_match_bases'],12)
        self.assertEqual((len(cells),len(si),len(distractor),len(bases)),(48,24,24,12))
        self.assertEqual(report['citation_field']['unknown'],48)
        self.assertIsNone(report['citation_field']['point'])
        self.assertEqual(report['I_behavior_by_probe']['refuse']['yes'],0)

    def test_joint_wrong_probe_keeps_correct_behavior_and_all_cells(self):
        records = self.records()
        for row in records:
            row.update(probe_pred='conflict',probe_probabilities=dict(answer=.1,refuse=.1,conflict=.8))
        report,cells,_,_,_ = study.summarize_joint(self.joined,records)
        self.assertEqual(len(cells),48)
        self.assertEqual(report['all']['matches_author_reference'],0)
        self.assertEqual(report['behavior_by_condition']['S']['supported_target_answer']['yes'],24)
        self.assertEqual(report['behavior_by_condition']['I']['has_substantive_target_answer']['no'],24)

    def test_joint_duplicate_or_mismatched_base_cannot_silently_join(self):
        for kind in ['duplicate','base']:
            records = self.records()
            if kind=='duplicate':
                records[-1] = records[0]
            else:
                records[0]['original_id']='wrong'
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                study.summarize_joint(self.joined,records)

    def test_exact_real_tokenizer48_prompts_match_original_answers(self):
        from transformers import AutoTokenizer
        protocol = study.read(study.source.DEFAULT/'protocol.json')
        tokenizer = AutoTokenizer.from_pretrained(protocol['model'],local_files_only=True)
        saved = {r['id']:r for r in study.read(study.source.DEFAULT/'predictions.json')['records']}
        lengths = []
        for row in self.rows:
            identity = study.prompt_identity(row,tokenizer)
            self.assertEqual(identity,{k:saved[row['id']][k] for k in identity})
            lengths.append(identity['input_tokens'])
        self.assertEqual(sum(lengths),11688)

    def test_real_cpu_qwen_prefill_capture_matches_hf_hidden_states_with_cache(self):
        import torch
        from transformers import Qwen2Config,Qwen2ForCausalLM
        torch.manual_seed(42)
        config = Qwen2Config(vocab_size=32,hidden_size=16,intermediate_size=32,
            num_hidden_layers=3,num_attention_heads=2,num_key_value_heads=1)
        model = Qwen2ForCausalLM(config).eval()
        ids = torch.tensor([[3,7,11,2]])
        with study.e.LastPromptCapture(model) as capture,torch.inference_mode():
            output = model.model(input_ids=ids,use_cache=True,output_hidden_states=True)
        expected = np.stack([v[0,-1].float().numpy() for v in output.hidden_states[1:]]).astype(np.float16)
        np.testing.assert_array_equal(capture.array(),expected)
        with patch.object(model,'forward',side_effect=AssertionError('LM head must not run')):
            with study.e.LastPromptCapture(model) as capture,torch.inference_mode():
                model.model(input_ids=ids,use_cache=True,output_hidden_states=False)
            np.testing.assert_array_equal(capture.array(),expected)


if __name__=='__main__':
    unittest.main()
