"""Blinding, source preservation and complete-denominator checks for separate reviews."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import controlled_semantic_transfer_review as r


class SeparateReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'runs/source';self.base=self.root/'runs/review'
        self.patches=[patch.object(r,'ROOT',self.root),patch.object(r,'SOURCE',self.source)]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        rows=[];preds=[];judgments=[];old=[]
        for i in range(10):
            for c in 'SICD':
                key=f'case{i}_{c}'; mode={'S':'answer','I':'refuse','C':'conflict','D':'answer'}[c]
                docs=['Fact alpha; blue folder.','Fact beta.','Background three.','Background four.','Background five.']
                if c=='D':docs[0]=docs[0].replace('blue','gold')
                rows.append(dict(id=key,original_id=f'base{i}',condition=c,question='Which fact?',docs=docs))
                preds.append(dict(id=key,raw_output='The answer is alpha.',probe_pred='conflict',probe_probabilities={'answer':.2,'refuse':.1,'conflict':.7},probe_layer_zero_based=28,input_tokens=100))
                judgments.append(dict(id=key,semantic_mode=mode))
                old.append(dict(id=key,behavior={k:'no' for k in r.FIELDS[:5]}))
        r.put(self.source/'materials/inputs.json',rows)
        r.put(self.source/'free_answer/predictions.json',dict(records=preds))
        r.put(self.source/'materials/input_judgments.json',judgments)
        r.put(self.source/'review/assistant-behavior-2026-10-20-v1/ratings.json',dict(ratings=old))
        r.prepare(self.base)

    def make_reviews(self):
        mapping=r.read(self.base/'coordinator/mapping.json')
        reverse={v['input_item_id']:k for k,v in mapping.items()}
        for task in ['input','behavior']:
            packet=r.read(self.base/(task+'_public/packet.json'));ratings=[]
            for item in packet['items']:
                common=dict(item_id=item['item_id'],confidence='high',rationale='Explicit evaluation.',resolution_basis='No supplied correction.')
                if task=='input':
                    condition=reverse[item['item_id']].split('_')[-1]
                    mode={'S':'answer','I':'refuse','C':'conflict','D':'answer'}[condition]
                    if reverse[item['item_id']]=='case0_S':mode='refuse'
                    rating=dict(**common,semantic_mode=mode,required_facts=['Necessary fact'],support_chain=['Document1 contains alpha.'],supported_answer=None if mode!='answer' else 'alpha',missing_facts=['Missing relation'] if mode=='refuse' else [],conflicting_claims=['alpha versus beta'] if mode=='conflict' else [],citations=[dict(doc_slot=1,quote='Fact alpha',role='support')])
                else:
                    rating=dict(**common,**{k:'yes' for k in r.FIELDS},citations=[dict(source='answer',quote='answer is alpha'),dict(source='document',doc_slot=1,quote='Fact alpha')])
                ratings.append(rating)
            value=dict(reviewer='fresh_context_'+task,independent_human_gold=False,packet_sha256=r.digest(self.base/(task+'_public/packet.json')),ratings=ratings)
            r.put(self.base/('reviewers/'+task+'/ratings.json'),value)

    def test_input_packet_has_no_answers_labels_probe_or_original_ids(self):
        packet=r.read(self.base/'input_public/packet.json')
        self.assertEqual(len(packet['items']),40)
        for item in packet['items']:
            self.assertEqual(set(item),{'item_id','question','documents'})
            self.assertEqual(len(item['documents']),5)
        behavior=r.read(self.base/'behavior_public/packet.json')
        self.assertTrue(all(set(x)=={'item_id','question','documents','answer'} for x in behavior['items']))

    def test_separate_permutations_and_no_source_write(self):
        before=r.inventory(); mapping=r.read(self.base/'coordinator/mapping.json')
        self.assertEqual(len({v['input_item_id'] for v in mapping.values()}),40)
        self.assertEqual(len({v['behavior_item_id'] for v in mapping.values()}),40)
        self.assertNotEqual([v['input_item_id'][1:] for v in mapping.values()],[v['behavior_item_id'][1:] for v in mapping.values()])
        r.prepare(self.base); self.assertEqual(before,r.inventory())

    def test_changed_quote_or_wrong_batch_rejected(self):
        self.make_reviews();path=self.base/'reviewers/input/ratings.json';original=r.read(path)
        value=copy.deepcopy(original);value['ratings'][0]['citations'][0]['quote']='Fabricated quote'
        path.write_text(r.encoded(value))
        with self.assertRaises(AssertionError):r.validate(self.base,'input')
        value=copy.deepcopy(original);value['packet_sha256']='wrong batch';path.write_text(r.encoded(value))
        with self.assertRaises(AssertionError):r.validate(self.base,'input')

    def test_duplicate_id_rejected_and_unknown_preserved(self):
        self.make_reviews();path=self.base/'reviewers/behavior/ratings.json';original=r.read(path)
        value=copy.deepcopy(original);value['ratings'][0]['item_id']=value['ratings'][1]['item_id'];path.write_text(r.encoded(value))
        with self.assertRaises(AssertionError):r.validate(self.base,'behavior')
        value=copy.deepcopy(original);value['ratings'][0]['has_substantive_answer']='unknown';path.write_text(r.encoded(value))
        self.assertEqual(len(r.validate(self.base,'behavior')),40)
        result=r.rate([dict(behavior_review={'answer':'yes'}),dict(behavior_review={'answer':'unknown'})],'answer')
        self.assertEqual((result['n'],result['point_estimate'],result['lower'],result['upper']),(2,None,.5,1.0))

    def test_join_uses_reviewed_semantics_preserves_old_files_and_replays(self):
        self.make_reviews();before=r.inventory();summary=r.analyze(self.base,write=True)
        self.assertEqual(summary['input_review_counts'],{'answer':19,'refuse':11,'conflict':10})
        self.assertEqual(len(summary['three_core_checks']['S_false_conflict_ids']),9)
        self.assertEqual(summary['primary_rates_by_semantic_mode']['refuse']['has_substantive_answer']['n'],11)
        self.assertEqual(summary['primary_rates_by_semantic_mode']['answer']['has_substantive_answer']['n'],9)
        self.assertEqual(summary,r.analyze(self.base,write=False));self.assertEqual(before,r.inventory())

    def test_source_change_blocks_join(self):
        self.make_reviews();path=self.source/'materials/inputs.json';path.write_text(path.read_text()+' ')
        with self.assertRaises(AssertionError):r.analyze(self.base,write=True)


if __name__=='__main__':unittest.main()
