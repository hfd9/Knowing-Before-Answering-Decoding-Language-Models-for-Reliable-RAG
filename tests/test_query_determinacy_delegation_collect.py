"""Exercise collection isolation and a failed batch without a model load."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import query_determinacy_delegation_collect as collect
import query_determinacy_delegation_collect_v2 as revise


class DelegationCollectionTests(unittest.TestCase):
    def test_dev_reads_no_reference_or_heldout_cases(self):
        original = Path.open

        def public_only(path, *args, **kwargs):
            if 'reference.json' in path.name or path.name == 'heldout-cases.json':
                raise AssertionError(f'opened {path.name}')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'open', public_only):
            manifest, cases, _, sequence = collect.public_plan('dev')
        self.assertEqual((len(cases), manifest['call_count'], len(sequence)), (8, 16, 16))
        self.assertEqual(len({(task['route'], task['case']) for task in sequence}), 16)

    def test_failed_batch_remains_unsealed_and_only_runs_once(self):
        class BrokenBackend:
            def __init__(self, environment):
                pass

            def generate(self, tasks):
                raise RuntimeError('simulated response failure')

        with TemporaryDirectory() as temp, patch.object(collect.local, 'environment_snapshot', return_value={}):
            output = Path(temp) / 'dev'
            with self.assertRaisesRegex(RuntimeError, 'simulated response failure'):
                collect.collect(output, 'dev', None, backend_class=BrokenBackend)
            self.assertTrue((output / '0000.attempt.json').is_file())
            self.assertFalse((output / '0000.record.json').exists())
            self.assertFalse((output / 'seal.json').exists())
            with self.assertRaises(FileExistsError):
                collect.collect(output, 'dev', None, backend_class=BrokenBackend)

    def test_heldout_needs_successful_dev_check_before_model_or_run_folder(self):
        with TemporaryDirectory() as temp, patch.object(collect, 'score', return_value={'interface_ready': False}), \
                patch.object(collect.local, 'environment_snapshot') as environment:
            output = Path(temp) / 'heldout'
            with self.assertRaisesRegex(ValueError, 'did not pass'):
                collect.collect(output, 'heldout', Path(temp) / 'dev')
            self.assertFalse(output.exists())
            environment.assert_not_called()

    def test_format_revision_preserves_extract_and_repeats_only_direct_dev(self):
        _, _, _, dev = revise.plan('dev')
        self.assertEqual([task['route'] for task in dev], ['direct'] * 8)
        _, _, _, original = collect.public_plan('heldout')
        _, _, _, revision = revise.plan('heldout')
        self.assertEqual(len(revision), 32)
        for first, second in zip(original, revision, strict=True):
            self.assertEqual((first['case'], first['route']), (second['case'], second['route']))
            if first['route'] == 'extract':
                self.assertEqual(first, second)
            else:
                self.assertTrue(second['prompt'].startswith(first['prompt'] + '\n'))

    def test_failed_revised_interface_blocks_heldout_before_model_load(self):
        with TemporaryDirectory() as temp, patch.object(revise, 'initial_dev_result', return_value={}), \
                patch.object(revise, 'score', return_value={'split': 'dev', 'interface_ready': False}), \
                patch.object(collect.local, 'environment_snapshot') as environment:
            output = Path(temp) / 'heldout'
            with self.assertRaisesRegex(ValueError, 'revised development interface failed'):
                revise.collect(output, 'heldout', Path(temp) / 'original', Path(temp) / 'revised')
            self.assertFalse(output.exists())
            environment.assert_not_called()


if __name__ == '__main__':
    unittest.main()
