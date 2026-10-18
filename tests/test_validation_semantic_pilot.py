"""Check selection, exact quotes and pre-reveal integrity without semantic inference."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import validation_semantic_pilot as pilot


class PilotTests(unittest.TestCase):
    def prepare(self,root):
        source=root/'runs/qwen2.5-3b-small/data/instances_val.jsonl'
        source.parent.mkdir(parents=True)
        rows=[dict(id=f'val_{i}_{mode}',original_id=f'val_{i}',question=f'Question {i}',
                   docs=[f'Original {i} document {j}.' for j in range(5)],true_mode=mode,gold_answer='SECRET_GOLD')
              for i in range(95) for mode in ['answer','refuse','conflict']]
        source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        (source.parent/'manifest.json').write_text(json.dumps(dict(splits=dict(val=dict(sha256=pilot.digest(source))))))
        for path in ['runs/qwen2.5-3b-validation-evidence-audit-v4/drafts/predictions.json',
                     'runs/qwen2.5-3b-free-answer-study/annotations.csv',
                     'runs/qwen2.5-3b-classification-grid/chat8/val/predictions.json']+[
                     f'runs/qwen2.5-3b-classification-prompt-validation-v3/{n}/predictions.json'
                     for n in ['definitions','decision_order','illustrations']]:
            target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('{}')
        base=root/'pilot'
        with patch.object(pilot,'ROOT',root),contextlib.redirect_stdout(io.StringIO()):pilot.prepare(base)
        return base

    def ratings(self,base):
        return [dict(review_id=r['review_id'],semantic_mode='refuse',reason='Fixture has no target answer.',
                     required_facts=['Target answer'],missing_facts=['Target answer'],conflicting_claims=[],
                     citations=[],question_interpretation='Fixture question',reviewer='test_fixture',all_five_documents_read=True)
                for r in pilot.read(base/'public/inputs.json')['records']]

    def test_sampling_is_complete_idempotent_and_public_packet_excludes_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base=self.prepare(root)
            packet=pilot.read(base/'public/inputs.json')
            self.assertEqual(len(packet['records']),30)
            self.assertEqual(len({r['group_id'] for r in packet['records']}),10)
            text=(base/'public/inputs.json').read_text()
            self.assertNotIn('SECRET_GOLD',text);self.assertNotIn('true_mode',text)
            original=pilot.digest(base/'protocol.json')
            with patch.object(pilot,'ROOT',root),contextlib.redirect_stdout(io.StringIO()):pilot.prepare(base)
            self.assertEqual(pilot.digest(base/'protocol.json'),original)
            with self.assertRaises(ValueError):pilot.save_new(base/'protocol.json',{'changed':True})

    def test_incomplete_unread_or_fabricated_quote_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as directory:
            base=self.prepare(Path(directory))
            with self.assertRaises(ValueError):pilot.reveal(base)
            ratings=self.ratings(base);path=base/'input_ratings.json'
            path.write_text(json.dumps(ratings[:-1]))
            with self.assertRaises(ValueError):pilot.seal(base)
            ratings[0]['all_five_documents_read']=False;path.write_text(json.dumps(ratings))
            with self.assertRaises(ValueError):pilot.seal(base)
            ratings[0]['all_five_documents_read']=True
            ratings[0]['citations']=[dict(doc_id=1,quote='NOT_IN_DOCUMENT')];path.write_text(json.dumps(ratings))
            with self.assertRaises(ValueError):pilot.seal(base)

    def test_changed_sealed_rating_or_protected_source_blocks_reveal(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);base=self.prepare(root);path=base/'input_ratings.json'
            ratings=self.ratings(base);path.write_text(json.dumps(ratings));original=path.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):pilot.seal(base)
            ratings[0]['reason']='Changed after sealing';path.write_text(json.dumps(ratings))
            with self.assertRaises(ValueError):pilot.reveal(base)
            path.write_bytes(original)
            target=root/'runs/qwen2.5-3b-validation-evidence-audit-v4/drafts/predictions.json'
            target.write_text('{"changed":true}')
            with patch.object(pilot,'ROOT',root),self.assertRaises(ValueError):pilot.reveal(base)
            self.assertFalse((base/'revealed/model_outputs.json').exists())


if __name__=='__main__':unittest.main()
