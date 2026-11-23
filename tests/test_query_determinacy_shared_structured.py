"""Exercise the two observed failures, candidate binding and the numeric control."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_shared_structured as structured
import query_determinacy_shared_live as old

PUBLIC = json.loads(old.PILOT_PUBLIC.read_bytes())
PRIOR = ROOT / 'docs/review/2026-11-23-shared-lines-results-v1/results.json'


class StructuredTests(unittest.TestCase):
    def test_exact_observed_fences_are_accepted_and_pinned_parser_still_rejects(self):
        extracts = [r for r in json.loads(PRIOR.read_bytes())['slots'] if r['kind'] == 'extract']
        for row, case in zip(extracts, PUBLIC['cases']):
            domain = case['domain']
            fixed = structured.extract_candidates(row['output'], domain)
            self.assertEqual(fixed['encoding'], 'single_json_fence')
            self.assertEqual(old.extract.parse(row['output'], domain)['status'], 'invalid')
            spans, sources = structured.materials(case)
            for span in spans.values():
                raw = case['background'].encode()
                self.assertEqual(raw[span['start_byte']:span['end_byte']].decode(), span['text'])
            self.assertEqual(structured.bind(fixed['values'], sources), ('S1', 'S2'))

    def test_does_not_repair_bad_values_or_wrappers(self):
        fence = '```json\n["34","58"]\n```'
        for text in ('text '+fence, fence+'\n'+fence, fence+'\nextra',
                     fence.replace('58','34'), fence.replace('34','-34')):
            self.assertEqual(structured.extract_candidates(text, 'integer')['status'], 'invalid')
        _, sources = structured.materials(PUBLIC['cases'][0])
        self.assertIsNone(structured.bind(['34','45'], sources))
        self.assertEqual(structured.bind(['58','34'], sources), ('S2','S1'))

    def test_candidate_slot_contract_cannot_emit_threshold_or_ordinal(self):
        spans, sources = structured.materials(PUBLIC['cases'][0])
        variants = structured.responses(('S1','S2'), tuple(spans))
        self.assertIn('S1=N|-\nS2=Y|S2', variants)
        self.assertIn('S1=Y|S1\nS2=Y|S2', variants)
        self.assertIn('S1=N|S2\nS2=Y|S1', variants)
        self.assertIn('S1=X|-\nS2=Y|S2', variants)
        self.assertNotIn('45=N|-\n2=Y|S2', variants)
        self.assertNotIn('S1=Y|S9\nS2=Y|S2', variants)
        # Scoreable syntax preserves the same wrong decision and missing evidence.
        worlds = structured.ensure_worlds(variants['S1=N|-\nS2=Y|S2'], sources)
        self.assertEqual([w['value'] for w in worlds], ['34','58'])
        self.assertEqual(worlds[0]['evidence_ids'], [])
        self.assertEqual(structured.final(worlds), 'U')
        unknown = structured.ensure_worlds(variants['S1=X|-\nS2=Y|S2'], sources)
        self.assertIsNone(structured.final(unknown))

    def test_numeric_control_uses_bound_values_and_strict_relations(self):
        _, sources = structured.materials(PUBLIC['cases'][0])
        for question, expected in zip(PUBLIC['cases'][0]['questions'], ('U','N','Y')):
            result = structured.numeric_comparison(question['text'], ('S1','S2'), sources)
            self.assertEqual(structured.final(structured.ensure_worlds(result, sources)), expected)
        self.assertIsNone(structured.numeric_comparison('该次校准读数是否超过30厘米？', ('S1','S2'), sources))
        self.assertIsNone(structured.numeric_comparison('该次校准读数是否超过30单位？', None, sources))
        equality = structured.numeric_comparison('该次校准读数是否超过58单位？', ('S1','S2'), sources)
        self.assertEqual(structured.final(structured.ensure_worlds(equality, sources)), 'N')


if __name__ == '__main__':
    unittest.main()
