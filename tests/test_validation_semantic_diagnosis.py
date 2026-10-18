"""Verify export isolation, denominators and preservation of sealed artifacts."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import validation_semantic_diagnosis as diagnosis


class DiagnosisTests(unittest.TestCase):
    def test_unknown_separate_invalid_stays_in_denominator(self):
        rows = []
        for mode, prediction, confidence in [('answer', 'answer', 'high'),
                                              ('refuse', 'unknown', 'high'),
                                              ('conflict', 'conflict', 'moderate'),
                                              ('unknown', 'answer', 'ambiguous')]:
            rows.append(dict(input_semantic_mode=mode, input_confidence=confidence,
                             **dict.fromkeys(diagnosis.METHODS, prediction)))
        table = diagnosis.agreement_table(rows)
        for method in diagnosis.METHODS:
            self.assertEqual(table['all_known'][method]['denominator'], 3)
            self.assertEqual(table['all_known'][method]['agreement'], 2)
            self.assertEqual(table['all_known'][method]['per_class']['refuse'],
                             dict(agreement=0, denominator=1))
            self.assertEqual(table['high_confidence_only'][method]['denominator'], 2)
            self.assertEqual(table['high_confidence_only'][method]['agreement'], 1)
        self.assertEqual(table['input_unknown_count'], 1)

    def test_reviewer_packet_hides_labels_and_preserves_full_documents(self):
        packet = dict(records=[], documents={})
        ratings = {}
        for i in range(30):
            key = f'P{i+1:03d}'
            packet['records'].append(dict(review_id=key, group_id='G_SECRET',
                                          question=f'Question {i}', doc_refs=[f'D{i}'] * 5,
                                          published_mode='RELEASE_SECRET'))
            packet['documents'][f'D{i}'] = f'complete original text {i}'
            ratings[key] = dict(semantic_mode='unknown' if i < 3 else 'answer',
                                confidence='moderate' if 3 <= i < 7 else 'high',
                                reason='ASSISTANT_SECRET')
        public, mapping, priority = diagnosis.review_packet(packet, ratings)
        self.assertEqual(len(public), 30)
        self.assertEqual(len(priority), 7)
        self.assertEqual(set(mapping.values()), set(ratings))
        self.assertEqual(diagnosis.review_packet(packet, ratings), (public, mapping, priority))
        text = json.dumps(public)
        for secret in ['RELEASE_SECRET', 'ASSISTANT_SECRET', 'G_SECRET', 'semantic_mode']:
            self.assertNotIn(secret, text)
        for row in public:
            old = next(r for r in packet['records'] if r['review_id'] == mapping[row['review_id']])
            self.assertEqual(row['question'], old['question'])
            self.assertEqual(row['documents'], [packet['documents'][ref] for ref in old['doc_refs']])

    def test_changed_sources_and_duplicate_ids_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = base / 'source.json'
            path.write_text('{"sealed":true}')
            hashes = {'source.json': diagnosis.digest(path)}
            diagnosis.verify_hashes(base, hashes)
            path.write_text('{"sealed":false}')
            with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
                diagnosis.verify_hashes(base, hashes)
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                diagnosis.indexed([dict(id='a'), dict(id='a')], 'id')

    def test_publish_is_complete_idempotent_and_refuses_changed_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'new-report'
            files = {'report.md': 'test report\n', 'reviewer/ratings.blank.csv': 'review_id,semantic_mode\nR001,\n'}
            self.assertEqual(diagnosis.publish(target, files), 'new_outputs_written')
            saved = {p.relative_to(target): (p.read_bytes(), p.stat().st_mtime_ns)
                     for p in target.rglob('*') if p.is_file()}
            self.assertEqual(diagnosis.publish(target, files), 'existing_outputs_verified')
            self.assertEqual(saved, {p.relative_to(target): (p.read_bytes(), p.stat().st_mtime_ns)
                                     for p in target.rglob('*') if p.is_file()})
            path = target / 'reviewer/ratings.blank.csv'
            path.write_text('review_id,semantic_mode\nR001,answer\n')
            with self.assertRaisesRegex(ValueError, 'Existing artifact differs'):
                diagnosis.publish(target, files)
            self.assertIn('answer', path.read_text())
            self.assertEqual((target / 'report.md').read_text(), files['report.md'])

    def test_html_source_text_is_escaped(self):
        text = diagnosis.details('<script>header</script>', '</pre><script>payload()</script>')
        self.assertNotIn('<script>', text)
        self.assertIn('&lt;script&gt;', text)


if __name__ == '__main__':
    unittest.main()
