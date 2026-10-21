"""Integrity and denominator tests; these do not validate the author's judgments."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import semantic_transfer_exploratory_behavior_review as review


class ExploratoryBehaviorReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = review.read(review.ROOT, review.RUN + '/behavior_review/packet.json')
        cls.ratings = review.read(review.ROOT, review.PREFIX + '-ratings.json')

    def invalid(self, mutate):
        candidate = copy.deepcopy(self.ratings)
        mutate(candidate)
        with self.assertRaises(ValueError):
            review.validate_ratings(self.packet, candidate)

    def test_real_sealed_review_and_derived_artifacts_replay(self):
        for name, data in review.artifacts(review.ROOT).items():
            self.assertEqual((review.ROOT / name).read_bytes(), data)

    def test_missing_or_duplicate_anonymous_row_is_rejected(self):
        self.invalid(lambda x: x['ratings'].pop())
        self.invalid(lambda x: x['ratings'].__setitem__(-1, x['ratings'][0]))

    def test_exposure_cannot_be_upgraded_to_independent_or_training_gold(self):
        for key, value in [('history_exposed', False), ('independent_gold', True),
                ('approved_for_training', True), ('formal_semantic_labels_added', 240)]:
            with self.subTest(key=key):
                self.invalid(lambda x: x.__setitem__(key, value))

    def test_unreviewed_rows_are_not_completed_unknowns(self):
        self.invalid(lambda x: x['ratings'][0].__setitem__('status', 'unreviewed'))

    def test_quoted_text_and_character_offsets_are_both_bound(self):
        self.invalid(lambda x: x['ratings'][0]['input_citations'][0].__setitem__('quote', 'wrong'))
        self.invalid(lambda x: x['ratings'][0]['output_citations'][0].__setitem__('end', 1))

    def test_source_hash_and_all_five_read_slots_are_bound(self):
        self.invalid(lambda x: x['ratings'][0]['input_citations'][0].__setitem__('document_sha256', '0' * 64))
        self.invalid(lambda x: x['ratings'][0]['read_document_slots'].pop())

    def test_missing_output_citation_is_rejected(self):
        self.invalid(lambda x: x['ratings'][0].__setitem__('output_citations', []))

    def test_invalid_field_value_is_rejected(self):
        self.invalid(lambda x: x['ratings'][0].__setitem__('has_substantive_answer', 'probably'))

    def test_unresolved_selection_requires_an_adopted_answer(self):
        def mutate(x):
            x['ratings'][0]['selection_without_resolution'] = 'yes'
            x['ratings'][0]['selects_single_answer'] = 'no'
        self.invalid(mutate)

    def test_unknown_rate_retains_full_denominator_and_no_point_estimate(self):
        result = review.rate([dict(a=v) for v in ['yes', 'no', 'unknown', 'unknown']], 'a')
        self.assertEqual(result, dict(eligible=4, yes=1, no=1, unknown=2,
            point=None, lower=.25, upper=.75))
        self.assertIsNone(review.rate([], 'a')['point'])
        self.assertIsNone(review.rate([], 'a')['lower'])

    def test_joint_endpoint_uses_three_valued_logic(self):
        result = review.conjunctive_rate([dict(a='yes', b='yes'), dict(a='unknown', b='no'),
            dict(a='yes', b='unknown')], 'a', 'b')
        self.assertEqual((result['yes'], result['no'], result['unknown'], result['eligible']), (1, 1, 1, 3))

    def test_changed_preserved_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'original').write_bytes(b'old')
            hashes = {'original': review.digest(b'old')}
            review.verify_files(root, hashes)
            (root / 'original').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                review.verify_files(root, hashes)

    def test_anonymous_join_must_be_bijective_and_match_answers(self):
        sealed = review.validate_ratings(self.packet, self.ratings)
        real_read = review.read
        for target in ['mapping', 'answer']:
            def modified_read(root, path):
                value = real_read(root, path)
                if target == 'mapping' and path.endswith('/behavior_mapping.json'):
                    keys = list(value)
                    value[keys[0]] = value[keys[1]]
                if target == 'answer' and path.endswith('/predictions.json'):
                    value['records'][0]['raw_output'] = 'wrong answer'
                return value
            with self.subTest(target=target), patch.object(review, 'read', side_effect=modified_read):
                with self.assertRaises(ValueError):
                    review.join_rows(review.ROOT, self.packet, sealed)


if __name__ == '__main__':
    unittest.main()
