from __future__ import annotations

import copy
import unittest

import evalsurfer.constants as constants
from evalsurfer.analysis.diagnostics.explainability import Deduction, Explainer
from evalsurfer.core.scoring import ScoringModel


def _report(categories: dict[str, list[tuple[str, int | None]]]) -> dict:
    """Build a minimal report from {category: [(id, score), ...]}, nesting each
    category under its metrics / assurance report section."""

    report: dict = {}
    for category, criteria in categories.items():
        layer = constants.LAYER_BY_CATEGORY[category]
        report.setdefault(layer, {})[category] = {
            "criteria": [
                {"id": cid, "name": cid.replace("_", " ").title(), "score": score}
                for cid, score in criteria
            ]
        }
    return report


class PerfectReportTest(unittest.TestCase):
    def test_perfect_report_has_no_deductions(self) -> None:
        report = _report(
            {"quality": [("a", 5), ("b", 5)], "safety": [("c", 5)]}
        )
        result = Explainer.explain(report)
        self.assertEqual(result["perfect"], 10.0)
        self.assertEqual(result["overall"], 10.0)
        self.assertEqual(result["deductions"], [])
        self.assertEqual(result["reconstructed"], 10.0)


class AttributionMathTest(unittest.TestCase):
    def test_deductions_sum_to_lost_points_multi_category(self) -> None:
        # quality mean(4,2)*2 = 6.0 ; safety mean(5,3)*2 = 8.0 ; overall = 7.0
        report = _report(
            {"quality": [("acc", 4), ("rel", 2)], "safety": [("tox", 5), ("bias", 3)]}
        )
        result = Explainer.explain(report)
        overall = result["overall"]
        self.assertEqual(overall, 7.0)

        total_lost = sum(d["points_lost"] for d in result["deductions"])
        # The core invariant: attributed deductions reconstruct (10 - overall).
        self.assertAlmostEqual(total_lost, constants.PERFECT_SCORE - overall, delta=0.01)
        self.assertEqual(result["reconstructed"], overall)

    def test_deduction_values_and_descending_order(self) -> None:
        report = _report(
            {"quality": [("acc", 4), ("rel", 2)], "safety": [("tox", 5), ("bias", 3)]}
        )
        deductions = Explainer.explain(report)["deductions"]
        # tox scored 5 -> no deduction; three imperfect criteria remain.
        self.assertEqual(len(deductions), 3)

        by_points = [(d["id"], d["points_lost"]) for d in deductions]
        # (5-2)*2/(2*2)=1.5 ; (5-3)*2/(2*2)=1.0 ; (5-4)*2/(2*2)=0.5
        self.assertEqual(by_points, [("rel", 1.5), ("bias", 1.0), ("acc", 0.5)])

        points = [d["points_lost"] for d in deductions]
        self.assertEqual(points, sorted(points, reverse=True))

    def test_single_category_denominator(self) -> None:
        report = _report({"quality": [("a", 4), ("b", 4)]})
        result = Explainer.explain(report)
        self.assertEqual(result["overall"], 8.0)  # mean(4,4)*2
        # P = 1, n_p = 2 -> (5-4)*2/(2*1) = 1.0 each
        points = [d["points_lost"] for d in result["deductions"]]
        self.assertEqual(points, [1.0, 1.0])
        self.assertAlmostEqual(sum(points), constants.PERFECT_SCORE - result["overall"], delta=0.01)


class AssessedOnlyTest(unittest.TestCase):
    def test_perfect_criteria_count_toward_denominator(self) -> None:
        # score 5 loses no points but still counts in n_p, so bias's deduction
        # uses n_p = 2 (denominator 2), not 1.
        report = _report({"quality": [("tox", 5), ("bias", 3), ("skip", None)]})
        result = Explainer.explain(report)
        self.assertEqual(result["overall"], 8.0)  # mean(5,3)*2, None excluded
        self.assertEqual(len(result["deductions"]), 1)
        self.assertEqual(result["deductions"][0]["id"], "bias")
        self.assertEqual(result["deductions"][0]["points_lost"], 2.0)  # (5-3)*2/(2*1)
        self.assertAlmostEqual(
            result["deductions"][0]["points_lost"],
            constants.PERFECT_SCORE - result["overall"],
            delta=0.01,
        )

    def test_category_with_all_none_is_not_counted(self) -> None:
        report = _report(
            {"quality": [("a", 3)], "operational": [("x", None), ("y", None)]}
        )
        result = Explainer.explain(report)
        # Only quality is assessed, so P = 1 and overall = mean(3)*2 = 6.0.
        self.assertEqual(result["overall"], 6.0)
        self.assertEqual(len(result["deductions"]), 1)
        self.assertEqual(result["deductions"][0]["points_lost"], 4.0)  # (5-3)*2/(1*1)


class EdgeCaseTest(unittest.TestCase):
    def test_empty_report(self) -> None:
        result = Explainer.explain({})
        self.assertEqual(result["perfect"], 10.0)
        self.assertIsNone(result["overall"])
        self.assertEqual(result["deductions"], [])
        self.assertEqual(result["reconstructed"], 10.0)

    def test_missing_categories_key_tolerated(self) -> None:
        self.assertEqual(Explainer.explain({"metadata": {"x": 1}})["deductions"], [])

    def test_missing_criteria_key_tolerated(self) -> None:
        result = Explainer.explain(
            {"metrics": {"quality": {}}, "assurance": {"safety": {"criteria": []}}}
        )
        self.assertEqual(result["deductions"], [])
        self.assertIsNone(result["overall"])

    def test_missing_name_and_id_tolerated(self) -> None:
        report = {"metrics": {"quality": {"criteria": [{"score": 3}]}}}
        deduction = Explainer.explain(report)["deductions"][0]
        self.assertIsNone(deduction["id"])
        self.assertEqual(deduction["name"], "")
        self.assertEqual(deduction["points_lost"], 4.0)  # (5-3)*2/(1*1)

    def test_none_name_falls_back_to_id(self) -> None:
        report = {
            "metrics": {"quality": {"criteria": [{"id": "acc", "name": None, "score": 2}]}}
        }
        self.assertEqual(Explainer.explain(report)["deductions"][0]["name"], "acc")


class ValidationTest(unittest.TestCase):
    def test_non_mapping_report_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            Explainer.explain([1, 2, 3])  # type: ignore[arg-type]

    def test_out_of_range_score_raises(self) -> None:
        report = _report({"quality": [("a", 7)]})
        with self.assertRaises(ValueError):
            Explainer.explain(report)

    def test_non_integer_score_raises(self) -> None:
        report = {"metrics": {"quality": {"criteria": [{"id": "a", "score": "5"}]}}}
        with self.assertRaises(ValueError):
            Explainer.explain(report)

    def test_boolean_score_rejected(self) -> None:
        report = {"metrics": {"quality": {"criteria": [{"id": "a", "score": True}]}}}
        with self.assertRaises(ValueError):
            Explainer.explain(report)


class ImmutabilityTest(unittest.TestCase):
    def test_input_report_is_not_mutated(self) -> None:
        report = _report(
            {"quality": [("acc", 4), ("rel", 2)], "safety": [("tox", 5)]}
        )
        snapshot = copy.deepcopy(report)
        Explainer.explain(report)
        self.assertEqual(report, snapshot)

    def test_deduction_dataclass_is_frozen(self) -> None:
        deduction = Deduction(id="a", name="A", category="quality", score=3, points_lost=1.0)
        with self.assertRaises(Exception):
            deduction.points_lost = 2.0  # type: ignore[misc]


class ConsistencyWithScoringTest(unittest.TestCase):
    def test_overall_matches_score_report(self) -> None:
        report = _report(
            {"quality": [("a", 4), ("b", 3)], "safety": [("c", 5), ("d", 2)]}
        )
        self.assertEqual(Explainer.explain(report)["overall"], ScoringModel.score(report)["overall"])


if __name__ == "__main__":
    unittest.main()
