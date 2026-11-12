import csv
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_results_audit as audit


@unittest.skipUnless((audit.MATERIAL / 'key.csv').is_file() and all((ROOT / 'runs' / name / 'manifest.json').is_file() for name, _, _ in audit.RUNS),
                     'user materials and local run artifacts are unavailable')
class ResultAuditTests(unittest.TestCase):
    def test_all_rows_and_technical_denominators_are_preserved(self):
        result = audit.analyze()
        self.assertEqual((result['total'], result['technical_complete'], result['technical_failures']), (144, 138, 6))
        self.assertEqual(sum(result['counts']['determinate']['assertion'].values()), 24)
        self.assertEqual(sum(result['counts']['single']['single_a'].values()), 36)

    def test_cannot_relabel_truncation_as_complete(self):
        with audit.JUDGMENTS.open(encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            fields, rows = reader.fieldnames, list(reader)
        row = next(r for r in rows if r['assertion'] == 'T')
        row['assertion'] = 'N'
        with tempfile.TemporaryDirectory() as tmp:
            altered = Path(tmp) / 'judgments.csv'
            with altered.open('w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            with patch.object(audit, 'JUDGMENTS', altered):
                with self.assertRaisesRegex(ValueError, 'technical state mismatch'):
                    audit.analyze()


if __name__ == '__main__':
    unittest.main()
