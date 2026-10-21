"""Numerical stage separation, unknown denominators and complete fixed pair coverage."""

import copy
import hashlib
import json
from pathlib import Path
import pickle
import sys
from types import SimpleNamespace
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import probe_calibration_diagnostic as audit


class DiagnosticTests(unittest.TestCase):
    def test_transition_dispositions_and_unknown_not_counted_as_error(self):
        cases=[('answer','answer','answer','unchanged_correct'),
               ('answer','refuse','refuse','unchanged_wrong'),
               ('answer','refuse','answer','changed_corrected'),
               ('answer','answer','conflict','changed_damaged'),
               ('answer','refuse','conflict','changed_both_wrong'),
               ('unknown','answer','refuse','changed_reference_unknown'),
               ('unknown','answer','answer','unchanged_reference_unknown')]
        for ref,before,after,expected in cases:
            self.assertEqual(audit.disposition(ref,before,after),expected)
        with self.assertRaises(ValueError):
            audit.disposition('unreviewed','answer','answer')

    def test_behavior_unknown_and_empty_conditional_denominators(self):
        result=audit.rate(['yes','unknown','no'])
        self.assertIsNone(result['point'])
        self.assertEqual((result['lower'],result['upper']),(1/3,2/3))
        self.assertEqual(audit.rate([])['eligible'],0)
        self.assertIsNone(audit.rate([])['point'])
        self.assertIsNone(audit.rate([])['lower'])
        with self.assertRaises(ValueError):
            audit.rate(['unreviewed'])

    def summary_rows(self):
        rows=[]
        for i,(ref,before,after) in enumerate([('answer','answer','conflict'),
              ('refuse','answer','refuse'),('unknown','answer','conflict'),('conflict','refuse','answer')]):
            rows.append(dict(original_id=str(i),author_reference=ref,raw_pred=before,
                calibrated_pred=after,disposition=audit.disposition(ref,before,after),existing_has_answer='no'))
        return rows

    def test_summary_reconciles_corrections_damage_and_keeps_unknown(self):
        result=audit.summarize(self.summary_rows())
        self.assertEqual((result['rows'],result['known_reference'],result['unknown_reference']),(4,3,1))
        self.assertEqual(result['net_reference_matches'],0)
        self.assertEqual(result['dispositions']['changed_corrected'],1)
        self.assertEqual(result['dispositions']['changed_damaged'],1)
        self.assertEqual(result['dispositions']['changed_both_wrong'],1)
        self.assertEqual(result['dispositions']['changed_reference_unknown'],1)
        self.assertEqual(result['raw']['matches_author_reference'],1)
        self.assertEqual(result['calibrated']['matches_author_reference'],1)

    def toy_probe(self):
        class Estimator:
            def decision_function(self,x):
                return np.array([[x[0,0],1.,-2.]])
            def predict(self,x):
                return np.argmax(self.decision_function(x),axis=1)
        class Router:
            calibrated_classifiers_=[SimpleNamespace(estimator=Estimator(),calibrators=[
                SimpleNamespace(a_=-1.,b_=2.),SimpleNamespace(a_=-1.,b_=-3.),SimpleNamespace(a_=-1.,b_=0.)])]
            def predict_proba(self,x):
                score=self.calibrated_classifiers_[0].estimator.decision_function(x)[0]
                q=1/(1+np.exp(-(score-np.array([2.,-3.,0.]))))
                return (q/q.sum())[None]
        return dict(scaler=SimpleNamespace(transform=lambda x:x),router=Router())

    def test_fixed_class_specific_calibration_can_change_argmax_without_fitting(self):
        result=audit.stage_replay(self.toy_probe(),np.ones((36,2048),dtype=np.float16))
        self.assertEqual(result['raw_pred'],'answer')
        self.assertEqual(result['calibrated_pred'],'refuse')
        self.assertAlmostEqual(sum(result['raw_softmax']),1.)
        self.assertAlmostEqual(sum(result['probability']),1.)
        self.assertLess(result['replay_error'],1e-14)

    def test_invalid_state_or_probability_replay_is_rejected(self):
        probe=self.toy_probe()
        for shape in [(35,2048),(36,2000)]:
            with self.assertRaises(ValueError):
                audit.stage_replay(probe,np.ones(shape,dtype=np.float16))
        values=np.ones((36,2048),dtype=np.float16);values[0,0]=np.nan
        with self.assertRaises(ValueError):
            audit.stage_replay(probe,values)
        values=np.ones((36,2048),dtype=np.float16);values[0]=0
        with self.assertRaises(ValueError):
            audit.stage_replay(probe,values)
        probe['router'].predict_proba=lambda x:np.array([[.9,.05,.05]])
        with self.assertRaisesRegex(ValueError,'Sigmoid replay'):
            audit.stage_replay(probe,np.ones((36,2048),dtype=np.float16))

    def pair_rows(self,dataset):
        if dataset=='binding48':
            source=audit.read('runs/qwen2.5-3b-behavior-binding-probe-v1/source/behavior_rows.json')
        else:
            import csv
            with (ROOT/'docs/records/2026-10-21-semantic-transfer-exploratory-behavior-cells.csv').open(newline='') as f:
                source=list(csv.DictReader(f))
        rows=[]
        for original in source:
            ref=original.get('exposed_author_input_mode','answer' if original['condition']=='S' else 'refuse')
            row=dict(dataset=dataset,id=original['id'],original_id=original['original_id'],
                condition=original['condition'],variant=original.get('variant',''),expression=original.get('expression',''),
                partition=original.get('partition','fictional_diagnostic'),question=original['question'],
                author_reference=ref,raw_pred='answer',calibrated_pred='answer',existing_behavior={})
            for mode in audit.MODES:
                for stage in ['linear','raw_softmax','calibrated_p']:
                    row[stage+'_'+mode]=1. if mode=='answer' else 0.
            rows.append(row)
        return rows

    def test_all48_binding_and300_transfer_pairs_keep_unknown_endpoints(self):
        binding=audit.make_pairs('binding48',self.pair_rows('binding48'))
        transfer=audit.make_pairs('transfer240',self.pair_rows('transfer240'))
        self.assertEqual((len(binding),len(transfer)),(48,300))
        self.assertEqual(sum(p['contrast']=='S_to_I' for p in binding),24)
        self.assertEqual(sum(p['contrast']=='S_to_I' for p in transfer),60)
        self.assertTrue(any(p['raw_both_match_reference'] is None for p in transfer))
        self.assertTrue(all(p['delta_linear_refuse']==0 for p in binding+transfer))

    def test_missing_duplicate_or_cross_partition_pair_rejected(self):
        rows=self.pair_rows('binding48')
        for kind in ['missing','duplicate','partition']:
            changed=copy.deepcopy(rows)
            if kind=='missing':changed.pop()
            elif kind=='duplicate':changed.append(changed[0])
            else:changed[0]['partition']='other'
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                audit.make_pairs('binding48',changed)

    def test_real_frozen_probe_replays_one_vector_from_each_existing_dataset(self):
        spec=audit.read(audit.SPEC)
        path=ROOT/spec['probe_source']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),spec['probe_sha256'])
        probe=pickle.loads(path.read_bytes())
        for dataset in ['binding48','transfer240']:
            run,records,_,_=audit.load_dataset(dataset,spec)
            record=records[0]
            stages=audit.stage_replay(probe,np.load(run/record['feature_file'],allow_pickle=False))
            self.assertEqual(stages['calibrated_pred'],record['probe_pred'])
            self.assertLess(max(abs(stages['probability'][i]-record['probe_probabilities'][m])
                for i,m in enumerate(audit.MODES)),1e-10)


if __name__=='__main__':
    unittest.main()
