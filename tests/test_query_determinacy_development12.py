import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import query_determinacy_development12_material as material
import query_determinacy_development12_verify as verifier


class Development12Tests(unittest.TestCase):
    def test_rebuild_and_verify(self):
        public, ref = material.build()
        self.assertEqual(public, json.loads((material.BASE / 'public-12-v2.json').read_bytes()))
        self.assertEqual(ref, json.loads((material.BASE / 'reference-12-v2.json').read_bytes()))
        summary = verifier.verify()
        self.assertEqual(summary['families'], {'integer': 6, 'identifier': 6})
        self.assertEqual(summary['finals'], {'Y': 12, 'N': 12, 'U': 12})

    def test_wrong_world_label_and_missing_quote_are_rejected(self):
        public, ref = material.build()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'public-12-v2.json').write_text(json.dumps(public, ensure_ascii=False))
            case_id = public['cases'][0]['id']
            qid = public['cases'][0]['questions'][0]['id']
            ref['cases'][case_id]['questions'][qid]['world_answers'] = ['Y', 'Y']
            (root / 'reference-12-v2.json').write_text(json.dumps(ref, ensure_ascii=False))
            with patch.object(verifier, 'BASE', root):
                with self.assertRaises(ValueError):
                    verifier.verify()
            _, ref = material.build()
            ref['cases'][case_id]['worlds'][0]['source_quote'] = '不属于背景的引用'
            (root / 'reference-12-v2.json').write_text(json.dumps(ref, ensure_ascii=False))
            with patch.object(verifier, 'BASE', root):
                with self.assertRaises(ValueError):
                    verifier.verify()


if __name__ == '__main__':
    unittest.main()
