import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import query_determinacy_prompt_results as result


class ResultTests(unittest.TestCase):
    def test_uncertain_and_incorrect_answers_remain_separate(self):
        self.assertEqual(result.category({'reference':'U','commitment':'N'}),'unsupported_choice')
        self.assertEqual(result.category({'reference':'N','commitment':'U'}),'overreserve')
        self.assertEqual(result.category({'reference':'U','commitment':'X'}),'unknown')
        self.assertEqual(result.category({'reference':'Y','commitment':'T'}),'technical_missing')

    def test_source_archive_detects_changed_live_file(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'file').write_bytes(b'original\n')
            archive=root/'a.json';archive.write_text(json.dumps({'files':[{'path':'file','raw_utf8':'original\n',
                'sha256':hashlib.sha256(b'original\n').hexdigest()}]}))
            with patch.object(result,'ROOT',root):
                self.assertEqual(len(result.verify_archive(archive,1)),1)
                (root/'file').write_bytes(b'modified\n')
                with self.assertRaisesRegex(ValueError,'differ'):result.verify_archive(archive,1)

    def test_paired_counts_conserve_each_planned_denominator(self):
        stats=result.analyze()
        self.assertEqual((stats['paired_source_inputs'],stats['review_rows']),(72,144))
        for name,counts in stats['pair_transitions'].items():
            self.assertEqual(sum(counts.values()),24 if name.endswith('dual_determinate') else 12)
        self.assertEqual(stats['groups']['plain/number/dual_split']['counts']['unsupported_choice'],4)


if __name__=='__main__':unittest.main()
