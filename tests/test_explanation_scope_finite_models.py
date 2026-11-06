from pathlib import Path
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/review/2026-11-06-explanation-scope-cpu-preflight-v1/finite-model-audit.json'


class FiniteModelChecks(unittest.TestCase):
    def test_fresh_audit_matches_saved_report(self):
        output = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/audit_explanation_scope_models.py')],
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(output.stdout), json.loads(REPORT.read_text()))

    def test_first_scenario_expected_counts_and_target_values(self):
        report = json.loads(REPORT.read_text())
        by_id = {r['id']: r for r in report['items']}
        plan = json.loads((ROOT / 'docs/review/2026-11-06-explanation-scope-materials-v2/design-lock.json').read_text())
        s = plan['scenes'][0]
        domain = {s['a'], s['b'], s['c'], s['alternative_target_values'][0]}
        self.assertEqual(len(domain), 4)
        self.assertEqual(by_id['exs01_S']['finite_all_records_trusted_world_count'], 4)
        self.assertEqual(by_id['exs01_S']['finite_all_records_trusted_target_values'], [s['a']])
        self.assertEqual(set(by_id['exs01_I0']['finite_all_records_trusted_target_values']), domain)
        for condition in ('IU', 'CT'):
            item = by_id[f'exs01_{condition}']
            self.assertEqual(item['finite_all_records_trusted_world_count'], 0)
            self.assertEqual([r['world_count'] for r in item['minimal_one_record_repair_cases']], [16, 16])
        self.assertEqual({tuple(r['target_values']) for r in by_id['exs01_IU']['minimal_one_record_repair_cases']},
                         {tuple(sorted(domain))})
        self.assertEqual({r['target_values'][0] for r in by_id['exs01_CT']['minimal_one_record_repair_cases']},
                         {s['a'], s['b']})


if __name__ == '__main__':
    unittest.main()
