"""Source resolution must preserve the task, source boundaries, and old versions."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import semantic_transfer_materials as original
import semantic_transfer_materials_v2 as previous
import semantic_transfer_materials_v3 as revision


class SourceResolutionTests(unittest.TestCase):
    def test_only_ambiguous_referent_is_changed_without_filling_missing_relations(self):
        core = revision.load_core()
        old = previous.load_core().read(previous.load_core().AUTHORED)
        new = core.read(core.AUTHORED)
        changed = [a['original_id'] for a, b in zip(old['units'], new['units']) if a != b]
        self.assertEqual(changed, ['train_744'])
        james = next(u for u in new['units'] if u['original_id'] == 'train_744')
        self.assertIn('of Scots (1430–1460)', james['question'])
        self.assertIn('changes the source question scope', james['question_change_reason'])
        self.assertEqual(len([u for u in new['units'] if u['expressions'] is None]), 8)
        self.assertIsNone(next(u for u in old['units'] if u['original_id'] == 'train_744')['expressions'])
        audit = core.read(ROOT / 'prompts/semantic_transfer_source_resolution_v1.json')
        self.assertEqual(len(audit['decisions']), 9)
        self.assertEqual(audit['full_passages_read_count'], 49)
        self.assertTrue(audit['source_scope_unchanged'])
        self.assertEqual(audit['independent_semantic_labels'], 0)

    def test_all_source_quotes_offsets_and_retained_backgrounds_rebuild(self):
        core = revision.load_core()
        design, spec, selected, partition = core.load_sources()
        catalog, _ = core.build_catalog(selected)
        rows, missing, judgments, edits, _, pairs = core.assemble(design, spec, selected, partition, catalog)
        self.assertEqual((len(rows), len(missing), len(pairs)), (176, 64, 220))
        james = [r for r in rows if r['original_id'] == 'train_744']
        self.assertEqual(len(james), 8)
        self.assertTrue(all(r['partition'] == 'semantic_train' and r['semantic_label'] is None for r in james))
        by_id = {r['id']: r for r in rows}
        for expression in ['A', 'B']:
            s = by_id[f'stv07_{expression}_S']
            i = by_id[f'stv07_{expression}_I']
            self.assertEqual(s['question'], i['question'])
            for slot in range(1, 6):
                if slot not in s['target_slots']:
                    self.assertEqual(s['docs'][slot - 1], i['docs'][slot - 1])

    def test_real_cpu_prepare_readonly_verify_preserves_prior_implementations(self):
        import evidence_experiment as e
        core = revision.load_core()
        paths = [original.AUTHORED, previous.load_core().AUTHORED, core.DESIGN, core.OLD_PROBE,
            ROOT / 'scripts/semantic_transfer_materials.py', ROOT / 'scripts/semantic_transfer_materials_v2.py']
        before = {p: core.digest(p) for p in paths}
        with tempfile.TemporaryDirectory() as folder, patch.object(e, 'load_model', side_effect=AssertionError('No model/GPU')):
            base = Path(folder)
            result = core.prepare(base, write=True)
            self.assertEqual((result['constructed'], result['unavailable']), (176, 64))
            protocol = core.read(base / 'protocol.json')
            self.assertEqual(protocol['material_version'], 3)
            self.assertEqual(protocol['source_resolution_audit_sha256'], core.digest(ROOT / 'prompts/semantic_transfer_source_resolution_v1.json'))
            snapshot = {p: core.digest(p) for p in base.rglob('*') if p.is_file()}
            core.prepare(base, write=False)
            self.assertEqual(snapshot, {p: core.digest(p) for p in snapshot})
            self.assertFalse(core.read(base / 'review_gate.json')['gpu_launch_ready'])
        self.assertEqual(before, {p: core.digest(p) for p in paths})


if __name__ == '__main__':
    unittest.main()
