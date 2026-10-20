"""Review intake must reject contaminated batches and keep the complete denominator."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import semantic_transfer_review_intake as intake


def packet():
    return dict(items=[dict(item_id='R001', question='What is the supported relation?',
        documents=['An explicit target relation is supplied here.'] * 5)])


def review(name='reviewer_a', mode='answer'):
    return dict(reviewer=name, history_exposed=False,
        exposure_description='Test fixture only; received the isolated synthetic packet, not real independent evidence.',
        packet_sha256='test_sha', ratings=[dict(item_id='R001', semantic_mode=mode, confidence='high',
            required_facts=['The target relation'], support_chain=['Explicit relation'],
            missing_facts=['Necessary relation'], conflicting_claims=['Target relation holds', 'It does not hold'],
            resolution_basis='No source priority supplied.', rationale='A synthetic workflow check.',
            citations=[dict(doc_slot=1, quote='explicit target relation')])])


class ReviewIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import semantic_transfer_materials_v3
        cls._folder = tempfile.TemporaryDirectory()
        cls.materials = Path(cls._folder.name) / 'materials'
        cls.materials.mkdir()
        semantic_transfer_materials_v3.load_core().prepare(cls.materials, write=True)

    @classmethod
    def tearDownClass(cls):
        cls._folder.cleanup()

    def test_history_exposure_and_unreviewed_template_are_rejected(self):
        for value in [None, True, 'false']:
            r = review()
            r['history_exposed'] = value
            with self.assertRaisesRegex(ValueError, 'History-exposed'):
                intake.validate_review(r, packet(), 'test_sha')
        r = review()
        r['ratings'][0]['status'] = 'unreviewed'
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            intake.validate_review(r, packet(), 'test_sha')

    def test_wrong_batch_missing_duplicate_and_false_quote_are_rejected(self):
        mutations = [lambda r: r.update(packet_sha256='other'), lambda r: r.update(ratings=[]),
            lambda r: r['ratings'].append(copy.deepcopy(r['ratings'][0])),
            lambda r: r['ratings'][0]['citations'][0].update(quote='invented quote'),
            lambda r: r['ratings'][0]['citations'][0].update(doc_slot=True),
            lambda r: r['ratings'][0]['citations'][0].update(end=1)]
        for mutate in mutations:
            r = review()
            mutate(r)
            with self.assertRaises(ValueError):
                intake.validate_review(r, packet(), 'test_sha')

    def test_supported_relations_require_explicit_reasoning_and_quotes(self):
        for mode, field, value in [('answer', 'support_chain', []), ('refuse', 'missing_facts', []),
                ('conflict', 'conflicting_claims', ['one claim']), ('unknown', 'rationale', '')]:
            r = review(mode=mode)
            r['ratings'][0][field] = value
            with self.assertRaises(ValueError):
                intake.validate_review(r, packet(), 'test_sha')
        verified = intake.validate_review(review(), packet(), 'test_sha')['R001']['citations'][0]
        self.assertEqual(packet()['items'][0]['documents'][0][verified['start']:verified['end']], verified['quote'])

    def test_agreement_keeps240_denominator_and_never_approves_labels(self):
        design = intake.read(intake.DESIGN)
        row = dict(id='stv01_A_S', original_id='train_1102', partition='semantic_train', expression='A', condition='S')
        reviews = {side: dict(metadata=review(name), ratings=intake.validate_review(review(name), packet(), 'test_sha'))
            for side, name in [('a', 'one'), ('b', 'two')]}
        report, candidates = intake.summarize([row], [], {row['id']: dict(a='R001', b='R001')}, reviews, design)
        self.assertEqual(report['agreement_coverage'], 1 / 240)
        self.assertEqual(report['partitions']['semantic_train']['agreement_coverage'], 1 / 96)
        self.assertIsNone(candidates[0]['semantic_label'])
        self.assertEqual(candidates[0]['consensus_candidate'], 'answer')
        self.assertFalse(report['approved_for_training'])
        self.assertFalse(report['gpu_launch_ready'])
        reviews['b']['ratings']['R001']['semantic_mode'] = 'refuse'
        report, candidates = intake.summarize([row], [], {row['id']: dict(a='R001', b='R001')}, reviews, design)
        self.assertEqual(report['disagreements'], ['stv01_A_S'])
        self.assertIsNone(candidates[0]['consensus_candidate'])
        reviews['b']['metadata']['reviewer'] = ' ONE '
        with self.assertRaisesRegex(ValueError, 'distinct'):
            intake.summarize([row], [], {row['id']: dict(a='R001', b='R001')}, reviews, design)

    def test_actual_materials_pending_intake_is_readonly_and_tamper_fails(self):
        materials = self.materials
        before = {p: intake.digest(p) for p in materials.rglob('*') if p.is_file()}
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'out'
            result = intake.process(materials, output)
            self.assertEqual((result['constructed_cells'], result['unavailable_cells']), (176, 64))
            self.assertEqual(result['validated_review_files'], 0)
            self.assertEqual(result['approved_semantic_labels'], 0)
            frozen = {p: intake.digest(p) for p in output.iterdir()}
            self.assertEqual(intake.process(materials, output, write=False), result)
            self.assertEqual(frozen, {p: intake.digest(p) for p in frozen})
            p = output / 'consensus_candidates.json'
            p.write_text('[]\n')
            with self.assertRaisesRegex(ValueError, 'Existing intake differs'):
                intake.process(materials, output, write=False)
            with self.assertRaisesRegex(ValueError, 'both reviews'):
                intake.process(materials, output, review_a=Path('absent'))
        self.assertEqual(before, {p: intake.digest(p) for p in before})

    def test_packet_mapping_and_planned_denominator_tampering_are_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder) / 'copy'
            for rel in ['protocol.json', 'materials/inputs.json', 'materials/unavailable_cells.json',
                    'coordinator/review_mapping.json', 'review_a/packet.json', 'review_b/packet.json']:
                path = base / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.materials / rel, path)
            p = base / 'materials/unavailable_cells.json'
            original = p.read_text()
            p.write_text('[]\n')
            with self.assertRaisesRegex(ValueError, 'Planned240'):
                intake.load_materials(base)
            p.write_text(original)
            p = base / 'coordinator/review_mapping.json'
            value = intake.read(p)
            keys = list(value)
            value[keys[0]], value[keys[1]] = value[keys[1]], value[keys[0]]
            p.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'Mapped packet content'):
                intake.load_materials(base)


if __name__ == '__main__':
    unittest.main()
