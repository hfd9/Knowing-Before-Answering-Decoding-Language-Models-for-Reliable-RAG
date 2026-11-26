import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mapping', ROOT / 'scripts/answer_change_frozen_mapping_audit.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MappingTests(unittest.TestCase):
    def test_pipeline_error_is_not_a_refusal(self):
        obj = {'error': 'bad evidence', 'outcome': None, 'tag': None, 'extra': ['kept']}
        mapped = m.map_candidate('test', obj)
        self.assertEqual(mapped['view']['availability'], 'pipeline_error')
        self.assertIsNone(mapped['view']['structured_action'])
        self.assertEqual(mapped['original_candidate'], obj)

    def test_structured_ask_is_preserved_not_fabricated_as_text(self):
        obj = {'error': None, 'tag': 'ASK_DATE', 'outcome': {'tag': 'ASK_DATE',
               'branches': [['2024-01-01', True, ['E1']]], 'ask_event': 'gift'}, 'extra': 3}
        mapped = m.map_candidate('test', obj)
        self.assertEqual(mapped['view']['structured_action'], 'ASK_DATE')
        self.assertNotIn('text', mapped['view'])
        self.assertEqual(mapped['original_candidate'], obj)

    def test_invalid_records_not_silently_repaired(self):
        for obj in ({'error': 'bad', 'outcome': {'tag': 'ANSWER_Y'}, 'tag': 'ANSWER_Y'},
                    {'error': None, 'outcome': None, 'tag': None},
                    {'error': None, 'outcome': {'tag': 'ASK_DATE', 'branches': [], 'ask_event': 'x'},
                     'tag': 'ANSWER_Y'}):
            with self.assertRaises(ValueError):
                m.map_candidate('test', obj)

    def test_text_and_unexpected_status_are_preserved_or_rejected(self):
        task = {'id': 'x/direct', 'case': 'x', 'route': 'direct'}
        record = {'id': 'x/direct', 'status': 'truncated', 'output': 'partial', 'extra': [1]}
        mapped = m.map_text(task, record)
        self.assertEqual(mapped['original_record'], record)
        self.assertEqual(mapped['view']['generation_status'], 'truncated')
        with self.assertRaises(ValueError):
            m.map_text(task, record | {'status': 'not-a-status'})


if __name__ == '__main__':
    unittest.main()
