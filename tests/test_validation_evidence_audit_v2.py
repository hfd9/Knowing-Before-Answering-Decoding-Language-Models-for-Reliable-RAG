"""Check the v2 prompt contract and failure visibility without GPU inference."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import validation_evidence_audit as v1
import validation_evidence_audit_v2 as v2


class AuditV2Tests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(v2.CONFIG.read_text())

    def test_prompt_examples_pass_unchanged_strict_parser(self):
        objects = [json.loads(line) for line in self.config['instruction'].splitlines()
                   if line.startswith('{"semantic_mode"')][1:]
        docs = ['Luma was born in Merin.', 'Luma was born in Tovan, not Merin.', '', '', '']
        self.assertEqual([x['semantic_mode'] for x in objects], v1.MODES)
        for value in objects:
            with self.subTest(mode=value['semantic_mode']):
                result = v1.parse_draft(json.dumps(value), docs)
                self.assertEqual(result['status'], 'valid_structure')
        self.assertEqual(self.config['max_new_tokens'], 512)
        self.assertEqual(self.config['smoke_minimum_structurally_valid_fraction'], 2/3)

    def test_full_inputs_preserved_and_labels_excluded(self):
        class Tokenizer:
            def apply_chat_template(self, messages, **kwargs):
                return json.dumps(messages, ensure_ascii=False)
        row = dict(question='ACTUAL_QUESTION?', docs=['FULL_DOC_'+str(i) for i in range(5)],
                   true_mode='SECRET_LABEL', gold_answer='SECRET_GOLD')
        messages = json.loads(v2.render(row, self.config, Tokenizer()))
        user = messages[1]['content']
        self.assertEqual(messages[0]['content'], self.config['instruction'])
        for doc in row['docs']:
            self.assertIn(doc, user)
        self.assertIn(row['question'], user)
        self.assertNotIn('SECRET_', json.dumps(messages))
        self.assertIn('strings', user)

    def test_v2_launcher_and_prompt_are_fingerprinted(self):
        with patch.object(v2, '_v1_protocol', return_value={'code_and_prompt_sha256': {}}):
            result = v2.protocol(None, None, None, self.config)
        self.assertEqual(result['audit_version'], 2)
        for path in ['scripts/validation_evidence_audit_v2.py',
                     'scripts/run_validation_evidence_audit_v2.sh',
                     'scripts/run_validation_evidence_audit_v2_review.sh',
                     'prompts/validation_evidence_audit_v2.json']:
            self.assertEqual(result['code_and_prompt_sha256'][path], v1.e.repro.digest_file(ROOT/path))

    def test_launcher_gate_and_full_failures_are_visible(self):
        for gate_exit, full_exit, expected_calls in [(0, 0, 3), (1, 0, 2), (0, 7, 3)]:
            with self.subTest(gate=gate_exit, full=full_exit), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                scripts = base/'scripts'
                scripts.mkdir()
                launcher = scripts/'run_validation_evidence_audit_v2_review.sh'
                launcher.write_text((ROOT/'scripts'/launcher.name).read_text())
                (scripts/'run_validation_evidence_audit_v2.sh').write_text(
                    '#!/bin/sh\n'
                    'printf "%s\\n" "$*" >> "$KBA_TEST_TRACE"\n'
                    'echo simulated_log_line\n'
                    'case "$*" in\n'
                    '*smoke-gate*) exit "$KBA_TEST_GATE_EXIT" ;;\n'
                    '*smoke-v2*) exit 0 ;;\n'
                    '*) exit "$KBA_TEST_FULL_EXIT" ;;\nesac\n')
                env = dict(os.environ, KBA_TEST_TRACE=str(base/'trace'),
                           KBA_TEST_GATE_EXIT=str(gate_exit), KBA_TEST_FULL_EXIT=str(full_exit))
                process = subprocess.run(['sh', str(launcher)], env=env, capture_output=True, text=True)
                self.assertEqual(process.returncode, gate_exit or full_exit)
                self.assertEqual(len((base/'trace').read_text().splitlines()), expected_calls)
                if gate_exit or full_exit:
                    self.assertIn('failed', process.stderr)
                    self.assertIn('simulated_log_line', process.stderr)
                if gate_exit:
                    self.assertIn('full run was not started', process.stderr)


if __name__ == '__main__':
    unittest.main()
