"""Manual decision completeness and provenance; no GPU or semantic auto-labeling."""
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from adjudicate_semantic_review import apply_decisions
import prepare_independent_semantic_review as review


class AdjudicationTests(unittest.TestCase):
    def setUp(self):
        self.original=[dict(item_id='item_1',has_substantive_answer='yes',
                            acknowledges_insufficiency='yes', acknowledges_conflict='no',
                            selects_single_answer='unknown',answer_correct='unknown',
                            reviewer='first-rater',notes='saved first judgment')]
        self.mapping={'behavioral_mapping':[{'review_id':'B1','source_item_id':'item_1'}]}
        self.diff=[{'review_id':'B1','field':'has_substantive_answer','old':'yes','independent':'unknown'}]
        self.decision=[{'review_id':'B1','final_fields':{'has_substantive_answer':'unknown'},
                        'adjudicator':'coordinator','reason':'Initial answer later undermined; unresolved commitment.'}]

    def test_unknown_survives_and_original_is_preserved(self):
        rows,audit=apply_decisions(self.original,self.mapping,self.diff,self.decision)
        self.assertEqual(rows[0]['has_substantive_answer'],'unknown')
        self.assertEqual(self.original[0]['has_substantive_answer'],'yes')
        self.assertEqual(rows[0]['reviewer'],'coordinator')
        self.assertIn('saved first judgment',rows[0]['notes'])
        self.assertTrue(audit[0]['changed_from_v3'])

    def test_missing_duplicate_and_unexpected_cells_are_rejected(self):
        for decisions in [[],self.decision*2,
                [dict(self.decision[0],final_fields={'answer_correct':'no'})]]:
            with self.subTest(decisions=decisions),self.assertRaises(ValueError):
                apply_decisions(self.original,self.mapping,self.diff,decisions)

    def test_decision_cannot_be_applied_to_changed_original(self):
        changed=[dict(self.original[0],has_substantive_answer='no')]
        with self.assertRaises(ValueError):apply_decisions(changed,self.mapping,self.diff,self.decision)

    def test_no_answer_cannot_coexist_with_correct_concrete_answer(self):
        changed=[dict(self.original[0],answer_correct='yes')]
        decision=[dict(self.decision[0],final_fields={'has_substantive_answer':'no'})]
        with self.assertRaises(ValueError):apply_decisions(changed,self.mapping,self.diff,decision)

    def test_explicit_old_snapshot_preserves_hash_checks_after_formal_version_advances(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);snapshot=root/'history';snapshot.mkdir()
            (root/'annotations.csv').write_bytes(b'formal v4')
            (snapshot/'annotations.csv').write_bytes(b'old v3')
            mapping={'protected_sources':{'annotations.csv':review.sha(b'old v3')}}
            with patch.object(review,'ROOT',root):
                with self.assertRaises(ValueError):review.verify_sources(mapping)
                review.verify_sources(mapping,snapshot)
                (snapshot/'annotations.csv').write_bytes(b'tampered old snapshot')
                with self.assertRaises(ValueError):review.verify_sources(mapping,snapshot)


if __name__=='__main__':unittest.main()
