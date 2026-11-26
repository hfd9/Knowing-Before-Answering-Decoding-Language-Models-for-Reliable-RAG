import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('protocol_check', ROOT / 'scripts/answer_change_development_protocol_check.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ProtocolConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((m.PACK / 'protocol.json').read_text())
        self.prose = (m.PACK / 'protocol.md').read_text()

    def test_counts_and_prose_agree(self):
        self.assertEqual(m.check(self.data, self.prose),
                         {'first_turn': 24, 'missing': 8, 'max_followup': 16, 'collection_release': False})

    def test_modified_prompt_or_followup_limit_fails(self):
        with self.assertRaises(ValueError):
            m.check(self.data | {'direct': self.data['direct'] + ' changed'}, self.prose)
        with self.assertRaises(ValueError):
            m.check(self.data | {'max_followup_calls': 12}, self.prose)

    def test_release_cannot_be_silently_enabled(self):
        with self.assertRaises(ValueError):
            m.check(self.data | {'new_rule_collection_release': True}, self.prose)


if __name__ == '__main__':
    unittest.main()
