"""CPU full48 material and single-attempt recovery tests; no model inference."""
from contextlib import ExitStack, redirect_stdout
import copy
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import relation_attachment_study as study


class RelationAttachmentTests(unittest.TestCase):
    def setUp(self):
        self.spec=study.read(study.SPEC)
        self.rows,self.worlds=study.make_materials(self.spec)

    def test_full_grid_worlds_primary_pairs_and_kept_examples(self):
        self.assertEqual(len(self.rows),48)
        self.assertEqual(len(self.worlds),36)
        pairs=study.pair_table(self.rows,self.spec)
        self.assertEqual(len(pairs),72)
        self.assertEqual(sum(p['kind']=='primary_TA_minus_OA' for p in pairs),12)
        self.assertEqual(study.make_materials(self.spec),(self.rows,self.worlds))
        self.assertEqual([r['id'] for r in study.ordered_rows(self.rows,self.spec)[:4]],self.spec['smoke_prefix_ids'])

    def test_world_leak_question_role_background_and_grid_tampering_rejected(self):
        for kind in ['world','leak','question','role','background','grid']:
            rows,worlds=copy.deepcopy((self.rows,self.worlds))
            row=next(r for r in rows if r['condition']=='TA')
            if kind=='world':
                worlds[row['id']]['worlds'][0][0]['value']='K-00000'
            elif kind=='leak':
                row['docs'][-1]+=' K-00000'
            elif kind=='question':
                row['question']+=' K-00000'
            elif kind=='role':
                row['condition']='TQ'
            elif kind=='background':
                row['docs'][-1]+=' Changed background.'
            else:
                rows[-1]=copy.deepcopy(rows[0])
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                study.validate_materials(rows,worlds,self.spec)

    def test_renderer_and_anonymous_input_packet_isolate_coordinator(self):
        self.assertEqual(set(study.renderer_inputs(self.rows[0])),{'question','docs'})
        packet,mapping,page=study.input_packet(self.rows)
        self.assertEqual(len(packet['items']),48)
        self.assertEqual(set(mapping),{r['id'] for r in self.rows})
        self.assertTrue(all(set(r)=={'item_id','question','documents'} for r in packet['items']))
        self.assertNotIn('rel01_TQ_v1',page)
        self.assertNotIn('witness_alternative',page)

    def test_real_source_prepare_freezes_and_replays_without_gpu(self):
        import evidence_experiment as e
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder)
            info=dict(model=study.read(study.core.MODEL_REFERENCE)['model'],
                model_files_sha256={'fixture':'cpu-only'},runtime_versions={'fixture':'1'},context_tokens=32768)
            with patch.object(study,'DEFAULT',run),patch.object(study,'runtime',return_value=(e,object(),info)),\
                    patch.object(e,'render_input',side_effect=lambda row,*a:study.encoded(row).decode()),\
                    patch.object(e,'encode',return_value={'input_ids':[7]}):
                rows,protocol,_=study.prepare(run,write=True)
                self.assertEqual((len(rows),protocol['scenarios'],protocol['new_probe_fits']),(48,6,0))
                self.assertEqual(len(protocol['implementation_sha256']),13)
                before={str(p):study.digest(p) for p in run.rglob('*') if p.is_file()}
                study.prepare(run,write=False)
                self.assertEqual(before,{str(p):study.digest(p) for p in run.rglob('*') if p.is_file()})

    def fixture(self,run):
        rows=study.ordered_rows(self.rows,self.spec)
        protocol=dict(model='synthetic-no-model',eos_token_ids=[2],ordered_ids=[r['id'] for r in rows])
        study.save(run/'protocol.json',protocol)
        return rows,protocol

    def simulation(self,empty=False,interrupt_at=None):
        import evidence_experiment as e
        class Tokenizer:
            len_calls=0
            def __len__(self):
                self.len_calls+=1
                return 100
            def decode(self,tokens,**kwargs):
                return '' if tokens==[2] else 'Synthetic CPU fixture answer.'
        tok=Tokenizer()
        calls=[]
        def render(row,*args):
            return study.encoded(row).decode()
        def generate(model,tokenizer,row,protocol):
            if interrupt_at is not None and len(calls)==interrupt_at:
                raise RuntimeError('Synthetic interruption after attempt')
            index=len(calls)
            calls.append(row['id'])
            tokens=[2] if empty and index==0 else [10,2]
            raw=tok.decode(tokens)
            return dict(**{k:row[k] for k in ['id','original_id','condition','variant']},
                prompt_sha256=study.sha(render(study.renderer_inputs(row))),input_tokens=1,
                input_token_ids_sha256=study.sha('[7]'),generated_token_ids=tokens,
                generated_tokens=len(tokens),raw_output=raw,raw_output_sha256=study.sha(raw),
                ended_with_eos=True,hit_output_limit=False,elapsed_seconds=0,completed_at='2026-10-23T00:00:00+00:00')
        stack=ExitStack()
        stack.enter_context(patch.object(e,'render_input',side_effect=render))
        stack.enter_context(patch.object(e,'encode',return_value={'input_ids':[7]}))
        stack.enter_context(patch.object(study,'generate',side_effect=generate))
        loader=stack.enter_context(patch.object(e,'load_model',return_value=object()))
        stack.enter_context(patch('classification_semantic_baseline.assert_gpu_idle'))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return stack,tok,calls,loader

    def test_complete48_no_resampling_no_behavior_scores_and_vocab_size_once(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder); rows,protocol=self.fixture(run)
            stack,tok,calls,loader=self.simulation()
            with stack:
                study.collect(run,rows,protocol,tok)
                result=study.finish(run,rows,protocol,tok)
                self.assertEqual((len(calls),loader.call_count),(48,1))
                self.assertEqual(result['scenarios'],6)
                self.assertTrue(all(result[k] is None for k in ['primary_TA_minus_OA',
                    'all_I_substantive_answer_rate','TQ_supported_answer_rate']))
                self.assertEqual(result['behavior_rows_reviewed'],0)
                study.collect(run,rows,protocol,tok)
                self.assertEqual((len(calls),loader.call_count),(48,1))
                before={str(p):study.digest(p) for p in run.rglob('*') if p.is_file()}
                study.finish(run,rows,protocol,tok,verify=True)
                self.assertEqual(before,{str(p):study.digest(p) for p in run.rglob('*') if p.is_file()})
                self.assertEqual(tok.len_calls,5)
                ratings=study.read(run/'behavior_review/ratings_template.json')['ratings']
                self.assertTrue(all(r['status']=='unreviewed' and all(r[f]=='unknown' for f in study.FIELDS) for r in ratings))

    def test_failed_smoke_stops_after_four_and_cannot_regenerate(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder); rows,protocol=self.fixture(run)
            stack,tok,calls,loader=self.simulation(empty=True)
            with stack:
                for _ in range(2):
                    with self.assertRaisesRegex(ValueError,'Technical smoke failed'):
                        study.collect(run,rows,protocol,tok)
                self.assertEqual((len(calls),loader.call_count),(4,1))

    def test_uncommitted_attempt_and_orphan_temp_block_model_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder); rows,protocol=self.fixture(run)
            stack,tok,calls,loader=self.simulation(interrupt_at=2)
            with stack:
                with self.assertRaisesRegex(RuntimeError,'Synthetic interruption'):
                    study.collect(run,rows,protocol,tok)
                with self.assertRaisesRegex(ValueError,'Uncommitted generation attempt'):
                    study.collect(run,rows,protocol,tok)
                self.assertEqual(loader.call_count,1)
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder); rows,protocol=self.fixture(run)
            (run/'generation_attempts').mkdir()
            (run/'generation_attempts/0000.json.tmp').write_text('incomplete')
            stack,tok,calls,loader=self.simulation()
            with stack,self.assertRaisesRegex(ValueError,'orphan file'):
                study.collect(run,rows,protocol,tok)
            self.assertEqual(loader.call_count,0)

    def test_normal_stop_after_commit_can_resume_prefix_without_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder); rows,protocol=self.fixture(run)
            stack,tok,calls,loader=self.simulation()
            real_save=study.save
            stopped=False
            def stop_after_commit(path,value,*args,**kwargs):
                nonlocal stopped
                result=real_save(path,value,*args,**kwargs)
                if Path(path).name=='progress.json' and value['completed']==5 and not stopped:
                    stopped=True
                    raise RuntimeError('Between committed inputs')
                return result
            with stack:
                with patch.object(study,'save',side_effect=stop_after_commit):
                    with self.assertRaisesRegex(RuntimeError,'Between committed inputs'):
                        study.collect(run,rows,protocol,tok)
                self.assertEqual(len(calls),5)
                study.collect(run,rows,protocol,tok)
                self.assertEqual(len(calls),len(set(calls)))
                self.assertEqual((len(calls),loader.call_count),(48,2))
                report=study.finish(run,rows,protocol,tok)
                self.assertTrue(report['historical_failure_record_present'])

    def test_corrupt_output_prompt_metadata_and_timing_rejected_before_new_model(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder); rows,protocol=self.fixture(run)
            stack,tok,calls,loader=self.simulation()
            with stack:
                study.collect(run,rows,protocol,tok)
                original=study.read(run/'predictions.json')
                for change in [dict(raw_output='tampered'),dict(input_tokens=99),dict(condition='other'),
                        dict(ended_with_eos=False),dict(generated_token_ids=[2,10,2]),
                        dict(generated_token_ids=[1000,2]),dict(elapsed_seconds=float('nan'))]:
                    altered=copy.deepcopy(original); altered['records'][0].update(change)
                    study.save(run/'predictions.json',altered)
                    with self.subTest(change=change),self.assertRaises(ValueError):
                        study.collect(run,rows,protocol,tok)
                self.assertEqual((len(calls),loader.call_count),(48,1))

    def test_incomplete_run_cannot_export_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder); rows,protocol=self.fixture(run)
            stack,tok,calls,loader=self.simulation()
            with stack,self.assertRaisesRegex(ValueError,'all48'):
                study.finish(run,rows,protocol,tok)
            self.assertFalse((run/'completion.json').exists())
            self.assertEqual(loader.call_count,0)


if __name__=='__main__':
    unittest.main()
