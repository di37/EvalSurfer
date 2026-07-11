from __future__ import annotations

import unittest

from evalsurfer.core.evaluate import Evaluator


class CoreEvaluatorTest(unittest.TestCase):
    def test_flattens_nested_and_flat_scores(self) -> None:
        nested = Evaluator.evaluate(
            {"sample": {"answer": "x"}, "scores": {"quality": {"correctness_accuracy": 4}}}
        )
        crit = nested["metrics"]["quality"]["criteria"]
        self.assertEqual(next(c for c in crit if c["id"] == "correctness_accuracy")["score"], 4)
        self.assertNotIn("diagnostics", nested)

    def test_rejects_non_mapping(self) -> None:
        with self.assertRaises(TypeError):
            Evaluator.evaluate(["not", "a", "mapping"])

    def test_unassessed_sample_reports_null_overall_not_zero(self) -> None:
        # Nothing was scored, so the overall score is null (honest) rather than a
        # misleading 0.0 that reads as the worst possible score.
        report = Evaluator.evaluate({"sample": {"answer": "x"}})
        self.assertIsNone(report["overall"]["score"])


if __name__ == "__main__":
    unittest.main()
