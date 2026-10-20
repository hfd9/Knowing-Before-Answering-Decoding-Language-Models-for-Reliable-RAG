"""Budget, grouping and untouched-train selection checks for the frozen next-round design."""

import hashlib
import json
from pathlib import Path
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]


class TransferDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=json.loads((ROOT/'prompts/semantic_transfer_validation_v1.json').read_text())

    def test_base_partitions_disjoint_all_variants_grouped(self):
        groups=self.spec['partitions'];self.assertEqual([len(x) for x in groups.values()],[12,6,12])
        self.assertEqual(len(set(x for group in groups.values() for x in group)),30)
        assigned={}
        for partition,ids in groups.items():
            for oid in ids:
                for expression in self.spec['construction']['expressions']:
                    for state in self.spec['construction']['semantic_conditions']:
                        assigned[(oid,expression,state)]=partition
        self.assertEqual(len(assigned),240)
        self.assertTrue(all(len({partition for key,partition in assigned.items() if key[0]==oid})==1 for group in groups.values() for oid in group))

    def test_sample_replays_from_train_member_only_and_excludes_existing_probe_train(self):
        manifest=json.loads((ROOT/'runs/qwen2.5-3b-small/data/manifest.json').read_text())
        excluded=set(manifest['splits']['train']['original_ids'])
        with zipfile.ZipFile(ROOT/'dataset/instances.zip') as z:
            rows=[json.loads(line) for line in z.read('instances_train.jsonl').decode().splitlines() if line.strip()]
        self.assertEqual(len(rows),5463);self.assertTrue(all(x['split']=='train' for x in rows))
        eligible={x['original_id'] for x in rows}-excluded
        salt=self.spec['source']['salt']
        ranked=sorted(eligible,key=lambda x:hashlib.sha256((salt+'|'+x).encode()).hexdigest())[:30]
        selected=[x for group in self.spec['partitions'].values() for x in group]
        self.assertEqual(selected,ranked);self.assertFalse(set(selected)&excluded)
        normalize=lambda t:' '.join(t.lower().split())
        old_questions={normalize(x['question']) for x in rows if x['original_id'] in excluded}
        new_questions={x['original_id']:normalize(x['question']) for x in rows if x['original_id'] in selected}
        self.assertFalse(set(new_questions.values())&old_questions)
        self.assertEqual(len(set(new_questions.values())),30)

    def test_fit_and_construction_budgets_cannot_expand(self):
        c=self.spec['construction'];p=self.spec['probe']
        self.assertEqual((c['bases'],c['variants_per_base'],c['maximum_variants']),(30,8,240))
        self.assertEqual(c['replacements_allowed'],0);self.assertFalse(c['repeat_previous_52_80_50_cells'])
        self.assertEqual(p['candidate_layers_zero_based'],[28]);self.assertEqual(p['max_training_fits'],1)
        self.assertEqual((p['hyperparameter_candidates'],p['calibration_fits'],p['threshold_tuning'],p['dev_refits']),(1,0,0,0))

    def test_semantic_compatibility_and_independent_behavior_are_explicit(self):
        self.assertIn('K_compatible_complete',self.spec['construction']['semantic_conditions'])
        self.assertIn('AGENTS.md',self.spec['construction']['history_independence_gate'])
        self.assertIn('hidden probe',self.spec['behavior']['review'])
        self.assertTrue(self.spec['source']['no_original_test_or_confirmation_member_opened'])
        self.assertEqual(self.spec['status'],'design_frozen_materials_not_prepared_no_gpu')


if __name__=='__main__':unittest.main()
