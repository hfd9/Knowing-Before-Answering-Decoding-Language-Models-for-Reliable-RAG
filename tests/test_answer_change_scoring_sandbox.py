import unittest

from scripts.answer_change_scoring_sandbox import compare_first_failure, metric_counts, tri_and


class ScoringSandboxTests(unittest.TestCase):
    def test_unknown_does_not_hide_known_pair_failure(self):
        self.assertEqual(tri_and("no", "unknown"), "no")
        self.assertEqual(tri_and("yes", "unknown"), "unknown")
        self.assertEqual(tri_and("yes", "yes"), "yes")
        with self.assertRaises(ValueError):
            tri_and()

    def test_counts_preserve_unknown_and_unrun(self):
        result = metric_counts([("completed", "yes"), ("completed", "no"),
                                ("completed", "unknown"), ("not_run", None),
                                ("failed", None), ("truncated", None)])
        self.assertEqual((result["planned"], result["assessable"]), (6, 2))
        self.assertEqual(result["status_counts"]["completed"], 3)
        self.assertEqual(result["completed_bound"], [1 / 3, 2 / 3])
        self.assertEqual(result["status_counts"]["not_run"], 1)

    def test_empty_completed_is_undefined_not_zero(self):
        self.assertIsNone(metric_counts([("not_run", None)])["completed_bound"])
        self.assertIsNone(metric_counts([])["completed_bound"])

    def test_incomplete_cannot_silently_receive_label(self):
        with self.assertRaises(ValueError):
            metric_counts([("truncated", "no")])
        with self.assertRaises(ValueError):
            metric_counts([("completed", None)])

    def test_triad_table_keeps_premise_unknown_and_failure_unknown(self):
        groups = [
            {"old_correct": "yes", "new_correct": "yes", "missing_failure": "yes"},
            {"old_correct": "yes", "new_correct": "unknown", "missing_failure": "no"},
            {"old_correct": "no", "new_correct": "unknown", "missing_failure": "unknown"},
            {"old_correct": "yes", "new_correct": "yes", "missing_failure": "unknown"},
        ]
        result = compare_first_failure(groups)
        self.assertEqual(result["groups"], 4)
        self.assertEqual(result["cells"]["yes"]["yes"], 1)
        self.assertEqual(result["cells"]["yes"]["unknown"], 1)
        self.assertEqual(result["cells"]["unknown"]["no"], 1)
        self.assertEqual(result["cells"]["no"]["unknown"], 1)


if __name__ == "__main__":
    unittest.main()
