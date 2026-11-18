import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import query_determinacy_exposure_inventory as audit


class ExposureInventoryTests(unittest.TestCase):
    def test_uses_only_listed_files_and_reports_aggregates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [{'prompt': '背景甲\n问题：是否满足？'}, {'prompt': '背景乙\n问题：是否满足？'}]
            (root / 'allow.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in rows))
            (root / 'sealed.jsonl').write_text('not valid JSON and must not be read')
            with patch.object(audit, 'ROOT', root), patch.object(audit, 'FILES', ('allow.jsonl',)), \
                 patch.object(audit, 'prior_question_groups', return_value={}):
                result = audit.inventory()
            self.assertEqual((result['total_rows'], result['distinct_exact_prompts'],
                              result['distinct_exact_question_lines']), (2, 2, 1))
            self.assertNotIn('是否满足', json.dumps(result, ensure_ascii=False))

    def test_absent_or_symlinked_listed_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(audit, 'ROOT', root), patch.object(audit, 'FILES', ('missing.jsonl',)):
                with self.assertRaises(ValueError):
                    audit.inventory()
            (root / 'real').write_text('{"prompt":"x"}\n')
            (root / 'link').symlink_to(root / 'real')
            with patch.object(audit, 'ROOT', root), patch.object(audit, 'FILES', ('link',)):
                with self.assertRaises(ValueError):
                    audit.inventory()

    def test_bad_input_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'bad').write_text('{"not_prompt":"x"}\n')
            with patch.object(audit, 'ROOT', root), patch.object(audit, 'FILES', ('bad',)):
                with self.assertRaises(ValueError):
                    audit.inventory()


if __name__ == '__main__':
    unittest.main()
