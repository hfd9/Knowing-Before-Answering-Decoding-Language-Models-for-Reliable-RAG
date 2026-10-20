"""Versioned author repair must preserve first draft and all frozen budgets."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import semantic_transfer_materials as original
import semantic_transfer_materials_v2 as revision


class MaterialRevisionTests(unittest.TestCase):
    def test_versioned_builder_does_not_mutate_original_module_or_spec(self):
        previous=original.digest(original.AUTHORED);core=revision.load_core()
        self.assertNotEqual(core.AUTHORED,original.AUTHORED)
        self.assertEqual(original.AUTHORED,ROOT/'prompts/semantic_transfer_materials_v1.json')
        self.assertEqual(original.digest(original.AUTHORED),previous)

    def test_locations_removed_without_changing_question_and_minimal_answer(self):
        core=revision.load_core();spec=core.read(core.AUTHORED);old=original.read(original.AUTHORED)
        units={u['original_id']:u for u in spec['units']};prior={u['original_id']:u for u in old['units']}
        self.assertEqual(units['train_1179']['question'],prior['train_1179']['question'])
        for expr in ['A','B']:
            text=units['train_1179']['expressions'][expr]['I'][0]
            self.assertNotIn('Yunfu',text);self.assertNotIn('Guangdong',text);self.assertNotIn('China',text)
        self.assertNotIn('Waste heat',units['train_315']['authored_answer'])
        self.assertEqual({u['original_id'] for u in spec['units']},{u['original_id'] for u in old['units']})

    def test_real_cpu_prepare_verify_binds_both_implementation_versions(self):
        import evidence_experiment as e
        core=revision.load_core();before={str(p):core.digest(p) for p in [original.AUTHORED,core.AUTHORED,core.DESIGN,core.OLD_PROBE]}
        with tempfile.TemporaryDirectory() as folder,patch.object(e,'load_model',side_effect=AssertionError('No weights/GPU')):
            base=Path(folder)/'v2';base.mkdir();result=core.prepare(base,write=True)
            self.assertEqual((result['constructed'],result['unavailable']),(168,72))
            protocol=core.read(base/'protocol.json')
            self.assertEqual(protocol['material_version'],2)
            self.assertIn('scripts/semantic_transfer_materials.py',protocol['implementation_sha256'])
            self.assertIn('scripts/semantic_transfer_materials_v2.py',protocol['implementation_sha256'])
            snapshot={str(p):core.digest(p) for p in base.rglob('*') if p.is_file()}
            core.prepare(base,write=False)
            self.assertEqual(snapshot,{str(p):core.digest(p) for p in base.rglob('*') if p.is_file()})
            self.assertEqual(core.read(base/'preflight.json')['semantic_coverage'],0.0)
        self.assertEqual(before,{str(p):core.digest(Path(p)) for p in before})


if __name__=='__main__':unittest.main()
