import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import explanation_scope_ledger_simulator as ledger


class LedgerSimulatorChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan, cls.digest = ledger.load_plan()

    def setUp(self):
        self.state = {'synthetic': True, 'plan_sha256': self.digest, 'attempts': [], 'records': [],
                      'smoke': None, 'failure': None}

    def append_record(self, eos=True, nonempty=True):
        i = len(self.state['records'])
        marker = {'index': i, 'id': self.plan['ordered_ids'][i], 'plan_sha256': self.digest}
        self.state['attempts'].append(marker)
        self.state['records'].append(dict(marker, prompt_sha256='a' * 64, output_sha256='b' * 64,
                                          output_tokens=10 if eos else 128, ended_with_eos=eos,
                                          hit_output_limit=not eos, nonempty_output=nonempty))

    def result(self):
        return ledger.evaluate(self.state, self.plan, self.digest)

    def smoke(self, passed):
        self.state['smoke'] = {'plan_sha256': self.digest, 'records_sha256': ledger.smoke_digest(self.state['records']),
                               'passed': passed}

    def test_empty_is_only_synthetic_not_authorization(self):
        result = self.result()
        self.assertEqual(result['state'], 'synthetic_clean_prefix')
        self.assertFalse(result['collection_permitted'])
        self.assertFalse(result['gpu_launch_ready'])

    def test_uncommitted_attempt_blocks_retry(self):
        self.state['attempts'].append({'index': 0, 'id': self.plan['ordered_ids'][0], 'plan_sha256': self.digest})
        self.assertEqual(self.result()['state'], 'blocked_uncommitted_attempt')

    def test_unverified_smoke_blocks_item_five(self):
        for _ in range(4):
            self.append_record()
        self.assertEqual(self.result()['state'], 'blocked_missing_smoke_receipt')
        self.smoke(True)
        self.assertEqual(self.result()['state'], 'synthetic_clean_prefix')

    def test_failed_smoke_cannot_be_declared_passed(self):
        for i in range(4):
            self.append_record(eos=i != 2)
        self.smoke(False)
        self.assertEqual(self.result()['state'], 'blocked_failed_smoke')
        self.smoke(True)
        with self.assertRaises(ValueError):
            self.result()

    def test_tampered_record_invalidates_smoke_receipt(self):
        for _ in range(4):
            self.append_record()
        self.smoke(True)
        self.state['records'][0]['output_sha256'] = 'c' * 64
        with self.assertRaises(ValueError):
            self.result()

    def test_recorded_failure_blocks_even_clean_prefix(self):
        self.append_record()
        self.state['failure'] = {'reason': 'synthetic interrupted write'}
        self.assertEqual(self.result()['state'], 'blocked_recorded_failure')

    def test_nonprefix_and_orphan_markers_rejected(self):
        self.append_record()
        self.state['records'][0]['id'] = self.plan['ordered_ids'][2]
        with self.assertRaises(ValueError):
            self.result()
        self.state['records'][0]['id'] = self.plan['ordered_ids'][0]
        self.state['attempts'].extend([{'index': i, 'id': self.plan['ordered_ids'][i], 'plan_sha256': self.digest}
                                       for i in (1, 2)])
        with self.assertRaises(ValueError):
            self.result()

    def test_full_declared_completion_remains_synthetic(self):
        for _ in range(4):
            self.append_record()
        self.smoke(True)
        for _ in range(44):
            self.append_record()
        result = self.result()
        self.assertEqual(result['state'], 'synthetic_complete')
        self.assertFalse(result['collection_permitted'])

    def test_non_synthetic_and_wrong_hash_are_rejected(self):
        self.state['synthetic'] = False
        with self.assertRaises(ValueError):
            self.result()
        self.state['synthetic'] = True
        self.state['plan_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.result()

    def test_inconsistent_stop_flags_are_rejected(self):
        self.append_record()
        self.state['records'][0]['ended_with_eos'] = False
        with self.assertRaises(ValueError):
            self.result()

    def test_modified_order_is_not_accepted_as_new_plan(self):
        data = json.loads(ledger.PLAN_PATH.read_text())
        data['ordered_ids'][4], data['ordered_ids'][5] = data['ordered_ids'][5], data['ordered_ids'][4]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'plan.json'
            path.write_text(json.dumps(data))
            with patch.object(ledger, 'PLAN_PATH', path):
                with self.assertRaises(ValueError):
                    ledger.load_plan()


if __name__ == '__main__':
    unittest.main()
