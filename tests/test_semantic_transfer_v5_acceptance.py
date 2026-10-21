"""Audit integrity, exposure boundaries and immutable delivery, not semantic truth."""

import copy
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import semantic_transfer_v5_acceptance as audit


class V5AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = audit.read(audit.MATERIALS / 'materials/inputs.json')
        cls.ratings = audit.read(audit.RATINGS)

    def test_false_quotes_missing_cells_and_wrong_batches_rejected(self):
        for mutation in [lambda v: v['ratings'][0]['citations'][0].update(quote='invented quote'),
                lambda v: v['ratings'][0]['citations'][0].update(start=-1),
                lambda v: v['ratings'].pop(), lambda v: v.update(inputs_sha256='0'*64),
                lambda v: v['ratings'][0].update(partition='semantic_eval')]:
            value = copy.deepcopy(self.ratings)
            mutation(value)
            with self.assertRaises(ValueError):
                audit.validate(self.rows, value)

    def test_exposure_cannot_be_upgraded_and_intake_rejects_author_judgments(self):
        for field, value in [('history_exposed', False), ('independent_gold', True),
                ('approved_for_training', True), ('gpu_launch_ready', True)]:
            ratings = copy.deepcopy(self.ratings)
            ratings[field] = value
            with self.assertRaisesRegex(ValueError, 'cannot approve'):
                audit.validate(self.rows, ratings)
        with self.assertRaisesRegex(ValueError, 'History-exposed'):
            audit.intake.validate_review(self.ratings, {}, '')

    def test_scope_uncertainty_detail_caveats_and_denominators_remain_distinct(self):
        summary, cells, pairs, si, repairs, risks, inventory = audit.derive(self.rows, self.ratings)
        self.assertEqual(len(cells), 240)
        self.assertEqual((len(pairs), len(si), len(repairs)), (300, 60, 18))
        self.assertEqual(summary['unknown_ids'], ['stv17_A_S', 'stv17_A_K', 'stv17_B_S', 'stv17_B_K'])
        self.assertEqual(summary['manual_semantic_counts'], {'answer':116, 'refuse':60, 'conflict':60, 'unknown':4})
        self.assertEqual(summary['S_to_I_pairs']['reviewed_answer_to_refuse'], 58)
        self.assertEqual(summary['AB_pairs']['residual_detail_or_scope_caveats'], 13)
        self.assertEqual(summary['AB_pairs']['same_determinate_mode'], 118)
        self.assertEqual((summary['approved_semantic_labels'], summary['independent_semantic_coverage']), (0, 0))
        self.assertTrue(all(c['formal_semantic_label'] is None for c in cells))
        self.assertTrue(all(p['probe_prediction'] is None and not p['literal_single_atom_minimality_proved'] for p in pairs))
        self.assertEqual(sum(len(d['occurrences']) for d in inventory['documents'].values()), 1200)
        self.assertEqual(len(inventory['background_slots']), 90)
        self.assertEqual(len(risks), 7)

    def test_changed_background_or_formal_labels_rejected(self):
        for key in ['background', 'formal_label']:
            rows = copy.deepcopy(self.rows)
            if key == 'background':
                rows[0]['docs'][2] += ' an added sentence'
            else:
                rows[0]['semantic_label'] = 'answer'
            if key == 'background':
                with self.assertRaisesRegex(ValueError, 'Background changed'):
                    audit.validate(rows, self.ratings)
            else:
                # load_materials also enforces this before validate. Check the
                # explicit null guard in the acceptance validator itself.
                with self.assertRaisesRegex(ValueError, 'Formal semantic labels'):
                    audit.validate(rows, self.ratings)

    def test_seal_replay_exact_public_zips_corruption_and_readonly_missing(self):
        before = {name: audit.digest(ROOT/name) for name in audit.read(audit.PRESERVED)}
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            with self.assertRaisesRegex(ValueError, 'Missing acceptance artifact'):
                audit.process(run, write=False)
            audit.process(run, write=True)
            initial = {str(p.relative_to(run)): audit.digest(p) for p in run.rglob('*') if p.is_file()}
            audit.process(run, write=False)
            self.assertEqual(initial, {str(p.relative_to(run)): audit.digest(p) for p in run.rglob('*') if p.is_file()})
            manifest = audit.read(run/'seal_manifest.json')
            for name, sha in manifest['files_sha256'].items():
                self.assertEqual(audit.digest(run/name), sha)
            for side in ['a','b']:
                name=f'input-review-{side}.zip'
                self.assertEqual((run/'public'/name).read_bytes(), (audit.MATERIALS/'handoff'/name).read_bytes())
                with zipfile.ZipFile(run/'public'/name) as z:
                    self.assertFalse(any('coordinator' in n or 'AGENTS' in n or 'ratings.json' == n for n in z.namelist()))
            (run/'public/input-review-a.zip').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'Frozen acceptance artifact differs'):
                audit.process(run, write=False)
        self.assertEqual(before, {name: audit.digest(ROOT/name) for name in before})

    def test_archive_reproducibility_and_path_traversal(self):
        self.assertEqual(audit.archive({'a':'A','b':'B'}), audit.archive({'b':'B','a':'A'}))
        with zipfile.ZipFile(io.BytesIO(audit.archive({'a':'A'}))) as z:
            self.assertEqual(z.read('a'), b'A')
        with self.assertRaisesRegex(ValueError, 'Unsafe archive'):
            audit.archive({'../outside': 'x'})


if __name__ == '__main__':
    unittest.main()
