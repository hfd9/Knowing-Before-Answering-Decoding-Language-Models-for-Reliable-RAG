"""A fresh process must reproduce overlap audit order without rewriting frozen artifacts."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import semantic_transfer_materials_v4_replay as repair


class MaterialReplayTests(unittest.TestCase):
    def test_overlap_lists_are_sorted_independent_of_input_permutation(self):
        core = repair.load_core()
        a = dict(shared_backgrounds_across_partitions=[dict(doc_id='T092'), dict(doc_id='T023')])
        b = dict(shared_backgrounds_across_partitions=list(reversed(a['shared_backgrounds_across_partitions'])))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'overlap_audit.json'
            core.put(path, a, True)
            before = path.read_bytes()
            core.put(path, b, False)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([r['doc_id'] for r in core.read(path)['shared_backgrounds_across_partitions']], ['T023', 'T092'])
        self.assertEqual(a['shared_backgrounds_across_partitions'][0]['doc_id'], 'T092')

    def test_real_prepare_and_verify_in_separate_hash_seed_processes(self):
        with tempfile.TemporaryDirectory() as folder:
            base = str(Path(folder) / 'materials')
            code = ('import sys;from pathlib import Path;'
                'sys.path.insert(0,str(Path.cwd()/"scripts"));'
                'import semantic_transfer_materials_v4_replay as r;'
                'p=Path(sys.argv[1]);p.mkdir(exist_ok=True);'
                'print(r.load_core().prepare(p,write=sys.argv[2]=="prepare"))')
            for mode, seed in [('prepare', '1'), ('verify', '2'), ('verify', '2718')]:
                env = dict(os.environ, PYTHONHASHSEED=seed)
                result = subprocess.run([sys.executable, '-B', '-c', code, base, mode], cwd=ROOT,
                    env=env, text=True, capture_output=True, timeout=90)
                self.assertEqual(result.returncode, 0, result.stderr)
            protocol = json.loads((Path(base) / 'protocol.json').read_text())
            self.assertEqual(protocol['material_replay_revision'], 2)
            self.assertIn('scripts/semantic_transfer_materials_v4.py', protocol['implementation_sha256'])
            self.assertEqual(len(json.loads((Path(base) / 'materials/inputs.json').read_text())), 240)


if __name__ == '__main__':
    unittest.main()
