"""Versioned data integrity and CPU replay tests, not independent semantic judgments."""

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import semantic_transfer_materials_v5 as revision


class RelationRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = revision.load_core()
        cls.design, cls.spec, cls.selected, cls.partition = cls.core.load_sources()
        cls.catalog, _ = cls.core.build_catalog(cls.selected)
        cls.result = cls.core.assemble(cls.design, cls.spec, cls.selected, cls.partition, cls.catalog)
        cls.rows = cls.result[0]

    def test_independent_parent_row_patch_rebuild_matches_all240(self):
        parent = self.core.read(revision.PARENT_RUN / 'materials/inputs.json')
        expected = copy.deepcopy(parent)
        by_id = {r['id']: r for r in expected}
        for edit in self.core.read(revision.REVISION)['document_changes']:
            self.assertEqual(by_id[edit['id']]['docs'][edit['doc_slot'] - 1], edit['before'])
            by_id[edit['id']]['docs'][edit['doc_slot'] - 1] = edit['after']
        self.assertEqual(expected, self.rows)
        changed = [a['id'] for a, b in zip(self.rows, parent) if a != b]
        self.assertEqual(len(changed), 83)
        self.assertEqual(sum('_I' in key for key in changed), 54)
        self.assertEqual((len(self.rows), len(self.result[1]), len(self.result[5])), (240, 0, 300))
        self.assertTrue(all(r['semantic_label'] is None for r in self.rows))

    def test_unlisted_change_question_or_source_quote_is_rejected(self):
        for mutate in [lambda s: s['units'][0].update(question='Unlisted question change'),
                lambda s: s['units'][0]['expressions']['A']['I'].__setitem__(0, 'Unlisted fact in 1999.'),
                lambda s: s['units'][0]['source_citations'][0].update(quote='false source quote')]:
            value = copy.deepcopy(self.spec)
            mutate(value)
            with self.assertRaises(AssertionError):
                self.core.validate_revision(value)

    def test_retained_names_and_clues_are_not_silently_deleted(self):
        units = {u['original_id']: u for u in self.spec['units']}
        for expression in ['A', 'B']:
            self.assertIn('Sharon Needles', ' '.join(units['train_1492']['expressions'][expression]['I']))
            self.assertIn('Pittsburgh', ' '.join(units['train_1492']['expressions'][expression]['I']))
            self.assertIn('Pachisi', ' '.join(units['train_1150']['expressions'][expression]['I']))
            self.assertIn('chess-like', ' '.join(units['train_1333']['expressions'][expression]['I']))
            # The queried revealing event's alias is part of the answer route, not an unrelated name.
            self.assertNotIn('showdown', ' '.join(units['train_989']['expressions'][expression]['I']))
            self.assertNotIn('runner-up', ' '.join(units['train_1525']['expressions'][expression]['I']))
            self.assertNotIn('Pearl Jam', ' '.join(units['train_1805']['expressions'][expression]['I']))
            self.assertNotIn('rice', ' '.join(units['train_33']['expressions'][expression]['I']))
            self.assertNotIn('Buckeye', ' '.join(units['train_1470']['expressions'][expression]['I']))
            self.assertNotIn('born Kevin', ' '.join(units['train_335']['expressions'][expression]['K']))

    def test_poker_modality_and_sunday_terminology_repairs(self):
        units = {u['original_id']: u for u in self.spec['units']}
        for expression in ['A', 'B']:
            poker = units['train_989']['expressions'][expression]
            self.assertEqual(poker['S'][0], poker['C'][0])
            self.assertNotIn('must', poker['C'][1])
            self.assertNotIn('prohibited', poker['C'][1])
            self.assertIn('concealed', poker['C'][1])
            for condition in ['S', 'K']:
                self.assertNotIn('weekday', ' '.join(units['train_1302']['expressions'][expression][condition]))
        self.assertNotIn('sushi', units['train_33']['expressions']['B']['K'][1])
        self.assertIn('human', units['train_315']['expressions']['A']['S'][0].lower())
        self.assertNotIn('human', ' '.join(units['train_315']['expressions']['A']['I']).lower())

    def test_ledgers_keep_author_limits_and_residual_risks_explicit(self):
        audit = self.core.revision_audit
        self.assertEqual(len(audit['I_relation_ledgers']), 60)
        self.assertEqual(len(audit['previous_AB_caveats']), 18)
        self.assertTrue(all(not r['independent_entailment_verified'] and
            not r['literal_or_formal_single_atom_minimality_proved'] for r in audit['I_relation_ledgers']))
        self.assertEqual(audit['independent_semantic_labels'], 0)
        self.assertFalse(audit['gpu_launch_ready'])
        self.assertIn('train_989', {r['original_id'] for r in audit['residual_review_risks']})

    def test_each_expression_has_its_own_source_support_for_retained_attributes(self):
        units = {u['original_id']: u for u in self.spec['units']}
        # Regression: borrowing an A-only property into B I violates matched-expression controls.
        self.assertIn('state government meets', units['train_1470']['expressions']['B']['S'][1])
        for expression in ['A', 'B']:
            self.assertIn('private homes', units['train_1302']['expressions'][expression]['S'][0])
            self.assertIn('private homes', units['train_1302']['expressions'][expression]['I'][0])
            self.assertIn('a Stanley Cup win', units['train_1222']['expressions'][expression]['I'][1])
        for condition in ['S', 'K', 'C']:
            self.assertIn('James II Stewart', units['train_744']['expressions']['B'][condition][0])
        self.assertTrue(units['train_405']['expressions']['A']['I'][0].endswith('system is in Colorado.'))
        self.assertIn('commercial use', units['train_1136']['expressions']['B']['S'][1])
        self.assertIn('commercial use', units['train_1136']['expressions']['B']['I'][1])
        self.assertEqual(units['train_315']['expressions']['B']['S'][1], units['train_315']['expressions']['B']['I'][1])
        self.assertIn('usually', units['train_315']['expressions']['B']['S'][1])
        self.assertIn('winning pairs', units['train_32']['expressions']['B']['I'][0])

    def test_real_tokenizer_prepare_verify_handoff_and_intake_without_model(self):
        import evidence_experiment as e
        import semantic_transfer_review_intake as intake
        protected = [revision.PARENT, revision.PARENT_RUN / 'materials/inputs.json', revision.OLD_REVIEW,
            ROOT / 'scripts/semantic_transfer_materials.py', ROOT / 'scripts/semantic_transfer_study.py', self.core.OLD_PROBE]
        before = {p: self.core.digest(p) for p in protected}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(e, 'load_model', side_effect=AssertionError('No model loading')), \
                patch('pickle.load', side_effect=AssertionError('No probe deserialization')):
            base = Path(folder) / 'materials'
            base.mkdir()
            result = self.core.prepare(base, True)
            self.assertEqual(result['changed_cells'], 83)
            self.assertEqual(result['material_version'], 5)
            protocol = self.core.read(base / 'protocol.json')
            self.assertEqual(protocol['review_packet_shuffle_seeds'], revision.SEEDS)
            self.assertEqual(self.core.read(base / 'review_gate.json')['minimum_frozen_semantic_coverage'], .90)
            self.assertFalse(self.core.read(base / 'review_gate.json')['gpu_launch_ready'])
            for side in ['a', 'b']:
                packet = self.core.read(base / f'review_{side}/packet.json')
                self.assertEqual(len(packet['items']), 240)
                self.assertTrue(all(set(r) == {'item_id', 'question', 'documents'} for r in packet['items']))
                with zipfile.ZipFile(base / f'handoff/input-review-{side}.zip') as archive:
                    self.assertEqual(set(archive.namelist()), {'packet.json', 'rubric.json', 'ratings_template.json',
                        'review.html', 'README.txt', 'checksums.json'})
                    checksums = json.loads(archive.read('checksums.json'))
                    for name, sha in checksums.items():
                        self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), sha)
            snapshot = {p: self.core.digest(p) for p in base.rglob('*') if p.is_file()}
            self.core.prepare(base, False)
            self.assertEqual(snapshot, {p: self.core.digest(p) for p in snapshot})
            report = intake.process(base, Path(folder) / 'intake')
            self.assertEqual(report['approved_semantic_labels'], 0)
            self.assertFalse(report['gpu_launch_ready'])
        self.assertEqual(before, {p: self.core.digest(p) for p in protected})

    def test_cpu_replay_in_two_fresh_processes_has_stable_audits_and_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            base = str(Path(folder) / 'materials')
            code = ('import sys;from pathlib import Path;sys.path.insert(0,str(Path.cwd()/"scripts"));'
                'import semantic_transfer_materials_v5 as r;p=Path(sys.argv[1]);p.mkdir(exist_ok=True);'
                'print(r.load_core().prepare(p,write=sys.argv[2]=="prepare"))')
            for mode, seed in [('prepare', '1'), ('verify', '2')]:
                result = subprocess.run([sys.executable, '-B', '-c', code, base, mode], cwd=ROOT,
                    env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
