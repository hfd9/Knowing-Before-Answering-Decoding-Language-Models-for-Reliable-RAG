import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('irs_packet', ROOT / 'scripts/answer_change_irs_independent_packet.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class PacketTests(unittest.TestCase):
    def fixture(self):
        plan, records = [], {}
        for group in ('same', 'different'):
            for state in ('missing', 'old', 'new'):
                case = f'{m.RULE}/{group}/{state}'
                task = {'id': case + '/direct', 'case': case, 'route': 'direct',
                        'messages': [{'role': 'user', 'content': f'input {group} {state}'}]}
                plan.append(task)
                records[task['id']] = {'status': 'complete', 'output': 'private model answer'}
        return plan, records

    def test_public_packet_has_only_original_inputs_and_blank_form(self):
        plan, records = self.fixture()
        packet, mapping, form = m.build(plan, records, 'archive', 'seal')
        self.assertEqual(len(packet['cases']), 6)
        self.assertEqual({str(x['messages']) for x in packet['cases']}, {str(x['messages']) for x in plan})
        self.assertNotIn('private model answer', str(packet) + str(form))
        self.assertNotIn(m.RULE, str(packet) + str(form))
        self.assertEqual(mapping['status'], 'prepared_not_reviewed')
        self.assertTrue(all(all(v is None for k, v in row.items() if k != 'review_id') for row in form['cases']))

    def test_missing_duplicate_or_incomplete_source_fails(self):
        plan, records = self.fixture()
        with self.assertRaisesRegex(ValueError, 'unexpected selection'):
            m.build(plan[:-1], records, 'archive', 'seal')
        bad = copy.deepcopy(records)
        bad[plan[0]['id']]['status'] = 'truncated'
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            m.build(plan, bad, 'archive', 'seal')


if __name__ == '__main__':
    unittest.main()
