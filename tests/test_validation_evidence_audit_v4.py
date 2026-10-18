"""Budget repair retains completion requirements and the frozen smoke gate."""

import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import validation_evidence_audit_v4 as v4
from test_validation_evidence_audit_v3 import CharacterTokenizer,decision_tokens


class V4Tests(unittest.TestCase):
    def setUp(self):
        self.config=v4.e.read_json(v4.CONFIG)
        self.tokenizer=CharacterTokenizer()
        self.row=dict(id='val_1_refuse',original_id='val_1',question='When did Cedar open?',
                      docs=['First document.','Second document.','Third.','Fourth.','Fifth.'])

    def test_budget_and_gate_retain_explicit_requirements(self):
        self.assertEqual(self.config['rationale_max_new_tokens'],1024)
        self.assertEqual(self.config['decision_max_new_tokens'],128)
        self.assertEqual(self.config['max_new_tokens'],1152)
        self.assertEqual(self.config['smoke_minimum_structurally_valid_fraction'],2/3)
        invalid=dict(draft=dict(status='invalid'))
        valid=dict(draft=dict(status='valid_structure'))
        with self.assertRaises(ValueError):
            v4.audit.smoke_gate([valid]*5+[invalid]*4,9,self.config)
        self.assertEqual(v4.audit.smoke_gate([valid]*6+[invalid]*3,9,self.config)['valid'],6)

    def test_completed_longer_analysis_valid_but_original_truncation_stays_invalid(self):
        for complete in [True,False]:
            rationale='word '*80 if complete else 'word'*64
            first_tokens=[ord(c) for c in rationale]+([0] if complete else [])
            decision=decision_tokens(self.tokenizer,'refuse',[])+[0]
            raw=self.tokenizer.decode(decision,skip_special_tokens=True)
            first=v4.v3.render(self.row,self.config,self.tokenizer)
            second=v4.v3.render_decision(self.row,self.config,self.tokenizer,rationale)
            record=dict(id=self.row['id'],original_id=self.row['original_id'],rationale=rationale,
                        rationale_sha256=v4.e.text_hash(rationale),rationale_token_ids=first_tokens,
                        raw_output=raw,raw_output_sha256=v4.e.text_hash(raw),decision_token_ids=decision,
                        prompt_sha256=v4.e.text_hash(first),decision_prompt_sha256=v4.e.text_hash(second),
                        input_tokens=len(first),decision_input_tokens=len(second),
                        generated_tokens=len(first_tokens)+len(decision),hit_output_limit=not complete,
                        draft=v4.v3.parse_draft(raw,self.row['docs'],not complete))
            with self.subTest(complete=complete),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'predictions.json';spec=dict(protocol_sha256='fixed')
                v4.e.repro.write_json(path,dict(spec=spec,records=[record]))
                replay=v4.v3.cached(path,spec,[self.row],self.config,self.tokenizer)
                self.assertEqual(replay[0]['draft']['status'],'valid_structure' if complete else 'invalid')

    def test_context_check_reserves_full_new_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            args=argparse.Namespace(model=directory)
            v4.e.repro.write_json(Path(directory)/'config.json',dict(max_position_embeddings=32768))
            result=v4.preflight(args,[self.row],self.config,self.tokenizer,[])
            self.assertEqual(result['budgets']['total'],1152)
            empty_decision=len(v4.e.encode(self.tokenizer,v4.v3.render_decision(self.row,self.config,self.tokenizer,''),'chat')['input_ids'])
            self.assertEqual(result['decision_input_upper_bound'],empty_decision+1024+8)
            v4.e.repro.write_json(Path(directory)/'config.json',dict(max_position_embeddings=100))
            with self.assertRaises(ValueError):
                v4.preflight(args,[self.row],self.config,self.tokenizer,[])

    def test_protocol_records_actual_budgets_and_new_code(self):
        with patch.object(v4.v3,'protocol',return_value=dict(generation={},code_and_prompt_sha256={})):
            spec=v4.protocol(None,None,None,self.config)
        self.assertEqual(spec['generation']['rationale_budget'],1024)
        self.assertEqual(spec['generation']['decision_budget'],128)
        self.assertEqual(spec['generation']['total_maximum_new_tokens'],1152)
        self.assertEqual(spec['schema_version'],4)
        self.assertEqual(len(spec['code_and_prompt_sha256']),4)


if __name__=='__main__':
    unittest.main()
