"""Separate first-line classification from whole-output formatting failures."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from analyze_prompt_baseline import first_line_label


class FirstLineAnalysisTests(unittest.TestCase):
    def test_explanation_and_repeated_labels_do_not_hide_first_line(self):
        for text, expected in [(" answer\n\nThe documents provide evidence", "answer"),
                               ("refuse\nOutput: refuse\nExplanation:", "refuse"),
                               (" conflict\nconflict", "conflict"),
                               ("\n REFUSE.\n", "refuse")]:
            self.assertEqual(first_line_label(text), expected)

    def test_multiple_labels_or_prose_on_first_line_remain_invalid(self):
        for text in ["answer conflict\nThe documents", "answer or refuse", "", "The answer is conflict.",
                     'Label: answer', '{"label":"answer"}', 'unknown\nanswer']:
            self.assertIsNone(first_line_label(text))


if __name__ == "__main__":
    unittest.main()
