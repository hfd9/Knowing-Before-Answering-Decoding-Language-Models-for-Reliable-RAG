import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import prepare_explanation_scope_materials as draft


class ScopeMaterialChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)
        self.plan = json.loads((ROOT / 'docs/review/2026-11-06-explanation-scope-materials-v2/design-lock.json').read_text())

    def tearDown(self):
        self.temp.cleanup()

    def generate(self):
        (self.out / 'design-lock.json').write_text(json.dumps(self.plan), encoding='utf-8')
        return draft.generate(self.out)

    def test_conflicting_reports_require_two_independent_repairs(self):
        result = self.generate()
        examples = result['coordinator.json']['witnesses']['exs01_IU']['local_repair_witnesses']
        self.assertEqual(len(examples), 4)
        scene = self.plan['scenes'][0]
        target_sets = {}
        for example in examples:
            world = {(x['entity'], x['field']): x['value'] for x in example['world']}
            target_sets.setdefault(example['dropped_record_index'], set()).add(world[(scene['target'], scene['f'])])
        self.assertEqual(target_sets, {0: set(scene['alternative_target_values']), 1: set(scene['alternative_target_values'])})

    def test_missing_treatment_edit_is_rejected(self):
        self.plan['condition_assignments']['IU'] = dict(self.plan['condition_assignments']['I0'])
        with self.assertRaises(AssertionError):
            self.generate()

    def test_colliding_values_are_rejected(self):
        self.plan['scenes'][0]['b'] = self.plan['scenes'][0]['a']
        with self.assertRaises(AssertionError):
            self.generate()


if __name__ == '__main__':
    unittest.main()
