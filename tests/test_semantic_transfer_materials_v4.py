"""Source augmentation repairs construction without changing independent-review requirements."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import semantic_transfer_materials_v4 as revision


class SourceAugmentedMaterialTests(unittest.TestCase):
    def test_exactly_missing_eight_units_change_and_all240_remain_grouped(self):
        core = revision.load_core()
        design, spec, selected, partition = core.load_sources()
        catalog, _ = core.build_catalog(selected)
        rows, missing, judgments, edits, bases, pairs = core.assemble(design, spec, selected, partition, catalog)
        self.assertEqual((len(rows), len(missing), len(pairs)), (240, 0, 300))
        self.assertTrue(all(r['semantic_label'] is None for r in rows))
        for base in bases:
            own = [r for r in rows if r['original_id'] == base['original_id']]
            self.assertEqual(len(own), 8)
            self.assertEqual(len({r['question'] for r in own}), 1)
            self.assertEqual({r['partition'] for r in own}, {partition[base['original_id']]})
        self.assertEqual(len(edits), 180)

    def test_false_source_quote_or_unlisted_extra_edit_is_rejected(self):
        core = revision.load_core()
        spec = core.read(core.AUTHORED)
        altered = copy.deepcopy(spec)
        u = next(u for u in altered['units'] if u.get('supplemental_source_citations'))
        u['supplemental_source_citations'][0]['quote'] = 'fabricated evidence'
        with self.assertRaises(AssertionError):
            core.validate_augmentation(altered)
        altered = copy.deepcopy(spec)
        altered['units'][0]['question'] += ' Changed.'
        with self.assertRaises(AssertionError):
            core.validate_augmentation(altered)

    def test_source_version_event_and_missing_premise_are_explicit(self):
        core = revision.load_core()
        units = {u['original_id']: u for u in core.read(core.AUTHORED)['units']}
        self.assertIn('market debut', units['train_1136']['question'])
        self.assertIn('supplied version', units['train_1154']['question'])
        self.assertIn('combat campaigns', units['train_1605']['question'])
        for expr in ['A', 'B']:
            self.assertNotIn('1958', ' '.join(units['train_1136']['expressions'][expr]['I']))
            self.assertNotIn('horse', ' '.join(units['train_1154']['expressions'][expr]['I']))
            self.assertNotIn('Wayne', ' '.join(units['train_1805']['expressions'][expr]['I']))
            self.assertNotIn('1950', ' '.join(units['train_1605']['expressions'][expr]['I']))
            self.assertNotIn('March', ' '.join(units['train_254']['expressions'][expr]['I']))
            self.assertNotIn('sashimi', ' '.join(units['train_33']['expressions'][expr]['I']).lower())
        # These checks concern target text only; unrelated March dates remain in full backgrounds.
        self.assertIn('pie', units['train_1154']['expressions']['A']['K'][1])

    def test_real_cpu_prepare_verify_marks_construction_only_and_preserves_old_versions(self):
        import evidence_experiment as e
        core = revision.load_core()
        frozen = [ROOT / 'prompts/semantic_transfer_materials_v3.json', core.DESIGN,
            ROOT / 'scripts/semantic_transfer_materials.py', ROOT / 'scripts/semantic_transfer_review_intake.py', core.OLD_PROBE]
        before = {p: core.digest(p) for p in frozen}
        with tempfile.TemporaryDirectory() as folder, patch.object(e, 'load_model', side_effect=AssertionError('No model/GPU')):
            base = Path(folder) / 'materials'
            base.mkdir()
            result = core.prepare(base, write=True)
            self.assertEqual((result['constructed'], result['unavailable']), (240, 0))
            gate = core.read(base / 'review_gate.json')
            self.assertTrue(gate['construction_coverage_requirement_met'])
            self.assertFalse(gate['gpu_launch_ready'])
            self.assertEqual(gate['minimum_frozen_semantic_coverage'], 0.90)
            self.assertFalse(any('below90%' in reason for reason in gate['reasons']))
            self.assertEqual(core.read(base / 'preflight.json')['semantic_coverage'], 0.0)
            protocol = core.read(base / 'protocol.json')
            self.assertEqual(protocol['material_version'], 4)
            self.assertEqual(protocol['supplemental_sources_sha256'], core.digest(revision.SOURCES))
            snapshot = {p: core.digest(p) for p in base.rglob('*') if p.is_file()}
            core.prepare(base, write=False)
            self.assertEqual(snapshot, {p: core.digest(p) for p in snapshot})
            import semantic_transfer_review_intake as intake
            report = intake.process(base, Path(folder) / 'intake')
            self.assertEqual(report['construction_coverage'], 1.0)
            self.assertFalse(report['approved_for_training'])
            self.assertEqual(report['approved_semantic_labels'], 0)
        self.assertEqual(before, {p: core.digest(p) for p in frozen})


if __name__ == '__main__':
    unittest.main()
