"""Version binding, unchanged gates and run-budget checks; no actual model inference."""

import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import semantic_transfer_study_v5 as v5


class V5StudyTests(unittest.TestCase):
    def test_location_guards_keep_all_frozen_runs_separate(self):
        v5.validate_locations(v5.MATERIALS, v5.DEFAULT)
        for run in [v5.core.DEFAULT, v5.MATERIALS, v5.ACCEPTANCE,
                v5.core.DEFAULT / 'nested', ROOT / 'runs', ROOT / 'elsewhere']:
            with self.assertRaises(ValueError):
                v5.validate_locations(v5.MATERIALS, run)
        with self.assertRaisesRegex(ValueError, 'frozen v5'):
            v5.validate_locations(v5.core.MATERIALS, v5.DEFAULT)

    def test_actual_v5_dependencies_and_old_v4_version_rejected(self):
        rows, mapping, packets, _ = v5.material_inputs(v5.MATERIALS)
        self.assertEqual((len(rows), len(mapping), len(packets['a']['items'])), (240, 240, 240))
        self.assertTrue(all(row['semantic_label'] is None for row in rows))
        with self.assertRaisesRegex(ValueError, 'Expected v5'):
            v5.material_inputs(v5.core.MATERIALS)
        original = v5.read
        def wrong_revision(path):
            value = original(path)
            if Path(path) == v5.MATERIALS/'protocol.json':
                value = copy.deepcopy(value)
                value['control_revision_sha256'] = '0'*64
            return value
        with patch.object(v5, 'read', side_effect=wrong_revision):
            with self.assertRaisesRegex(ValueError, 'snapshot changed'):
                v5.material_inputs(v5.MATERIALS)

    def test_author_acceptance_modes_never_supply_approved_labels(self):
        rows, mapping, packets, design = v5.material_inputs(v5.MATERIALS)
        labels, gate, evidence = v5.core.approval_labels(v5.MATERIALS, rows, mapping, packets, design, None)
        self.assertEqual(len(labels), 240)
        self.assertTrue(all(label is None for label in labels.values()))
        self.assertEqual((gate['approved_semantic_labels'], gate['audited_context_receipts']), (0, 0))
        self.assertFalse(gate['gpu_launch_ready'])
        self.assertEqual(evidence, {})

    def test_real_cli_all_inference_stages_fail_at_closed_gate_before_loading(self):
        # Missing implementation config, tokenizer and model/probe access would
        # fail differently. The closed persisted gate must be the first error.
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as folder:
            run=Path(folder)
            v5.put(run/'review_gate.json', {'gpu_launch_ready':False})
            for stage in ['run','analyze','verify-results']:
                result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/semantic_transfer_study_v5.py'),
                    '--stage',stage,'--run-dir',str(run)],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('Review gate closed',result.stderr)
                self.assertEqual({p.name for p in run.iterdir()},{'review_gate.json'})

    def test_same_design_fit_attempt_in_other_version_blocks_new_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);run=root/'current';old=root/'old_version'
            v5.put(old/'fit_attempt.json',{'synthetic_only':True})
            v5.put(old/'protocol.json',{'task':'semantic_transfer_chat_L28_v1',
                'design_sha256':v5.digest(v5.core.intake.DESIGN)})
            with self.assertRaisesRegex(ValueError,'already has a fit attempt'):
                v5.require_shared_fit_budget(run,root)
            # Resume of the same attempted run remains governed by the unchanged
            # core's own attempt/metadata checks; unrelated designs do not spend it.
            v5.require_shared_fit_budget(old,root)
            (old/'protocol.json').write_text(v5.serialize({'task':'semantic_transfer_chat_L28_v5_v1',
                'design_sha256':'unrelated_synthetic_design'}))
            v5.require_shared_fit_budget(run,root)

    def test_binding_import_does_not_mutate_old_defaults_or_frozen_sources(self):
        expected=ROOT/'runs/qwen2.5-3b-semantic-transfer-materials-v4-r2'
        self.assertEqual(v5.core.MATERIALS,expected)
        self.assertNotEqual(v5.DEFAULT,v5.core.DEFAULT)
        preserved=v5.read(ROOT/'docs/records/2026-10-21-semantic-transfer-v5-acceptance-preserved.json')
        self.assertTrue(all(v5.digest(ROOT/name)==sha for name,sha in preserved.items()))


if __name__ == '__main__':
    unittest.main()
