import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import query_determinacy_extract_v2 as parser
import query_determinacy_world_extract_parser as old


class ExtractV2Tests(unittest.TestCase):
    def test_previous_integer_array_failures_have_new_parser_only(self):
        for output, expected in [('[13,21]', ['13', '21']), ('[50,62]', ['50', '62'])]:
            with self.subTest(output=output):
                self.assertEqual(old.parse(output), ('invalid', None))
                self.assertEqual(parser.parse(output, 'integer'),
                                 {'status': 'parsed', 'values': expected, 'types': ['json_integer'] * 2})

    def test_integer_literals_strings_and_mixed_types(self):
        self.assertEqual(parser.parse('[0,"999999999"]', 'integer')['values'], ['0', '999999999'])
        self.assertEqual(parser.parse('["13",21]', 'integer')['types'], ['string', 'json_integer'])

    def test_integer_rejects_ambiguous_or_noncanonical_values(self):
        for output in ('["001","2"]', '[01,2]', '[-0,1]', '[-1,2]', '[1.0,2]',
                       '[1e0,2]', '[true,2]', '[NaN,2]', '[1000000000,2]',
                       '[" 1","2"]', '[1,"1"]', '["",2]', '[]', '[1,2,3]',
                       '{"a":1}', '```json\n[1,2]\n```'):
            with self.subTest(output=output):
                self.assertEqual(parser.parse(output, 'integer')['status'], 'invalid')

    def test_identifier_preserves_case_and_leading_zeros(self):
        out = parser.parse('["001","A-2"]', 'identifier')
        self.assertEqual(out['values'], ['001', 'A-2'])
        self.assertEqual(parser.parse('["a1","A1"]', 'identifier')['values'], ['a1', 'A1'])
        for output in ('[1,"A2"]', '["a b","x"]', '["x","x"]', '["é","x"]', '["x","a/b"]'):
            with self.subTest(output=output):
                self.assertEqual(parser.parse(output, 'identifier')['status'], 'invalid')

    def test_strict_json_and_output_limit(self):
        for output in ('[1,2] trailing', '[1,2,]', 'null', '[1,Infinity]', ' ' * 4097):
            with self.subTest(output=output):
                self.assertEqual(parser.parse(output, 'integer')['status'], 'invalid')
        self.assertEqual(parser.parse('["x","' + 'y' * 65 + '"]', 'identifier')['status'], 'invalid')

    def test_technical_failure_and_domain_checks(self):
        self.assertEqual(parser.parse('[1,2]', 'integer', technical_complete=False)['status'], 'technical_failure')
        with self.assertRaises(ValueError):
            parser.parse('[1,2]', 'other')
        with self.assertRaises(TypeError):
            parser.parse(None, 'integer')

    def test_against_original_all_24_extracts_without_changing_old_score(self):
        root = Path(__file__).resolve().parents[1]
        p = root / 'docs/review/2026-11-18-query-determinacy-paraphrase-results-v1/extraction.json'
        rows = json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(len(rows), 24)
        statuses = []
        for row in rows:
            domain = 'integer' if row['case'].startswith('H') else 'identifier'
            result = parser.parse(row['output'], domain)
            statuses.append(result['status'])
            self.assertEqual(result['values'], row['reference'])
            self.assertEqual(old.score(row['output'], row['reference']), row['score'])
        self.assertEqual(statuses.count('parsed'), 24)


if __name__ == '__main__':
    unittest.main()
