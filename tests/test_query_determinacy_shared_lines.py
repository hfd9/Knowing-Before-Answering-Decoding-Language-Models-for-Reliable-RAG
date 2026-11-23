"""CPU checks for the released line-output entry and frozen-run regression."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_shared_lines as lines
import query_determinacy_shared_lines_run as run
import query_determinacy_shared_lines_score as scorer

OLD_RESULTS = ROOT / 'docs/review/2026-11-23-shared-pilot-results-v1/results.json'


class FixtureTokenizer:
    def __init__(self, outputs):
        self.outputs = outputs

    def __len__(self):
        return 152000

    @staticmethod
    def apply_chat_template(messages, **_kwargs):
        return messages[0]['content']

    def __call__(self, text, **_kwargs):
        return {'input_ids': list(text.encode())}

    def decode(self, tokens, **_kwargs):
        return self.outputs[tokens[0] - 1000]


class FixtureBackend:
    def __init__(self, outputs, eos, truncate_at=None):
        self.tok = FixtureTokenizer(outputs)
        self.outputs = outputs
        self.eos = eos
        self.truncate_at = truncate_at
        self.calls = []

    def __call__(self, text, attempt):
        index = attempt['index']
        self.calls.append(index)
        rendered, ids = run.base.tokenize(self.tok, text)
        truncated = index == self.truncate_at
        generated = [index + 1000] + ([] if truncated else [self.eos])
        return {'status': 'truncated' if truncated else 'complete', 'output': self.outputs[index],
                'input_tokens': len(ids), 'output_tokens': len(generated), 'rendered_prompt': rendered,
                'input_token_ids': ids, 'generated_token_ids': generated}


def evidence_line(value, answer, index, domain):
    suffix = f',R{index}' if domain == 'identifier' else ''
    return f'W={value}|{answer}|S{index}{suffix}'


class SharedLinesTests(unittest.TestCase):
    def setUp(self):
        self.release, self.public, self.extra = run.release_config()
        self.reference = json.loads(scorer.REFERENCE.read_bytes())
        self.cases = {case['id']: case for case in self.public['cases']}
        self.old = json.loads(OLD_RESULTS.read_bytes())
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'run'
        self.addCleanup(patch.stopall)
        patch.object(run, 'RUN', self.path).start()

    def expected_outputs(self):
        result = []
        for case, question, kind, branch in run.base.slots(self.public):
            ref = self.reference['cases'][case['id']]
            values = [world['value'] for world in ref['worlds']]
            if kind == 'extract':
                result.append(json.dumps(values))
                continue
            qr = ref['questions'][question['id']]
            rows = [evidence_line(v, a, i, case['domain'])
                    for i, (v,a) in enumerate(zip(values, qr['world_answers']), 1)]
            result.append(rows[branch] if kind == 'branch' else '\n'.join([*rows, f'F={qr["final"]}']))
        return result

    def setup_backend(self, outputs, truncate_at=None):
        env = self.release['environment']
        backend = FixtureBackend(outputs, env['eos_token_ids'][0], truncate_at)
        patch.object(run.base, 'load_tokenizer', return_value=backend.tok).start()
        patch.object(run.base, 'environment_snapshot', return_value=env).start()
        patch.object(run.base, 'verify_device', return_value={'gpu_uuid': 'GPU-fixture'}).start()
        patch.object(run.base, 'QwenBackend', return_value=backend).start()
        return backend

    def test_all_real_entry_stages_with_cpu_fixture_and_seal(self):
        backend = self.setup_backend(self.expected_outputs())
        with patch.object(scorer, 'REFERENCE', Path(self.tmp.name) / 'not-there'), redirect_stdout(io.StringIO()):
            run.prepare(self.path)
            self.assertEqual(run.process(self.path)['count'], 0)
            state = run.process(self.path, collect=True)
            self.assertEqual(state['count'], 26)
            self.assertEqual(run.process(self.path, collect=True), state)
            seal = Path(self.tmp.name) / 'seal.json'
            digest = scorer.seal(self.path, seal)
            with self.assertRaisesRegex(ValueError, 'before reference'):
                scorer.score_sealed(seal, '0' * 64)
        scored = scorer.score_sealed(seal, digest)
        self.assertEqual(len(backend.calls), 26)
        self.assertEqual(len(state['device_preflights']), 1)
        self.assertEqual([v['correct_and_supported'] for v in scored['method_totals'].values()], [6, 6, 6])
        self.assertEqual([v['readable'] for v in scored['method_totals'].values()], [6, 6, 6])
        self.assertEqual(sum(c['branch']['attempted_calls'] for c in scored['costs_by_case'].values()), 14)

    def test_invalid_extract_skip_and_terminal_failure_preserved(self):
        outputs = self.expected_outputs()
        outputs[3] = 'not JSON'
        backend = self.setup_backend(outputs, truncate_at=16)
        run.prepare(self.path)
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'technical failure preserved'):
            run.process(self.path, collect=True)
        state = run.process(self.path)
        self.assertEqual((state['count'], state['blocked']), (17, True))
        self.assertEqual(backend.calls, [0,1,2,3,13,14,15,16])
        score = scorer.score_state(state, self.reference)
        self.assertEqual(score['method_totals']['joint']['unresolved'], 6)
        self.assertEqual(score['method_totals']['direct']['readable'], 6)
        with self.assertRaisesRegex(ValueError, 'technical failure preserved'):
            run.process(self.path, collect=True)
        self.assertEqual(len(backend.calls), 8)

    def test_evidence_map_is_byte_exact_and_public_prompts_are_shared(self):
        values = ('34', '58')
        for case in self.public['cases']:
            spans = lines.evidence_map(case)
            raw = case['background'].encode()
            for span in spans.values():
                self.assertEqual(raw[span['start_byte']:span['end_byte']].decode(), span['text'])
            common = lines.prompt('extract', case, None).split('\n提取')[0]
            self.assertEqual(re.sub(r'\[[SR][12]\]', '', common).split('材料：\n')[1], case['background'])
            for kind, branch in (('direct',None), ('joint',None), ('branch',0)):
                self.assertTrue(lines.prompt(kind, case, case['questions'][0], values, branch).startswith(common))

    def test_all_old_outputs_and_diagnostic_labels_regress(self):
        self.assertEqual(len(self.old['outputs']), 26)
        for row in self.old['outputs']:
            domain = self.cases[row['case']]['domain']
            if row['kind'] == 'extract':
                self.assertEqual(run.base.extract.parse(row['output'], domain)['status'], 'parsed')
            else:
                with self.assertRaises(ValueError):
                    lines.parse(row['output'], domain, single_world=row['kind']=='branch')

        # Serialize the separately audited explicit labels as fixtures. This preserves
        # their old decisions, not their evidence or their original format grade.
        for row in self.old['descriptive_label_check']:
            cid, qid = row['case'], row['question']
            case_ref = self.reference['cases'][cid]
            domain = self.cases[cid]['domain']
            values = [world['value'] for world in case_ref['worlds']]
            spans = self.extra['evidence_map'][cid]
            evidence = scorer.required_ids(case_ref, spans)
            for method, expected in row['methods'].items():
                world_lines = [f'W={v}|{label}|-' for v,label in zip(values, expected['raw_world_answers'])]
                texts = world_lines if method == 'branch' else ['\n'.join([*world_lines, 'F='+expected['raw_final']])]
                result = scorer.grade(method, [{'status':'complete', 'output':t} for t in texts], domain,
                                      values, case_ref, case_ref['questions'][qid], evidence)
                self.assertEqual(result['final'], expected['raw_final'])
                self.assertEqual([w['answer'] for w in result['worlds']], expected['raw_world_answers'])
                self.assertFalse(result['correct_and_supported'])
                if qid == 'r2':
                    self.assertFalse(result['worlds'][0]['correct'])
                    if method != 'branch':
                        self.assertFalse(result['final_matches_merge'])
                        self.assertTrue(result['final_correct'])

    def test_distinguishes_evidence_and_wrong_candidate_from_grammar(self):
        ref = self.reference['cases']['D7M4']
        expected = ref['questions']['r2']
        spans = self.extra['evidence_map']['D7M4']
        ids = scorer.required_ids(ref, spans)
        status = lambda s: {'status': 'complete', 'output': s}
        for citation in ('S2', 'R9', '-'):
            text = f'W=34|Y|{citation}\r\nW=58|Y|S2\r\nF=Y\r\n'
            row = scorer.grade('joint', [status(text)], 'integer', ['34','58'], ref, expected, ids)
            self.assertTrue(row['readable'] and row['final_correct'])
            self.assertEqual(row['worlds'][0]['evidence_status'], 'missing_or_wrong_id')
        texts = [status('W=58|Y|S2'), status('W=34|Y|S1')]
        row = scorer.grade('branch', texts, 'integer', ['34','58'], ref, expected, ids)
        self.assertTrue(row['readable'])
        self.assertFalse(row['extraction_binding_ok'] or row['resolved'])
        row = scorer.grade('direct', [status('W=34|N|S1\nW=58|Y|S2\nF=Y')], 'integer', None, ref, expected, ids)
        self.assertEqual(row['worlds'][0]['evidence_status'], 'contradicts')
        self.assertEqual(row['evidence_implies'], 'Y')
        self.assertFalse(row['correct_and_supported'])

    def test_rejects_malformed_rows_without_repair(self):
        for text in ('W=34单位|Y|S1','W=34|U|S1','W=34|Y|S1,S1','W=34|Y|S1\n\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                lines.parse(text, 'integer', single_world=True)
        for text in ('W=34|Y|S1\nW=34|Y|S2\nF=Y', 'W=34|Y|S1\nW=58|Y|S2\nF=N\n说明'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                lines.parse(text, 'integer', single_world=False)

    def test_unmatched_attempt_blocks_before_device_access(self):
        run.prepare(self.path)
        (self.path / 'attempts/0000.json').touch()
        with patch.object(run.base, 'verify_device') as device:
            with self.assertRaisesRegex(ValueError, 'unfinished'):
                run.process(self.path, collect=True)
            device.assert_not_called()


if __name__ == '__main__':
    unittest.main()
