import unittest

from scripts import probe_measurement_existing_cache_audit_20261109 as audit


class ExistingCacheAuditTests(unittest.TestCase):
    def test_duplicate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate identifier'):
            audit.index([{'id': 'x'}, {'id': 'x'}])

    def test_group_preserves_unknown_and_counts_paired_bases(self):
        rows = [
            dict(group='g', original_id='a', reference_match_pattern='both',
                 calibrated_class_same=True, token_delta=0, right_reference_p_change_positive=True),
            dict(group='g', original_id='a', reference_match_pattern='unknown',
                 calibrated_class_same=False, token_delta=3, right_reference_p_change_positive=None),
            dict(group='g', original_id='b', reference_match_pattern='neither',
                 calibrated_class_same=True, token_delta=-1, right_reference_p_change_positive=False),
        ]
        result = audit.group_counts(rows, ['group'])[0]
        self.assertEqual((result['pairs'], result['bases']), (3, 2))
        self.assertEqual((result['both_match'], result['neither_match'], result['reference_unknown']), (1, 1, 1))
        self.assertEqual((result['class_same'], result['class_changed']), (2, 1))
        self.assertEqual((result['token_delta_zero'], result['token_delta_nonzero']), (1, 2))
        self.assertEqual((result['right_reference_p_increase'], result['right_reference_p_decrease_or_equal'],
                          result['right_reference_p_unavailable']), (1, 1, 1))


if __name__ == '__main__':
    unittest.main()
