"""Source provenance, incomplete denominators, blinding and CPU-only material lifecycle."""

import copy
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import semantic_transfer_materials as m


class TransferMaterialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.design,cls.spec,cls.sources,cls.partitions=m.load_sources()
        cls.catalog,_=m.build_catalog(cls.sources)
        cls.inputs,cls.missing,cls.judgments,cls.edits,cls.reviews,cls.pairs=m.assemble(cls.design,cls.spec,cls.sources,cls.partitions,cls.catalog)

    def test_complete_and_incomplete_cells_keep_all30_grouped_bases(self):
        self.assertEqual((len(self.inputs),len(self.missing)),(168,72))
        self.assertEqual(len({r['id'] for r in self.inputs+self.missing}),240)
        self.assertEqual({r['original_id'] for r in self.inputs+self.missing},set(self.partitions))
        for oid in self.partitions:
            own=[r for r in self.inputs+self.missing if r['original_id']==oid]
            self.assertEqual(len(own),8);self.assertEqual({r['partition'] for r in own},{self.partitions[oid]})
        self.assertEqual([sum(r['partition']==part for r in self.inputs) for part in self.design['partitions']],[72,40,56])
        self.assertTrue(all(r['semantic_label'] is None for r in self.inputs+self.missing+self.judgments))

    def test_questions_backgrounds_slots_fixed_and_conflict_edits_targetB_only(self):
        for oid in {r['original_id'] for r in self.inputs}:
            own=[r for r in self.inputs if r['original_id']==oid]
            self.assertEqual(len({r['question'] for r in own}),1)
            reference=own[0]
            for row in own:
                self.assertEqual(row['target_slots'],reference['target_slots'])
                for slot in range(1,6):
                    if slot not in reference['target_slots']:self.assertEqual(row['docs'][slot-1],reference['docs'][slot-1])
            for expr in ['A','B']:
                s=next(r for r in own if r['expression']==expr and r['condition']=='S')
                c=next(r for r in own if r['expression']==expr and r['condition']=='C')
                changed=[i+1 for i,(a,b) in enumerate(zip(s['docs'],c['docs'])) if a!=b]
                self.assertEqual(changed,[s['target_slots'][1]])

    def test_all_source_and_target_citations_are_exact_and_tamper_rejected(self):
        docs={d['doc_id']:d['text'] for d in self.catalog['documents']}
        self.assertEqual(sum(len(u['source_citations']) for u in self.spec['units']),53)
        for u in self.spec['units']:
            for c in u['source_citations']:self.assertEqual(docs[c['doc_id']][c['start']:c['end']],c['quote'])
        lookup={r['id']:r for r in self.inputs}
        for judgment in self.judgments:
            for c in judgment['citations']:self.assertEqual(lookup[judgment['id']]['docs'][c['doc_slot']-1][c['start']:c['end']],c['quote'])
        changed=copy.deepcopy(self.spec);changed['units'][0]['source_citations'][0]['quote']='Fabricated'
        with self.assertRaises(AssertionError):m.assemble(self.design,changed,self.sources,self.partitions,self.catalog)

    def test_all126_edit_records_reconstruct_targets(self):
        lookup={r['id']:r for r in self.inputs};self.assertEqual(len(self.edits),126)
        for record in self.edits:
            old=lookup[record['reference']]['docs'];new=lookup[record['id']]['docs']
            for slot in range(1,6):
                text=old[slot-1]
                for change in sorted([x for x in record['changes'] if x['doc_slot']==slot],key=lambda x:x['before_start'],reverse=True):
                    self.assertEqual(text[change['before_start']:change['before_end']],change['before'])
                    text=text[:change['before_start']]+change['after']+text[change['before_end']:]
                self.assertEqual(text,new[slot-1])

    def test_two_review_packets_hide_labels_identity_and_outputs(self):
        packets,mapping=m.make_review_packets(self.inputs)
        for task,packet in packets.items():
            self.assertEqual(len(packet['items']),168)
            for item in packet['items']:self.assertEqual(set(item),{'item_id','question','documents'})
        self.assertEqual(set(mapping),{r['id'] for r in self.inputs})
        self.assertNotEqual([x['a'] for x in mapping.values()],[x['b'] for x in mapping.values()])

    def test_pair_groups_do_not_treat_variants_as_independent_bases(self):
        self.assertEqual(len(self.pairs),210)
        for oid in {r['original_id'] for r in self.inputs}:
            own=[p for p in self.pairs if p['original_id']==oid]
            self.assertEqual(len(own),10);self.assertEqual(len({p['partition'] for p in own}),1)
        self.assertEqual(len({p['original_id'] for p in self.pairs}),21)

    def test_shared_backgrounds_and_old_train_overlap_disclosed(self):
        audit=m.overlap_audit(self.inputs,self.catalog,self.partitions)
        self.assertEqual(audit['shared_backgrounds_across_partitions'][0]['doc_id'],'T023')
        self.assertGreater(audit['used_backgrounds_exactly_seen_in_old_probe_train'],0)
        self.assertIn('not all entity knowledge',audit['caveat'])

    def test_real_tokenizer_cpu_prepare_verify_preserves_sources_and_blocks_gpu(self):
        import evidence_experiment as e
        source_hashes={str(p):m.digest(p) for p in [m.ARCHIVE,m.MANIFEST,m.TRAIN600,m.OLD_FREE,m.OLD_PROBE,m.AUTHORED,m.DESIGN]}
        with tempfile.TemporaryDirectory() as folder,patch.object(e,'load_model',side_effect=AssertionError('GPU/model weights must not load')):
            base=Path(folder)/'materials';base.mkdir()
            first=m.prepare(base,write=True)
            self.assertEqual((first['constructed'],first['unavailable'],first['independent_semantic_labels']),(168,72,0))
            self.assertGreater(first['min_tokens'],0);self.assertLess(first['max_tokens']+128,32768)
            gate=m.read(base/'review_gate.json');self.assertFalse(gate['gpu_launch_ready']);self.assertEqual(gate['construction_coverage'],.7)
            self.assertTrue(gate['author_intents_must_not_be_used_as_training_gold'])
            before={str(p):m.digest(p) for p in base.rglob('*') if p.is_file()}
            m.prepare(base,write=False)
            self.assertEqual(before,{str(p):m.digest(p) for p in base.rglob('*') if p.is_file()})
            page=base/'review_a/review.html';original=page.read_text();page.write_text(original+' altered')
            with self.assertRaises(ValueError):m.prepare(base,write=False)
            page.write_text(original)
            path=base/'materials/inputs.json';value=m.read(path);value[0]['docs'][0]+='TAMPER';path.write_text(m.json_text(value))
            with self.assertRaises(ValueError):m.prepare(base,write=False)
        self.assertEqual(source_hashes,{str(p):m.digest(Path(p)) for p in source_hashes})

    def test_cli_has_no_gpu_stage(self):
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/semantic_transfer_materials.py'),'--stage','run'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2);self.assertIn('invalid choice',result.stderr)


if __name__=='__main__':unittest.main()
