"""CPU material, counterfactual-witness and generation-recovery checks; no real model calls."""

from contextlib import ExitStack, redirect_stdout
import copy
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import behavior_binding_study as study


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.spec = study.read(study.SPEC)
        self.rows, self.worlds = study.make_materials(self.spec)

    def test_material_pairing_balance_and_two_compatible_completions(self):
        self.assertEqual(len(self.rows), 48)
        self.assertEqual(len(self.worlds), 24)
        for row in self.rows:
            if row['condition'] == 'I':
                w = self.worlds[row['id']]['worlds']
                self.assertNotEqual(w[0]['assignments'][row['target_entity']],
                                    w[1]['assignments'][row['target_entity']])
                self.assertNotIn(row['target_value'], '\n'.join(row['docs']))
        self.assertEqual([r['id'] for r in study.ordered_rows(self.rows, self.spec)[:4]],
                         self.spec['smoke_prefix_ids'])
        self.assertEqual(study.make_materials(self.spec), (self.rows, self.worlds))

    def test_target_leak_witness_change_and_unrelated_edit_rejected(self):
        for kind in ['leak', 'world', 'background', 'question']:
            rows, worlds = copy.deepcopy((self.rows, self.worlds))
            row = next(r for r in rows if r['condition'] == 'I')
            if kind == 'leak':
                row['docs'][4] += ' ' + row['target_value']
            elif kind == 'world':
                worlds[row['id']]['worlds'][0]['assignments'][row['distractor_entity']] = 'bad'
            elif kind == 'question':
                row['question'] += ' ' + row['target_value']
            else:
                row['docs'][4] += ' changed background'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                study.validate_materials(rows, worlds, self.spec)

    def test_renderer_receives_only_question_documents(self):
        self.assertEqual(set(study.renderer_inputs(self.rows[0])), {'question', 'docs'})
        with self.assertRaisesRegex(ValueError, 'dedicated run'):
            study.validate_location(ROOT / 'runs')

    def test_prepare_real_source_files_freeze_and_readonly_replay(self):
        import evidence_experiment as e
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            model = study.read(study.MODEL_REFERENCE)['model']
            info = dict(model=model, model_files_sha256={'synthetic': 'cpu-test-only'},
                        runtime_versions={'fixture': '1'}, context_tokens=32768)
            with patch.object(study, 'DEFAULT', run), patch.object(study, 'runtime',
                    return_value=(e, object(), info)), patch.object(e, 'render_input',
                    side_effect=lambda row, *args: study.encoded(row).decode()), patch.object(
                    e, 'encode', return_value={'input_ids': [7]}):
                rows, protocol, _ = study.prepare(run, write=True)
                self.assertEqual(len(rows), 48)
                self.assertEqual(protocol['new_probe_fits'], 0)
                self.assertEqual(len(protocol['implementation_sha256']), 12)
                before = {str(p): study.digest(p) for p in run.rglob('*') if p.is_file()}
                study.prepare(run, write=False)
                self.assertEqual(before, {str(p): study.digest(p) for p in run.rglob('*') if p.is_file()})

    def fixture(self, run):
        rows = study.ordered_rows(self.rows, self.spec)
        protocol = dict(model='synthetic-no-model', eos_token_ids=[2], ordered_ids=[r['id'] for r in rows])
        study.save(run / 'protocol.json', protocol)
        return rows, protocol

    def simulation(self, empty=False, interrupt_at=None):
        import evidence_experiment as e
        class Tokenizer:
            def __len__(self):
                return 100
            def decode(self, tokens, **kwargs):
                return '' if tokens == [2] else 'Synthetic saved answer.'
        tok = Tokenizer()
        calls = []
        stack = ExitStack()
        def render(row, *args):
            return study.encoded(row).decode()
        def generate(model, tokenizer, row, protocol):
            if interrupt_at is not None and len(calls) == interrupt_at:
                raise RuntimeError('Synthetic interruption after attempt')
            index = len(calls)
            calls.append(row['id'])
            tokens = [2] if empty and index == 0 else [10, 2]
            raw = tok.decode(tokens)
            return dict(**{k: row[k] for k in ['id', 'original_id', 'condition', 'variant']},
                prompt_sha256=study.sha(render(study.renderer_inputs(row))), input_tokens=1,
                input_token_ids_sha256=study.sha('[7]'), generated_token_ids=tokens,
                generated_tokens=len(tokens), raw_output=raw, raw_output_sha256=study.sha(raw),
                ended_with_eos=True, hit_output_limit=False, elapsed_seconds=0,
                completed_at='2026-10-21T00:00:00+00:00')
        stack.enter_context(patch.object(e, 'render_input', side_effect=render))
        stack.enter_context(patch.object(e, 'encode', return_value={'input_ids': [7]}))
        stack.enter_context(patch.object(study, 'generate', side_effect=generate))
        loader = stack.enter_context(patch.object(e, 'load_model', return_value=object()))
        stack.enter_context(patch('classification_semantic_baseline.assert_gpu_idle'))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return stack, tok, calls, loader

    def test_all48_finish_and_resume_without_loading_model_or_scoring(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            rows, protocol = self.fixture(run)
            stack, tok, calls, loader = self.simulation()
            with stack:
                study.collect(run, rows, protocol, tok)
                report = study.finish(run, rows, protocol, tok)
                self.assertEqual((len(calls), loader.call_count), (48, 1))
                self.assertIsNone(report['primary_distractor_adoption_rate'])
                self.assertIsNone(report['S_correct_rate'])
                self.assertEqual(report['behavior_rows_reviewed'], 0)
                study.collect(run, rows, protocol, tok)
                self.assertEqual((len(calls), loader.call_count), (48, 1))
                before = {str(p): study.digest(p) for p in run.rglob('*') if p.is_file()}
                self.assertEqual(study.finish(run, rows, protocol, tok, verify=True), report)
                self.assertEqual(before, {str(p): study.digest(p) for p in run.rglob('*') if p.is_file()})
                packet = study.read(run / 'behavior_review/packet.json')
                self.assertTrue(all(set(r) == {'item_id', 'question', 'documents', 'answer'} for r in packet['items']))
                ratings = study.read(run / 'behavior_review/ratings_template.json')['ratings']
                self.assertTrue(all(r['status'] == 'unreviewed'
                    and all(r[f] == 'unknown' for f in study.FIELDS) for r in ratings))

    def test_failed_smoke_stops_at_four_without_rerun(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            rows, protocol = self.fixture(run)
            stack, tok, calls, loader = self.simulation(empty=True)
            with stack:
                for _ in range(2):
                    with self.assertRaisesRegex(ValueError, 'Technical smoke failed'):
                        study.collect(run, rows, protocol, tok)
                self.assertEqual((len(calls), loader.call_count), (4, 1))

    def test_uncommitted_attempt_blocks_model_reload_and_duplicate_answer(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            rows, protocol = self.fixture(run)
            stack, tok, calls, loader = self.simulation(interrupt_at=2)
            with stack:
                with self.assertRaisesRegex(RuntimeError, 'Synthetic interruption'):
                    study.collect(run, rows, protocol, tok)
                self.assertEqual(len(calls), 2)
                with self.assertRaisesRegex(ValueError, 'Uncommitted generation attempt'):
                    study.collect(run, rows, protocol, tok)
                self.assertEqual(loader.call_count, 1)

    def test_cache_tampering_rejected_before_any_new_model_call(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            rows, protocol = self.fixture(run)
            stack, tok, calls, loader = self.simulation()
            with stack:
                study.collect(run, rows, protocol, tok)
                original = study.read(run / 'predictions.json')
                changes = [dict(raw_output='tampered'), dict(input_tokens=99),
                    dict(ended_with_eos=False), dict(condition='other'),
                    dict(generated_token_ids=[2, 10, 2]), dict(generated_token_ids=[1000, 2]),
                    dict(elapsed_seconds=float('nan'))]
                for change in changes:
                    value = copy.deepcopy(original)
                    value['records'][0].update(change)
                    study.save(run / 'predictions.json', value)
                    with self.subTest(change=change), self.assertRaises(ValueError):
                        study.collect(run, rows, protocol, tok)
                self.assertEqual((len(calls), loader.call_count), (48, 1))

    def test_incomplete_cache_cannot_export_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            rows, protocol = self.fixture(run)
            stack, tok, calls, loader = self.simulation()
            with stack, self.assertRaisesRegex(ValueError, 'all48'):
                study.finish(run, rows, protocol, tok)
            self.assertFalse((run / 'completion.json').exists())
            self.assertEqual(loader.call_count, 0)

    def test_atomic_immutable_output_refuses_changed_content(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fixed.json'
            study.save(path, {'fixed': 1}, immutable=True)
            with self.assertRaisesRegex(ValueError, 'Frozen artifact mismatch'):
                study.save(path, {'fixed': 2}, immutable=True)
            self.assertEqual(study.read(path), {'fixed': 1})


if __name__ == '__main__':
    unittest.main()
