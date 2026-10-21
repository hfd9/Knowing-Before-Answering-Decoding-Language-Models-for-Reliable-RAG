"""CPU simulations for collection authority, one240 budget, cache/resume and no training/gold."""

from contextlib import ExitStack
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import semantic_transfer_exploratory_collection as study


class CollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=study.read(study.binding.MATERIALS/'materials/inputs.json')
        cls.parent=study.read(study.binding.DEFAULT/'protocol.json')
        cls.labels=study.read(study.binding.DEFAULT/'approved_labels.json')
        cls.gate=study.read(study.binding.DEFAULT/'review_gate.json')

    def prepare_fixture(self,run):
        with patch.object(study.binding,'prepare',return_value=(self.rows,self.labels,self.gate,self.parent,object())):
            return study.prepare(run,write=True)

    def fake_runtime(self, empty_smoke=False, fail_first=False):
        import evidence_experiment as e
        from sklearn.dummy import DummyClassifier
        from sklearn.preprocessing import StandardScaler
        features=np.asarray([[1.]*2048,[2.]*2048,[3.]*2048],dtype=np.float32)
        probe=dict(layer=28,scaler=StandardScaler().fit(features),
            router=DummyClassifier(strategy='prior').fit(features,[0,1,2]))
        class Tokenizer:
            def decode(self,tokens,**kwargs):
                return '' if len(tokens)==1 else 'Synthetic answer.'
        tokenizer=Tokenizer();calls=[];stack=ExitStack()
        def generate(model,tok,row,old,eos):
            if fail_first:raise RuntimeError('Synthetic interruption after attempt marker')
            index=len(calls);calls.append(row['id'])
            states=np.full((36,2048),1+(row['condition'] in ['I','C']),dtype=np.float16)
            tokens=[eos[0]] if empty_smoke and index==0 else [999,eos[0]]
            raw=tokenizer.decode(tokens)
            return dict(**{k:row[k] for k in ['id','original_id','partition','expression','condition']},
                prompt_sha256=study.core.text_hash(row['id']),input_tokens=1,generated_token_ids=tokens,
                generated_tokens=len(tokens),raw_output=raw,raw_output_sha256=study.core.text_hash(raw),
                ended_with_eos=True,hit_output_limit=False,elapsed_seconds=0,
                completed_at='2026-10-21T00:00:00+00:00',**study.core.predict(old,states)),states
        stack.enter_context(patch.object(study,'load_old_probe',return_value=probe))
        stack.enter_context(patch.object(e,'render_input',side_effect=lambda row,*args:row['id']))
        stack.enter_context(patch.object(e,'encode',return_value={'input_ids':[7]}))
        stack.enter_context(patch.object(study.core,'generate',side_effect=generate))
        stack.enter_context(patch('classification_semantic_baseline.assert_gpu_idle'))
        loader=stack.enter_context(patch.object(e,'load_model',return_value=object()))
        stack.enter_context(patch.object(study.core,'optional_fit',side_effect=AssertionError('training forbidden')))
        stack.enter_context(patch.object(study.core,'evaluation_lock',side_effect=AssertionError('formal evaluation forbidden')))
        return stack,tokenizer,calls,loader

    def test_amendment_retains_zero_training_and_no_formal_approval(self):
        value=study.amendment()
        self.assertEqual(value['scope']['max_model_generations'],240)
        original=study.read
        for field in ['max_new_training_fits','max_model_generations']:
            bad=copy.deepcopy(value);bad['scope'][field]=1
            with patch.object(study,'read',side_effect=lambda p:bad if Path(p)==study.AMENDMENT else original(p)):
                with self.assertRaisesRegex(ValueError,'scope changed'):
                    study.amendment()

    def test_prepare_prefix_in_same240_null_labels_and_all_protected_locations(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as folder:
            run=Path(folder);rows,protocol,_=self.prepare_fixture(run)
            self.assertEqual(len(rows),len({r['id'] for r in rows}))
            self.assertEqual(len(rows),240)
            self.assertEqual([r['id'] for r in rows[:4]],study.amendment()['technical_smoke']['prefix_ids'])
            self.assertFalse(protocol['formal_review_gate']['gpu_launch_ready'])
            self.assertEqual(protocol['max_training_fits'],0)
            self.assertTrue(all(v is None for v in study.read(run/'approved_labels.json').values()))
            before={p.name:study.digest(p) for p in run.iterdir()}
            with patch.object(study.binding,'prepare',return_value=(self.rows,self.labels,self.gate,self.parent,object())):
                study.prepare(run,write=False)
            self.assertEqual(before,{p.name:study.digest(p) for p in run.iterdir()})
        for run in [study.binding.DEFAULT,study.binding.core.DEFAULT,study.binding.ACCEPTANCE,
                study.binding.MATERIALS,ROOT/'runs']:
            with self.assertRaises(ValueError):study.validate_run_location(run)

    def test_missing_approval_is_not_faked_and_scope_tampering_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as folder:
            run=Path(folder);_,protocol,_=self.prepare_fixture(run)
            study.require_collection_permission(run,protocol)
            with self.assertRaisesRegex(ValueError,'Review gate closed'):
                study.core.require_ready(protocol['formal_review_gate'])
            (run/'approved_labels.json').write_text(study.serialize({**self.labels,self.rows[0]['id']:'answer'}))
            with self.assertRaisesRegex(ValueError,'remain null'):
                study.require_collection_permission(run,protocol)
            (run/'approved_labels.json').write_text(study.serialize(self.labels))
            study.put(run/'fit_attempt.json',{'synthetic':True})
            with self.assertRaisesRegex(ValueError,'Unexpected training'):
                study.require_collection_permission(run,protocol)

    def test_full240_collect_finish_resume_and_readonly_replay_without_fits(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as folder:
            run=Path(folder);rows,protocol,_=self.prepare_fixture(run)
            stack,tok,calls,loader=self.fake_runtime()
            with stack:
                study.collect(run,rows,protocol,tok)
                summary=study.finish(run,rows,protocol,tok)
                self.assertEqual((len(calls),loader.call_count),(240,1))
                self.assertIsNone(summary['semantic_accuracy']);self.assertIsNone(summary['semantic_macroF1'])
                self.assertIsNone(summary['actual_behavior_rates'])
                self.assertEqual(summary['training_fits'],0)
                self.assertEqual(study.read(run/'smoke_gate.json')['ids'],[r['id'] for r in rows[:4]])
                study.collect(run,rows,protocol,tok)
                self.assertEqual((len(calls),loader.call_count),(240,1))
                hashes={str(p.relative_to(run)):study.digest(p) for p in run.rglob('*') if p.is_file()}
                self.assertEqual(study.finish(run,rows,protocol,tok,write=False),summary)
                self.assertEqual(hashes,{str(p.relative_to(run)):study.digest(p) for p in run.rglob('*') if p.is_file()})
                packet=study.read(run/'behavior_review/packet.json')
                self.assertTrue(all(set(r)=={'item_id','question','documents','answer'} for r in packet['items']))
                self.assertEqual(len(packet['items']),240)
                self.assertTrue(all(r['status']=='unreviewed' for r in study.read(run/'behavior_review/ratings_template.json')['ratings']))
                value=study.read(run/'predictions.json');value['records'][0]['probe_probabilities']['answer']+=.1
                (run/'predictions.json').write_text(study.serialize(value))
                with self.assertRaisesRegex(ValueError,'probability mismatch'):
                    study.collect(run,rows,protocol,tok)
                self.assertEqual(loader.call_count,1)

    def test_failed_smoke_preserves_first4_and_never_generates_remaining236(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as folder:
            run=Path(folder);rows,protocol,_=self.prepare_fixture(run)
            stack,tok,calls,loader=self.fake_runtime(empty_smoke=True)
            with stack:
                with self.assertRaisesRegex(ValueError,'Technical smoke failed'):
                    study.collect(run,rows,protocol,tok)
                self.assertEqual(len(calls),4)
                self.assertFalse(study.read(run/'smoke_gate.json')['passed'])
                with self.assertRaisesRegex(ValueError,'Technical smoke failed'):
                    study.collect(run,rows,protocol,tok)
                self.assertEqual((len(calls),loader.call_count),(4,1))

    def test_uncommitted_attempt_stops_resume_before_model_loading(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as folder:
            run=Path(folder);rows,protocol,_=self.prepare_fixture(run)
            stack,tok,calls,loader=self.fake_runtime(fail_first=True)
            with stack:
                with self.assertRaisesRegex(RuntimeError,'Synthetic interruption'):
                    study.collect(run,rows,protocol,tok)
                self.assertEqual(loader.call_count,1)
                self.assertTrue((run/'generation_attempts/0000.json').is_file())
                with self.assertRaisesRegex(ValueError,'Uncommitted generation attempt'):
                    study.collect(run,rows,protocol,tok)
                self.assertEqual((len(calls),loader.call_count),(0,1))

    def test_incomplete_collection_cannot_export_completion_or_semantic_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as folder:
            run=Path(folder);rows,protocol,_=self.prepare_fixture(run)
            stack,tok,_,_=self.fake_runtime()
            with stack:
                with self.assertRaisesRegex(ValueError,'all240'):
                    study.finish(run,rows,protocol,tok)
                self.assertFalse((run/'completion.json').exists())
                self.assertFalse((run/'reports').exists())


if __name__ == '__main__':
    unittest.main()
