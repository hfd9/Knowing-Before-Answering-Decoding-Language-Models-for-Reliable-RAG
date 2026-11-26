import copy
import json
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import answer_change_irs_independent_packet as p
import answer_change_irs_review_intake as m
import answer_change_irs_stage2_intake as s


class IntakeTests(unittest.TestCase):
    def fixture(self):
        plan, records = [], {}
        for group in ('same', 'different'):
            for state in ('missing', 'old', 'new'):
                case = f'{p.RULE}/{group}/{state}'
                task = {'id': case + '/direct', 'case': case, 'route': 'direct',
                        'messages': [{'role': 'user', 'content': '2024-01-01 E1 $100; 2025-01-01 E2 $200'}]}
                plan.append(task)
                records[task['id']] = {'status': 'complete', 'output': 'private output'}
        inputs, _, template = p.build(plan, records, 'archive', 'seal')
        review = copy.deepcopy(template)
        review.update(reviewer='synthetic', previous_exposure='synthetic fixture',
                      reviewed_without_model_outputs=True)
        for row in review['cases']:
            row.update(actual_date_provided='missing', possible_date_1='2024-01-01',
                possible_date_2='2025-01-01', branch_1_conclusion='Y', branch_1_support_quote=['E1 $100'],
                branch_2_conclusion='N', branch_2_support_quote=['E2 $200'],
                unique_conclusion_for_case='ambiguous', material_sufficiency='yes',
                author_metadata_dependency='yes', uncertainty_or_disagreement='none')
        return inputs, template, review

    def test_complete_input_only_review_can_be_validated(self):
        inputs, template, review = self.fixture()
        self.assertTrue(m.validate(review, inputs, template))

    def test_rejects_nonexistent_quote_and_missing_exposure(self):
        inputs, template, review = self.fixture()
        review['cases'][0]['branch_1_support_quote'] = ['invented quote']
        with self.assertRaisesRegex(ValueError, 'support quote'):
            m.validate(review, inputs, template)
        inputs, template, review = self.fixture()
        review['previous_exposure'] = ''
        with self.assertRaisesRegex(ValueError, 'exposure'):
            m.validate(review, inputs, template)

    def test_unknown_allowed_but_does_not_become_gold(self):
        inputs, template, review = self.fixture()
        review['reviewed_without_model_outputs'] = False
        review['cases'][0]['branch_1_conclusion'] = 'unknown'
        review['cases'][0]['branch_1_support_quote'] = []
        self.assertTrue(m.validate(review, inputs, template))

    def test_changed_input_packet_is_rejected_before_run_creation(self):
        inputs, template, review = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = root / 'public'
            public.mkdir()
            (public / 'input-packet.json').write_bytes(p.encode(inputs))
            (public / 'review-form.json').write_bytes(p.encode(template))
            submitted = root / 'review.json'
            submitted.write_bytes(p.encode(review))
            run = root / 'intake'
            with patch.object(m, 'PUBLIC', public), patch.object(m, 'RUN', run), \
                 patch.object(m, 'EXPECTED_PACKET', '0' * 64), \
                 patch.object(m, 'EXPECTED_TEMPLATE', p.sha((public / 'review-form.json').read_bytes())):
                with self.assertRaisesRegex(ValueError, 'public packet or template changed'):
                    m.seal(submitted)
                self.assertFalse(run.exists())

    def test_seal_then_connect_and_reject_tampering(self):
        inputs, template, review = self.fixture()
        plan, records = [], {}
        for group in ('same', 'different'):
            for state in ('missing', 'old', 'new'):
                case = f'{p.RULE}/{group}/{state}'
                task = {'id': case + '/direct', 'case': case, 'route': 'direct',
                        'messages': [{'role': 'user', 'content': '2024-01-01 E1 $100; 2025-01-01 E2 $200'}]}
                plan.append(task)
                records[task['id']] = {'id': task['id'], 'status': 'complete', 'output': 'private output'}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public, run = root / 'public', root / 'intake'
            public.mkdir()
            (public / 'input-packet.json').write_bytes(p.encode(inputs))
            (public / 'review-form.json').write_bytes(p.encode(template))
            submitted = root / 'submitted.json'
            submitted.write_bytes(p.encode(review))
            archive = root / 'source.zip'
            files = {}
            for i, task in enumerate(plan):
                files[f'{i:02d}.attempt.json'] = p.encode({'task': task})
                files[f'{i:02d}.record.json'] = p.encode(records[task['id']])
            seal_raw = p.encode({name: p.sha(raw) for name, raw in files.items()})
            with ZipFile(archive, 'w') as z:
                z.writestr('prepared/plan.json', p.encode(plan))
                z.writestr('run/seal.json', seal_raw)
                for name, raw in files.items():
                    z.writestr('run/' + name, raw)
            source_sha, seal_sha = p.sha(archive.read_bytes()), p.sha(seal_raw)
            expected_packet, mapping, expected_template = p.build(plan, records, source_sha, seal_sha)
            self.assertEqual(expected_packet, inputs)
            self.assertEqual(expected_template, template)
            coordination = root / 'mapping.json'
            coordination.write_bytes(p.encode(mapping))
            with patch.object(m, 'RUN', run), patch.object(m, 'PUBLIC', public), \
                 patch.object(m, 'COORDINATOR', coordination), patch.object(p, 'SOURCE', archive), \
                 patch.object(p, 'EXPECTED_ARCHIVE', source_sha), patch.object(p, 'EXPECTED_SEAL', seal_sha), \
                 patch.object(m, 'EXPECTED_PACKET', p.sha((public / 'input-packet.json').read_bytes())), \
                 patch.object(m, 'EXPECTED_TEMPLATE', p.sha((public / 'review-form.json').read_bytes())):
                with self.assertRaises(FileNotFoundError):
                    m.connect()
                m.seal(submitted)
                self.assertFalse(json.loads((run / 'seal.json').read_bytes())['independence_certified'])
                self.assertFalse((run / 'stage2.json').exists())
                m.connect()
                stage2 = json.loads((run / 'stage2.json').read_bytes())
                self.assertEqual(len(stage2['cases']), 6)
                self.assertEqual(len(stage2['review_form']), 6)
                self.assertEqual({r['model_output'] for r in stage2['cases']}, {'private output'})
                s.prepare()
                review2 = json.loads((run / 'stage2-review-template.json').read_bytes())
                review2.update(reviewer='synthetic', reviewed_at='2026-11-26T12:00:00+08:00',
                               exposure_and_role='fixture; prior exposure unknown')
                for row in review2['cases']:
                    for field in s.FIELDS:
                        row[field] = 'unknown'
                    row['supporting_output_quotes'] = []
                    row['uncertainty_or_notes'] = 'synthetic unknown'
                review2['cases'][0]['claims_actual_date'] = 'yes'
                review2['cases'][0]['supporting_output_quotes'] = ['private output']
                review2_path = root / 'stage2-submitted.json'
                review2_path.write_bytes(p.encode(review2))
                s.seal(review2_path)
                s.verify()
                with self.assertRaisesRegex(ValueError, 'exists'):
                    s.seal(review2_path)
                original_stage2 = (run / 'stage2.json').read_bytes()
                changed = json.loads(original_stage2)
                changed['cases'][0]['model_output'] = 'tampered output'
                (run / 'stage2.json').write_bytes(p.encode(changed))
                with self.assertRaisesRegex(ValueError, 'output mismatch'):
                    s.verify()
                (run / 'stage2.json').write_bytes(original_stage2)
                (run / 'stage2-review' / 'review.json').write_text('{}')
                with self.assertRaisesRegex(ValueError, 'review seal mismatch'):
                    s.verify()
                with self.assertRaisesRegex(ValueError, 'intake exists'):
                    m.seal(submitted)
                (run / 'review.json').write_text('{}')
                with self.assertRaisesRegex(ValueError, 'seal mismatch'):
                    m.connect()
                with self.assertRaisesRegex(ValueError, 'first-stage seal mismatch'):
                    s.verify()

    def test_stage2_rejects_missing_evidence_invalid_time_and_ids(self):
        stage = {'cases': [{'review_id': 'R1', 'model_output': 'Given 2024, yes.'}],
                 'review_form': [{'review_id': 'R1', **{k: None for k in s.FIELDS},
                                  'supporting_output_quotes': None, 'uncertainty_or_notes': None}]}
        review = s.make_template(stage)
        review.update(reviewer='synthetic', reviewed_at='2026-11-26T12:00:00+08:00',
                      exposure_and_role='synthetic')
        row = review['cases'][0]
        row.update({k: 'unknown' for k in s.FIELDS})
        row.update(supporting_output_quotes=[], uncertainty_or_notes='unknown')
        self.assertTrue(s.validate(review, stage))
        row['claims_actual_date'] = 'yes'
        with self.assertRaisesRegex(ValueError, 'needs output quote'):
            s.validate(review, stage)
        row['supporting_output_quotes'] = ['invented']
        with self.assertRaisesRegex(ValueError, 'quote not in output'):
            s.validate(review, stage)
        row['supporting_output_quotes'] = ['Given 2024']
        review['reviewed_at'] = '2026-11-26T12:00:00'
        with self.assertRaisesRegex(ValueError, 'requires timezone'):
            s.validate(review, stage)
        review['reviewed_at'] = '2026-11-26T12:00:00+08:00'
        row['review_id'] = 'R2'
        with self.assertRaisesRegex(ValueError, 'IDs differ'):
            s.validate(review, stage)


if __name__ == '__main__':
    unittest.main()
