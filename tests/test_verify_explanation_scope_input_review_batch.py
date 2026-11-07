import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import verify_explanation_scope_input_review_batch as verifier


class ReviewBatchVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        items = []
        for i in range(1, 49):
            entity = f'Unit XU-{i}'
            quote = f'A record assigns {entity} the alpha code VX-{i}.'
            items.append({'item_id': f'P{i:03d}', 'question': f'What is the alpha code for {entity}?',
                          'documents': [quote, 'Rule.', 'Other.', 'Other.', 'Other.']})
        self.packet = {'items': items}
        self.packet_path = self.root / 'packet.json'
        self.packet_path.write_text(json.dumps(self.packet))
        self.response = {
            'reviewer_id': 'SCOPECLI20261107R01', 'batch': 'P001-P002',
            'input_packet_sha256': hashlib.sha256(self.packet_path.read_bytes()).hexdigest(),
            'exposure_statement': 'No prior case materials reported.',
            'reading_statement': 'Two items and ten documents reported read.',
            'limitations': 'No independent approval claimed.', 'items': []}
        for i, source in enumerate(items[:2], 1):
            quote = source['documents'][0]
            self.response['items'].append({
                'item_id': source['item_id'], 'target_entity': f'Unit XU-{i}',
                'target_field': 'alpha code', 'target_record_state': 'target_record_supported',
                'target_records': [{'document_index': 1, 'quote': quote, 'value': f'VX-{i}'}],
                'conflicts': [], 'target_support_interpretation': 'One record supports the value.',
                'missing_or_uncertain': 'World truth not established.', 'reasoning': 'The record is explicit.',
                'evidence_citations': [{'document_index': 1, 'quote': quote}]})
        self.events = [{'type': 'item.completed', 'item': {'type': 'command_execution',
                        'aggregated_output': '\n'.join(json.dumps(x) for x in items[:2])}}]
        self.response_path = self.root / 'response.json'
        self.events_path = self.root / 'events.jsonl'

    def run_verifier(self, response=None, events=None):
        self.response_path.write_text(json.dumps(self.response if response is None else response))
        self.events_path.write_text(''.join(json.dumps(x) + '\n' for x in (self.events if events is None else events)))
        return verifier.verify(self.packet_path, self.response_path, self.events_path, 1, 2)

    def test_valid_packet_and_evidence_preserve_limits(self):
        result = self.run_verifier()
        self.assertEqual((result['reviewed_items'], result['visible_complete_items']), (2, 2))
        self.assertFalse(result['semantic_correctness_verified'])
        self.assertFalse(result['independent_formal_approval'])

    def test_bad_quote_and_wrong_document_are_rejected(self):
        for change in ('quote', 'document_index'):
            with self.subTest(change=change):
                response = copy.deepcopy(self.response)
                response['items'][0]['evidence_citations'][0][change] = ('not present' if change == 'quote' else 2)
                with self.assertRaisesRegex(ValueError, 'quote not present'):
                    self.run_verifier(response=response)

    def test_missing_visible_item_is_rejected(self):
        events = copy.deepcopy(self.events)
        events[0]['item']['aggregated_output'] = json.dumps(self.packet['items'][0])
        with self.assertRaisesRegex(ValueError, 'presentation not observed'):
            self.run_verifier(events=events)

    def test_duplicate_and_packet_hash_change_are_rejected(self):
        response = copy.deepcopy(self.response)
        response['items'][1]['item_id'] = response['items'][0]['item_id']
        with self.assertRaisesRegex(ValueError, 'missing or duplicated'):
            self.run_verifier(response=response)
        response = copy.deepcopy(self.response)
        response['input_packet_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'fingerprint differs'):
            self.run_verifier(response=response)


if __name__ == '__main__':
    unittest.main()
