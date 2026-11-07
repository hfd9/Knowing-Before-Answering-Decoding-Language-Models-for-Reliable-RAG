import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import verify_explanation_scope_input_review_20261107 as verifier


class ArchivedReviewVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.archive = Path(self.temp.name) / 'archive'
        shutil.copytree(verifier.ARCHIVE, self.archive)

    def verify(self):
        with patch.object(verifier, 'ARCHIVE', self.archive), contextlib.redirect_stdout(io.StringIO()):
            verifier.main()

    def change_json(self, relative, update):
        path = self.archive / relative
        data = json.loads(path.read_text())
        update(data)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

    def test_archived_review_replays(self):
        self.verify()

    def test_modified_batch_response_fails(self):
        self.change_json('input/batch01-response.txt',
                         lambda x: x['items'][0]['evidence_citations'][0].update(quote='fabricated quote'))
        with self.assertRaises(ValueError):
            self.verify()

    def test_focal_delivery_cannot_precede_input_seal(self):
        self.change_json('coordinator/phase2_focal_delivery.json',
                         lambda x: x.update(delivered_at='2020-01-01T00:00:00+00:00'))
        with self.assertRaisesRegex(ValueError, 'focal case timing differs'):
            self.verify()

    def test_modified_post_seal_comparison_is_detected(self):
        self.change_json('coordinator/post_seal_comparison.json',
                         lambda x: x['rows'][0].update(state_agrees=False))
        with self.assertRaisesRegex(ValueError, 'state or conflict comparison differs'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
