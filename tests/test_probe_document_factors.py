"""Fact/prompt invariance, factorial pairing, source reuse and technical gates."""

import argparse
from collections import Counter
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import probe_document_factors as f
from test_controlled_evidence_pilot import Tokenizer


class DocumentFactorTests(unittest.TestCase):
    def test_80_cells_hold_question_facts_fixed_and_have_exact_tail_edits(self):
        spec, rows, edits, background = f.build()
        self.assertEqual(len(rows), 80)
        self.assertEqual(sum(r['source'] is not None for r in rows), 10)
        self.assertEqual(len(edits), 19)
        self.assertEqual(len(background), 20)
        for oid in {r['original_id'] for r in rows}:
            group = {(r['target_level'], r['background_level'], r['rotation']): r for r in rows if r['original_id'] == oid}
            self.assertEqual(len({r['question'] for r in group.values()}), 1)
            for edit in [r for r in edits if r['original_id'] == oid]:
                a = group['F', 'S', 0]['docs'][edit['source_target_slot'] - 1]
                b = group['C', 'S', 0]['docs'][edit['source_target_slot'] - 1]
                self.assertEqual(a[edit['start']:edit['end']], edit['before'])
                self.assertEqual(b, a[:edit['start']])
                self.assertIn(edit['retained_fact_quote'], b)
                self.assertEqual(b[edit['fact_start']:edit['fact_start'] + len(edit['retained_fact_quote'])], edit['retained_fact_quote'])
            if oid == 'val_86':
                slot = group['F', 'S', 0]['native_target_slots'][1] - 1
                self.assertEqual(group['C', 'S', 0]['docs'][slot], group['F', 'S', 0]['docs'][slot])
                self.assertIn('organisation account', group['C', 'S', 0]['docs'][slot])
        self.assertEqual(f.build()[1], rows)

    def test_rotation_preserves_multisets_and_maps_target_slots(self):
        rows = f.build()[1]
        for original in [r for r in rows if r['rotation'] == 0]:
            rotated = next(r for r in rows if r['original_id'] == original['original_id'] and r['rotation'] == 1
                           and r['target_level'] == original['target_level'] and r['background_level'] == original['background_level'])
            self.assertEqual(rotated['docs'], original['docs'][1:] + original['docs'][:1])
            self.assertEqual(Counter(rotated['docs']), Counter(original['docs']))
            for old_slot, new_slot in zip(original['native_target_slots'], rotated['rotated_target_slots']):
                self.assertEqual(original['docs'][old_slot - 1], rotated['docs'][new_slot - 1])

    def test_background_selection_keeps_complete_texts_and_original_duplicates(self):
        _, rows, _, _ = f.build()
        source = {r['id']: r for r in map(__import__('json').loads, f.m.SOURCE.read_text().splitlines())}
        for row in [r for r in rows if r['rotation'] == 0]:
            original = source[row['background_source_id']]
            expected = [original['docs'][i - 1] for i in row['background_source_slots']]
            actual = [text for i, text in enumerate(row['docs'], 1) if i not in row['native_target_slots']]
            self.assertEqual(expected, actual)
        row = next(r for r in rows if r['original_id'] == 'val_86' and r['background_level'] == 'L' and r['rotation'] == 0)
        self.assertEqual(row['background_source_slots'], [1, 3, 4])
        self.assertEqual(len(set(row['docs'])), 4)

    def test_factor_metadata_cannot_enter_prompt(self):
        row = f.build()[1][0]
        original = f.d.prompt(row, Tokenizer())
        changed = dict(row, target_level='SECRET', background_level='SECRET', source={'SECRET': 'SECRET'}, id='SECRET')
        self.assertEqual(original, f.d.prompt(changed, Tokenizer()))

    def test_report_has12_contrasts_and120_pairs_without_accuracy(self):
        rows = f.build()[1]
        records = [dict(r, input_tokens=100, origin='reused_endpoint' if r['source'] else 'new_forward', probe_pred='conflict',
                        probe_probabilities=dict(answer=.1, refuse=.1, conflict=.8)) for r in rows]
        result = f.summarize(rows, records)
        self.assertEqual(len(result['contrasts']), 12)
        self.assertEqual(len(result['paired']), 120)
        self.assertTrue(all(r['n_pairs'] == 10 for r in result['contrasts'].values()))
        self.assertEqual((result['new_forwards'], result['reused_endpoints']), (70, 10))
        self.assertNotIn('accuracy', result)
        with self.assertRaises(ValueError):
            f.summarize(rows, records[:-1])

    def test_gpu_busy_stops_before_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(run_dir=Path(tmp), model='unused', smoke=True)
            with patch.object(f.p.s, 'assert_gpu_idle', side_effect=RuntimeError('GPU busy')), \
                 patch.object(f.e, 'load_model', side_effect=AssertionError('Must not load')):
                with self.assertRaisesRegex(RuntimeError, 'busy'):
                    f.run(args, {}, [dict(id='one', source=None)], None, None, {})
            self.assertEqual(f.e.read_json(Path(tmp) / 'last_failure.json')['id'], 'one')

    def test_full_requires_valid_smoke_even_before_model_load(self):
        args = argparse.Namespace(run_dir=Path('/tmp/unused-factors'), model='unused', smoke=False)
        with patch.object(f, 'require_smoke', side_effect=ValueError('No valid smoke')), \
             patch.object(f.e, 'load_model', side_effect=AssertionError('Must not load')):
            with self.assertRaisesRegex(ValueError, 'No valid smoke'):
                f.run(args, {}, [], None, None, {})

    def test_real_tokenizer_probe_cache_bridge_and_completed_resume(self):
        model = f.e.read_json(f.d.DEFAULT / 'protocol.json')['model']
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(run_dir=Path(tmp), model=model, smoke=True)
            spec, rows, probe, tokenizer, _ = f.prepare(args)
            self.assertEqual(len(rows), 16)
            records = []
            for row in rows:
                h = f.d.source_state(row, tokenizer, model) if row['source'] else np.ones((36, 2048), dtype=np.float16)
                relative = f'features/{len(records):04d}.npy'; f.e.save_array(args.run_dir / relative, h)
                record = {k: row[k] for k in ['id', 'original_id', 'question_level', 'document_level', 'target_level', 'background_level', 'rotation']}
                record.update(origin='new_forward', capture_phase='decoder_prefill_without_generation',
                              prompt_sha256=f.e.text_hash(f.d.prompt(row, tokenizer)),
                              input_tokens=len(f.e.encode(tokenizer, f.d.prompt(row, tokenizer), 'chat')['input_ids']),
                              feature_file=relative, feature_sha256=f.m.digest(args.run_dir / relative), **f.d.prediction(probe, h))
                records.append(record)
            path = args.run_dir / 'states.json'
            value = dict(protocol_sha256=f.m.digest(args.run_dir / 'protocol.json'), records=records)
            f.e.repro.write_json(path, value)
            self.assertEqual(len(f.cache(args, rows, probe, tokenizer)), 16)
            self.assertFalse(f.gate(args, spec, rows, records, probe, tokenizer)['semantic_accuracy_gate'])
            self.assertEqual(len(f.gate(args, spec, rows, records, probe, tokenizer)['bridges']), 2)
            with patch.object(f.e, 'load_model', side_effect=AssertionError('Must not load on resume')):
                self.assertEqual(len(f.run(args, spec, rows, probe, tokenizer, {})), 16)
            for key, replacement in [('rotation', 9), ('target_level', 'BAD'), ('probe_pred', 'INVALID'), ('origin', 'reused_endpoint')]:
                bad = copy.deepcopy(value); bad['records'][0][key] = replacement; f.e.repro.write_json(path, bad)
                with self.subTest(key=key), self.assertRaises(ValueError):
                    f.cache(args, rows, probe, tokenizer)
            f.e.repro.write_json(path, value)
            source_index = next(i for i, r in enumerate(rows) if r['source'])
            feature = args.run_dir / records[source_index]['feature_file']; h = np.load(feature)
            f.e.save_array(feature, h * 2)
            with self.assertRaisesRegex(ValueError, 'bridge failed'):
                f.gate(args, spec, rows, records, probe, tokenizer)
            f.prepare(args, write=False)
            (args.run_dir / 'materials/target_edits.json').write_text('[]')
            with self.assertRaisesRegex(ValueError, 'artifact differs'):
                f.prepare(args, write=False)

    def test_launcher_stops_after_failed_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = Path(tmp) / 'scripts'; scripts.mkdir()
            launcher = scripts / 'run_probe_document_factors_review.sh'
            launcher.write_bytes((ROOT / 'scripts' / launcher.name).read_bytes())
            (scripts / 'run_probe_document_factors.sh').write_text('#!/bin/sh\nexit 7\n')
            result = subprocess.run(['sh', str(launcher)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse((Path(tmp) / 'runs/qwen2.5-3b-probe-document-factors-v1/launch/full.log').exists())


if __name__ == '__main__':
    unittest.main()
