"""Failure-boundary tests use only temporary synthetic files, never the model or GPU."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import new_controlled_probe_20261111 as run

class Transactions(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.sha='abc'
    def tearDown(self): self.tmp.cleanup()
    def save(self, index=0, ident='x', protocol='abc'):
        (self.root/'attempts').mkdir(exist_ok=True)
        (self.root/'attempts'/f'{index:04d}.json').write_text(json.dumps({'index':index,'id':ident,'protocol_sha256':protocol}))
        (self.root/'features').mkdir(exist_ok=True)
        (self.root/'features'/f'{index:04d}.npy').write_bytes(b'fixture')
        return {'id':ident,'feature_file':f'features/{index:04d}.npy'}
    def test_valid_committed_record(self):
        row=self.save(); run.validate_pending(self.root,[row],self.sha)
    def test_uncommitted_attempt_stops(self):
        self.save()
        with self.assertRaises(Exception): run.validate_pending(self.root,[],self.sha)
    def test_wrong_protocol_or_identity_stops(self):
        row=self.save(protocol='different')
        with self.assertRaises(Exception): run.validate_pending(self.root,[row],self.sha)
    def test_orphan_feature_and_temporary_state_stop(self):
        row=self.save(); (self.root/'features'/'orphan.npy').write_bytes(b'x')
        with self.assertRaises(Exception): run.validate_pending(self.root,[row],self.sha)
        (self.root/'features'/'orphan.npy').unlink(); (self.root/'states.json.tmp').write_text('partial')
        with self.assertRaises(Exception): run.validate_pending(self.root,[row],self.sha)
    def test_unexpected_attempt_file_stops(self):
        row=self.save(); (self.root/'attempts'/'partial.tmp').write_text('partial')
        with self.assertRaises(Exception): run.validate_pending(self.root,[row],self.sha)
    def test_bridge_rejects_excess_error(self):
        row=self.save(); plan={'bridge_tolerances':{'max_layer_relative_l2':0.02,'max_probability_absolute_error':0.01}}
        with patch.object(run,'RUN',self.root), patch.object(run.np,'load',return_value=np.ones((1,1))), patch.object(run.d,'source_state',return_value=np.ones((1,1))), patch.object(run.d,'bridge_error',return_value={'max_layer_relative_l2':0.021,'max_probability_absolute_error':0}):
            with self.assertRaises(Exception): run.check_bridge({},row,None,None,plan)
    def test_incomplete_report_stops(self):
        with self.assertRaises(Exception): run.report([],{'items':[]},[])
    def test_synthetic_complete_report_has_prespecified_pairs(self):
        rows=[{'id':'bridge','original_id':'old'}]; records=[{'id':'bridge'}]; reviews=[]
        for base in range(6):
            for state,expected in [('S','answer'),('I','refuse'),('C','conflict')]:
                for wording in ('A','B'):
                    ident=f'{base}_{state}_{wording}'
                    rows.append({'id':ident,'original_id':str(base),'document_level':state,'question_level':wording})
                    reviews.append({'id':ident,'proposed_probe_class':expected})
                    records.append({'id':ident,'probe_pred':expected,'probe_probabilities':{'answer':0.3,'refuse':0.3,'conflict':0.4},'input_tokens':100})
        result=run.report(rows,{'items':reviews},records)
        kinds=[x['type'] for x in result['pairs']]
        self.assertEqual((len(kinds),kinds.count('A-B'),kinds.count('S-I'),kinds.count('S-C')),(42,18,12,12))
        self.assertTrue(all(x['left']['matches_informed_author_ref'] and x['right']['matches_informed_author_ref'] for x in result['pairs']))

if __name__=='__main__': unittest.main()
