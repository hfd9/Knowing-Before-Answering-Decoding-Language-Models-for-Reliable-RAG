import copy
from contextlib import nullcontext
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import query_determinacy_shared_live as live
import query_determinacy_shared_score as scorer
import query_determinacy_two_case_cpu as old_mock

BASE = ROOT / 'docs/review/2026-11-18-two-case-cpu-v1'
PUBLIC = json.loads((BASE/'public.json').read_bytes())
REF = BASE/'reference.json'
REF_SHA = hashlib.sha256(REF.read_bytes()).hexdigest()


class Backend:
    def __init__(self, mode='normal'):
        self.mode = mode
        self.calls = []

    def __call__(self, prompt, attempt):
        self.calls.append(attempt)
        c = next(c for c in PUBLIC['cases'] if c['id'] == attempt['case'])
        question = next((q for q in c['questions'] if q['id'] == attempt['question']), None)
        kind = attempt['kind']
        values = None
        if kind == 'joint':
            values = json.loads(prompt.split('上一步抽取得到候选：', 1)[1].split('。这些只是', 1)[0])
        if kind == 'branch':
            value = json.loads(prompt.split('上一步抽取得到一个待检验的候选：', 1)[1].split('。只在', 1)[0])
            values = [value]
        if self.mode == 'invalid' and c['id'] == 'D7M4' and kind == 'extract':
            raw = '[true,2]'
        elif self.mode == 'wrong_candidate' and c['id'] == 'D7M4' and kind == 'extract':
            raw = '["34","99"]'
        elif self.mode == 'truncated' and kind == 'extract':
            return {'status': 'truncated', 'output': '["34"', 'input_tokens': 4, 'output_tokens': 2}
        else:
            req = {'question': question['text'] if question else None, 'values': values}
            if self.mode == 'wrong_candidate' and values and '99' in values:
                # A valid but wrong actual extraction must not be repaired with reference values.
                if kind == 'branch':
                    raw = json.dumps({'value': values[0], 'answer': 'N', 'citations': []})
                else:
                    raw = json.dumps({'final': 'N', 'worlds': [{'value': v, 'answer': 'N', 'citations': []} for v in values]})
            else:
                oldmode = 'adversarial' if self.mode == 'adversarial' else 'normal'
                raw = old_mock.mock(kind, req, c, oldmode)['output']
        return {'status': 'complete', 'output': raw, 'input_tokens': len(prompt), 'output_tokens': len(raw)}


class SharedLiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = self.root/'run'
        live.init_run(self.run, PUBLIC)

    def score(self):
        sealed = self.root/'seal.json'
        digest = scorer.seal(self.run, sealed)
        return scorer.score(sealed, digest, REF, REF_SHA)

    def test_normal_and_reference_separation(self):
        backend = Backend()
        result = live.collect(self.run, backend)
        self.assertEqual((result['count'], result['total'], len(backend.calls)), (26, 26, 26))
        self.assertNotIn('reference', (self.run/'public.json').read_text())
        scored = self.score()
        for row in scored['rows']:
            for method in ('direct', 'joint', 'branch'):
                self.assertTrue(row[method]['correct_and_supported'], (row['case'], row['question'], method))
        for cost in scored['route_costs']:
            self.assertEqual(cost['executed_calls'], cost['planned_calls'])
        self.assertEqual(len(Backend().calls), 0)
        self.assertEqual(len(live.collect(self.run, backend)['entries']), 26)
        self.assertEqual(len(backend.calls), 26)

    def test_invalid_extract_skips_downstream_but_direct_is_scored(self):
        backend = Backend('invalid')
        result = live.collect(self.run, backend)
        self.assertEqual((result['count'], len(backend.calls)), (26, 17))
        for row in self.score()['rows']:
            if row['case'] == 'D7M4':
                self.assertTrue(row['direct']['correct_and_supported'])
                self.assertEqual(row['extraction_status'], 'invalid')
                self.assertEqual(row['joint']['status'], 'unresolved')
                self.assertEqual(row['branch']['status'], 'unresolved')

    def test_wrong_extraction_is_not_reference_corrected(self):
        backend = Backend('wrong_candidate')
        live.collect(self.run, backend)
        rows = [r for r in self.score()['rows'] if r['case'] == 'D7M4']
        self.assertTrue(all(r['extracted'] == ['34', '99'] and not r['extraction_correct'] for r in rows))
        self.assertTrue(all(r['joint']['status'] == 'wrong_candidates' and r['branch']['status'] == 'wrong_candidates' for r in rows))
        prompts = [x['prompt'] for x in backend.calls if x['case'] == 'D7M4' and x['kind'] in ('joint', 'branch')]
        self.assertTrue(all('99' in x for x in prompts if '待检验的候选：' in x and '候选：[' in x))

    def test_adversarial_joint_worlds_and_citations(self):
        live.collect(self.run, Backend('adversarial'))
        rows = self.score()['rows']
        row = next(r for r in rows if r['case'] == 'D7M4' and r['question'] == 'p4')
        for name in ('direct', 'joint', 'branch'):
            self.assertTrue(row[name]['final_correct'])
            self.assertFalse(row[name]['all_worlds_correct'])
            self.assertFalse(row[name]['correct_and_supported'])
        row = next(r for r in rows if r['case'] == 'N3K6' and r['question'] == 'u5')
        for name in ('direct', 'joint', 'branch'):
            self.assertTrue(row[name]['all_worlds_correct'])
            self.assertFalse(row[name]['all_evidence_ok'])

    def test_truncation_saved_and_retry_blocked(self):
        backend = Backend('truncated')
        with self.assertRaisesRegex(ValueError, 'technical failure'):
            live.collect(self.run, backend)
        self.assertEqual((len(backend.calls), live.replay(self.run)['count']), (4, 4))
        with self.assertRaisesRegex(ValueError, 'manual audit'):
            live.collect(self.run, backend)
        self.assertEqual(len(backend.calls), 4)
        self.assertEqual(len(self.score()['rows']), 6)

    def test_interrupted_attempt_blocks(self):
        (self.run/'attempts'/'0000.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'unfinished'):
            live.collect(self.run, Backend())

    def test_changed_prompt_detected(self):
        live.collect(self.run, Backend())
        path = self.run/'attempts'/'0000.json'
        data = json.loads(path.read_bytes()); data['prompt'] += 'changed'; path.write_bytes(live.encode(data))
        with self.assertRaisesRegex(ValueError, 'attempt changed'):
            live.replay(self.run)

    def test_resume_clean_prefix_and_hold_lock(self):
        backend = Backend()
        original = live.write_new
        def interrupted(path, data):
            if path.name == '0003.json' and path.parent.name == 'attempts':
                raise OSError('simulated interruption before next attempt')
            original(path, data)
        with patch.object(live, 'write_new', side_effect=interrupted):
            with self.assertRaisesRegex(OSError, 'simulated interruption'):
                live.collect(self.run, backend)
        self.assertEqual(live.replay(self.run)['count'], 3)
        with live.locked(self.run):
            with self.assertRaises(BlockingIOError):
                live.collect(self.run, backend)
        self.assertEqual(live.collect(self.run, backend)['count'], 26)
        self.assertEqual(len(backend.calls), 26)

    def test_record_corruption_is_detected(self):
        live.collect(self.run, Backend())
        path = self.run/'records'/'0000.json'
        data = json.loads(path.read_bytes()); data['output'] += 'tamper'; path.write_bytes(live.encode(data))
        with self.assertRaisesRegex(ValueError, 'output hash'):
            live.replay(self.run)

    def test_route_choice_requires_complete_paired_costs_and_no_new_u_selection(self):
        def entry(final, correct=True, status='scored'):
            return {'status': status, 'final': final, 'correct_and_supported': correct}
        rows = [{'reference_final': 'U', 'direct': entry('U'), 'joint': entry('U'), 'branch': entry('U')}]
        costs = [{'route': route, 'planned_calls': 1, 'journal_slots': 1, 'skipped_extract': 0,
                  'input_tokens': cost, 'output_tokens': 1} for route, cost in (('direct', 1), ('joint', 3), ('branch', 5))]
        self.assertEqual(scorer.development_choice(rows, costs)['candidate'], 'direct')
        rows[0]['direct'] = entry('Y', False)
        self.assertEqual(scorer.development_choice(rows, costs)['status'], 'no_conclusion')
        rows[0]['direct'] = entry('U', status='unresolved')
        self.assertEqual(scorer.development_choice(rows, costs)['reason'], 'unscored_or_missing')
        for method in ('direct', 'joint', 'branch'):
            rows[0][method] = entry('U', False)
        self.assertEqual(scorer.development_choice(rows, costs)['status'], 'no_conclusion')

    def test_seal_checked_before_reference_and_manifest_bound(self):
        live.collect(self.run, Backend())
        sealed = self.root/'seal.json'; scorer.seal(self.run, sealed)
        with self.assertRaisesRegex(ValueError, 'seal hash'):
            scorer.score(sealed, '0'*64, self.root/'missing-reference', REF_SHA)
        public = self.run/'public.json'; public.write_bytes(public.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError, 'manifest'):
            live.replay(self.run)

    def test_real_cli_rejects_missing_user_flag_and_wrong_directory(self):
        missing = self.root/'must-not-exist'
        p = subprocess.run([sys.executable, str(ROOT/'scripts/query_determinacy_shared_live.py'), 'collect', str(missing)], text=True, capture_output=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('requires --user-executed', p.stderr)
        p = subprocess.run([sys.executable, str(ROOT/'scripts/query_determinacy_shared_live.py'),
                            'prepare', str(missing), '--user-executed'], text=True, capture_output=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('fixed two-case pilot run directory', p.stderr)
        self.assertFalse(missing.exists())

    def test_released_entry_runs_with_fake_device_and_replays_tokens(self):
        run = self.root / 'pilot'
        env = json.loads(live.RELEASE.read_bytes())['environment']
        eos = env['eos_token_ids'][0]
        class Tokenizer:
            def __len__(self): return max(env['eos_token_ids']) + 1
            def apply_chat_template(self, messages, **kwargs): return messages[0]['content'] + '\nrendered'
            def __call__(self, *args, **kwargs): return {'input_ids': [10, 11]}
            def decode(self, *args, **kwargs): return '[]'
        tok = Tokenizer()
        def fake_backend(text, _attempt):
            rendered, ids = live.tokenize(tok, text)
            return {'status': 'complete', 'output': '[]', 'input_tokens': len(ids), 'output_tokens': 2,
                    'rendered_prompt': rendered, 'input_token_ids': ids, 'generated_token_ids': [20, eos]}
        with patch.object(live, 'PILOT_RUN', run), patch.object(live, 'environment_snapshot', return_value=env), \
                patch.object(live, 'verify_device', return_value={'gpu_uuid': 'GPU-fixture'}) as device, \
                patch.object(live, 'QwenBackend', return_value=fake_backend), patch.object(live, 'load_tokenizer', return_value=tok):
            live.prepare_live(run)
            device.assert_not_called()
            result = live.collect_live(run)
            self.assertEqual((result['count'], result['total']), (26, 26))
            self.assertEqual(sum(e['record']['status'] == 'skipped_extract' for e in result['entries']), 18)
            sealed = self.root / 'pilot-seal.json'
            seal_hash = scorer.seal(run, sealed)
            with self.assertRaisesRegex(ValueError, 'scoring reference does not match release'):
                scorer.score(sealed, seal_hash, self.root / 'missing', '0' * 64)
            self.assertEqual(scorer.score(sealed, seal_hash, REF, REF_SHA)['count_planned_questions'], 6)
            self.assertEqual(live.collect_live(run)['count'], 26)
            device.assert_called_once()
            record_path = run / 'records/0000.json'
            row = json.loads(record_path.read_bytes())
            row['input_token_ids'] = [99, 11]
            row['input_token_ids_sha256'] = live.sha(live.encode(row['input_token_ids']))
            record_path.write_bytes(live.encode(row))
            with self.assertRaisesRegex(ValueError, 'token or prompt mismatch'):
                live.replay(run)

    def test_reject_reference_fields_in_public(self):
        value = copy.deepcopy(PUBLIC); value['cases'][0]['reference'] = 'Y'
        with self.assertRaisesRegex(ValueError, 'reference'):
            live.validate_public(value)

    def test_adapter_with_cpu_fake_torch_and_model(self):
        class Vector:
            def __init__(self, values): self.values = values
            def tolist(self): return self.values
        class Matrix:
            ndim = 2
            shape = (1, 4)
            def __getitem__(self, item): return Vector([10, 11, 20, 99][item[1]])
        class Cuda:
            @staticmethod
            def synchronize(): pass
        class Torch:
            cuda = Cuda()
            long = object()
            @staticmethod
            def tensor(*args, **kwargs): return 'fake_tensor'
            @staticmethod
            def ones_like(value): return value
            @staticmethod
            def inference_mode(): return nullcontext()
        class Tokenizer:
            @staticmethod
            def apply_chat_template(*args, **kwargs): return 'rendered'
            @staticmethod
            def decode(ids, **kwargs): return 'answer'
            def __call__(self, *args, **kwargs): return {'input_ids': [10, 11]}
        class Model:
            config = type('Config', (), {'max_position_embeddings': 32768})()
            @staticmethod
            def generate(**kwargs): return Matrix()
        backend = object.__new__(live.QwenBackend)
        backend.torch, backend.tok, backend.model, backend.cfg, backend.eos = Torch(), Tokenizer(), Model(), {}, [99]
        result = backend('prompt', {})
        self.assertEqual((result['status'], result['input_token_ids'], result['generated_token_ids']),
                         ('complete', [10, 11], [20, 99]))
        backend.eos = [100]
        self.assertEqual(backend('prompt', {})['status'], 'truncated')


if __name__ == '__main__':
    unittest.main()
