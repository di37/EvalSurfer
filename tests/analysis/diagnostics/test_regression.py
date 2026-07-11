from __future__ import annotations

import copy
import unittest

import evalsurfer.constants as constants
from evalsurfer.analysis.diagnostics.regression import CriterionDiff, RegressionDiffer


def _criterion(cid: str, name: str, score: int | None):
    return {"id": cid, "name": name, "score": score, "evidence": ""}


BEFORE = {
    "overall": {
        "score": 7.1,
        "decision": constants.DECISION_PASS_WITH_FIXES,
        "summary": "before",
    },
    "metrics": {
        constants.CATEGORY_QUALITY: {
            "score": 6.5,
            "criteria": [
                _criterion("correctness_accuracy", "Correctness / Accuracy", 2),
                _criterion("relevance", "Relevance", 4),
                _criterion("completeness", "Completeness", None),
            ],
        },
        constants.CATEGORY_OPERATIONAL: {
            "score": 7.0,
            "criteria": [_criterion("time_to_first_token", "Time to First Token", 3)],
        },
    },
    "assurance": {
        constants.CATEGORY_SAFETY: {
            "score": 9.0,
            "criteria": [_criterion("pii_leakage", "PII Leakage", 5)],
        },
    },
    "decision": constants.DECISION_PASS_WITH_FIXES,
    "coverage": {"applicable": 18, "assessed": 5, "score": 0.278, "missing": []},
}

AFTER = {
    "overall": {"score": 8.2, "decision": constants.DECISION_PASS, "summary": "after"},
    "metrics": {
        constants.CATEGORY_QUALITY: {
            "score": 8.0,
            "criteria": [
                _criterion("correctness_accuracy", "Correctness / Accuracy", 4),
                _criterion("relevance", "Relevance", 4),
                _criterion("completeness", "Completeness", 5),
                _criterion("instruction_following", "Instruction Following", 5),
            ],
        },
        constants.CATEGORY_OPERATIONAL: {
            "score": 7.0,
            "criteria": [_criterion("cost_per_request", "Cost per Request", 4)],
        },
    },
    "assurance": {
        constants.CATEGORY_SAFETY: {
            "score": 8.0,
            "criteria": [_criterion("pii_leakage", "PII Leakage", 4)],
        },
    },
    "decision": constants.DECISION_PASS,
    "coverage": {"applicable": 18, "assessed": 7, "score": 0.389, "missing": []},
}


def _by_id(diff):
    return {c["id"]: c for c in diff["criteria"]}


class OverallAndDecisionTest(unittest.TestCase):
    def test_overall_delta_rounds_to_one_decimal(self) -> None:
        self.assertEqual(RegressionDiffer.diff(BEFORE, AFTER)["overall_delta"], 1.1)

    def test_overall_delta_none_when_either_score_missing(self) -> None:
        self.assertIsNone(RegressionDiffer.diff({"overall": {}}, AFTER)["overall_delta"])
        self.assertIsNone(RegressionDiffer.diff(BEFORE, {})["overall_delta"])

    def test_decision_change_reports_from_and_to(self) -> None:
        self.assertEqual(
            RegressionDiffer.diff(BEFORE, AFTER)["decision_change"],
            {"from": constants.DECISION_PASS_WITH_FIXES, "to": constants.DECISION_PASS},
        )

    def test_decision_change_none_when_unchanged(self) -> None:
        self.assertIsNone(RegressionDiffer.diff(BEFORE, BEFORE)["decision_change"])

    def test_decision_prefers_top_level_over_overall(self) -> None:
        before = {"decision": constants.DECISION_PASS, "overall": {"decision": constants.DECISION_FAIL}}
        after = {"decision": constants.DECISION_PASS, "overall": {"decision": constants.DECISION_FAIL}}
        # Top-level "pass" wins on both sides, so nothing changed.
        self.assertIsNone(RegressionDiffer.diff(before, after)["decision_change"])

    def test_decision_falls_back_to_overall(self) -> None:
        before = {"overall": {"decision": constants.DECISION_FAIL}}
        after = {"overall": {"decision": constants.DECISION_PASS}}
        self.assertEqual(
            RegressionDiffer.diff(before, after)["decision_change"],
            {"from": constants.DECISION_FAIL, "to": constants.DECISION_PASS},
        )


class CategoryDeltaTest(unittest.TestCase):
    def test_category_deltas(self) -> None:
        categories = RegressionDiffer.diff(BEFORE, AFTER)["categories"]
        self.assertEqual(
            categories[constants.CATEGORY_QUALITY], {"before": 6.5, "after": 8.0, "delta": 1.5}
        )
        self.assertEqual(
            categories[constants.CATEGORY_SAFETY], {"before": 9.0, "after": 8.0, "delta": -1.0}
        )
        self.assertEqual(
            categories[constants.CATEGORY_OPERATIONAL], {"before": 7.0, "after": 7.0, "delta": 0.0}
        )

    def test_all_three_categories_always_present(self) -> None:
        categories = RegressionDiffer.diff({}, {})["categories"]
        self.assertEqual(set(categories), set(constants.CATEGORIES))
        for entry in categories.values():
            self.assertEqual(entry, {"before": None, "after": None, "delta": None})

    def test_category_delta_none_when_one_score_missing(self) -> None:
        before = {"metrics": {constants.CATEGORY_QUALITY: {"score": 6.0, "criteria": []}}}
        after = {"metrics": {constants.CATEGORY_QUALITY: {"score": None, "criteria": []}}}
        self.assertIsNone(
            RegressionDiffer.diff(before, after)["categories"][constants.CATEGORY_QUALITY]["delta"]
        )


class CriteriaDiffTest(unittest.TestCase):
    def test_change_classifications(self) -> None:
        by_id = _by_id(RegressionDiffer.diff(BEFORE, AFTER))
        self.assertEqual(by_id["correctness_accuracy"]["change"], constants.CHANGE_IMPROVED)
        self.assertEqual(by_id["correctness_accuracy"]["delta"], 2)
        self.assertEqual(by_id["relevance"]["change"], constants.CHANGE_UNCHANGED)
        self.assertEqual(by_id["relevance"]["delta"], 0)
        self.assertEqual(by_id["pii_leakage"]["change"], constants.CHANGE_REGRESSED)
        self.assertEqual(by_id["pii_leakage"]["delta"], -1)

    def test_added_from_none_score(self) -> None:
        # completeness went from a null score to 5 -> newly assessed.
        entry = _by_id(RegressionDiffer.diff(BEFORE, AFTER))["completeness"]
        self.assertEqual(entry["change"], constants.CHANGE_ADDED)
        self.assertIsNone(entry["before"])
        self.assertEqual(entry["after"], 5)
        self.assertIsNone(entry["delta"])

    def test_added_from_new_id(self) -> None:
        entry = _by_id(RegressionDiffer.diff(BEFORE, AFTER))["instruction_following"]
        self.assertEqual(entry["change"], constants.CHANGE_ADDED)
        self.assertIsNone(entry["before"])
        self.assertEqual(entry["after"], 5)

    def test_removed_when_id_absent_in_after(self) -> None:
        entry = _by_id(RegressionDiffer.diff(BEFORE, AFTER))["time_to_first_token"]
        self.assertEqual(entry["change"], constants.CHANGE_REMOVED)
        self.assertEqual(entry["before"], 3)
        self.assertIsNone(entry["after"])
        self.assertIsNone(entry["delta"])

    def test_none_in_both_is_unchanged(self) -> None:
        before = {"metrics": {constants.CATEGORY_QUALITY: {"criteria": [_criterion("x", "X", None)]}}}
        after = {"metrics": {constants.CATEGORY_QUALITY: {"criteria": [_criterion("x", "X", None)]}}}
        entry = _by_id(RegressionDiffer.diff(before, after))["x"]
        self.assertEqual(entry["change"], constants.CHANGE_UNCHANGED)
        self.assertIsNone(entry["delta"])

    def test_name_falls_back_to_before_then_id(self) -> None:
        before = {"metrics": {constants.CATEGORY_QUALITY: {"criteria": [_criterion("x", "Named", 3)]}}}
        after = {"metrics": {constants.CATEGORY_QUALITY: {"criteria": [{"id": "x", "score": 4}]}}}
        self.assertEqual(_by_id(RegressionDiffer.diff(before, after))["x"]["name"], "Named")
        # When neither report names it, fall back to the id.
        bare = {"metrics": {constants.CATEGORY_QUALITY: {"criteria": [{"id": "y", "score": 3}]}}}
        self.assertEqual(_by_id(RegressionDiffer.diff(bare, bare))["y"]["name"], "y")

    def test_criteria_matched_within_same_category(self) -> None:
        # The same id in different categories must not be matched across categories.
        before = {"metrics": {constants.CATEGORY_QUALITY: {"criteria": [_criterion("shared", "Q", 3)]}}}
        after = {"assurance": {constants.CATEGORY_SAFETY: {"criteria": [_criterion("shared", "S", 5)]}}}
        diff = RegressionDiffer.diff(before, after)
        changes = [(c["id"], c["change"]) for c in diff["criteria"]]
        # quality "shared" disappears (removed); safety "shared" appears (added).
        self.assertEqual(
            changes,
            [("shared", constants.CHANGE_REMOVED), ("shared", constants.CHANGE_ADDED)],
        )

    def test_criteria_ordering_is_category_then_before_then_new(self) -> None:
        ids = [c["id"] for c in RegressionDiffer.diff(BEFORE, AFTER)["criteria"]]
        # Category order follows constants.CATEGORIES (quality, operational, safety).
        self.assertEqual(
            ids,
            [
                "correctness_accuracy",
                "relevance",
                "completeness",
                "instruction_following",
                "time_to_first_token",
                "cost_per_request",
                "pii_leakage",
            ],
        )

    def test_every_change_is_a_known_kind(self) -> None:
        for entry in RegressionDiffer.diff(BEFORE, AFTER)["criteria"]:
            self.assertIn(entry["change"], constants.CHANGES)


class RegressionsImprovementsTest(unittest.TestCase):
    def test_regressions_and_improvements_lists(self) -> None:
        diff = RegressionDiffer.diff(BEFORE, AFTER)
        self.assertEqual(diff["regressions"], ["pii_leakage"])
        self.assertEqual(diff["improvements"], ["correctness_accuracy"])

    def test_removed_and_added_are_not_regressions_or_improvements(self) -> None:
        diff = RegressionDiffer.diff(BEFORE, AFTER)
        self.assertNotIn("time_to_first_token", diff["regressions"])
        self.assertNotIn("completeness", diff["improvements"])


class CoverageDeltaTest(unittest.TestCase):
    def test_coverage_delta_rounds_to_three(self) -> None:
        self.assertEqual(RegressionDiffer.diff(BEFORE, AFTER)["coverage_delta"], 0.111)

    def test_coverage_delta_none_when_missing(self) -> None:
        self.assertIsNone(RegressionDiffer.diff({}, AFTER)["coverage_delta"])
        self.assertIsNone(RegressionDiffer.diff(BEFORE, {"coverage": {}})["coverage_delta"])


class IdenticalAndEmptyTest(unittest.TestCase):
    def test_identical_reports_show_no_movement(self) -> None:
        diff = RegressionDiffer.diff(BEFORE, BEFORE)
        self.assertEqual(diff["overall_delta"], 0.0)
        self.assertIsNone(diff["decision_change"])
        self.assertEqual(diff["coverage_delta"], 0.0)
        self.assertEqual(diff["regressions"], [])
        self.assertEqual(diff["improvements"], [])
        for entry in diff["criteria"]:
            self.assertEqual(entry["change"], constants.CHANGE_UNCHANGED)

    def test_empty_reports(self) -> None:
        diff = RegressionDiffer.diff({}, {})
        self.assertIsNone(diff["overall_delta"])
        self.assertIsNone(diff["decision_change"])
        self.assertIsNone(diff["coverage_delta"])
        self.assertEqual(diff["criteria"], [])
        self.assertEqual(diff["regressions"], [])
        self.assertEqual(diff["improvements"], [])

    def test_missing_categories_key_is_tolerated(self) -> None:
        diff = RegressionDiffer.diff({"overall": {"score": 5.0}}, {"overall": {"score": 6.0}})
        self.assertEqual(diff["overall_delta"], 1.0)
        self.assertEqual(diff["criteria"], [])


class ValidationAndImmutabilityTest(unittest.TestCase):
    def test_rejects_non_mapping_inputs(self) -> None:
        with self.assertRaises(TypeError):
            RegressionDiffer.diff([], {})
        with self.assertRaises(TypeError):
            RegressionDiffer.diff({}, "not a report")

    def test_inputs_are_not_mutated(self) -> None:
        before_snapshot = copy.deepcopy(BEFORE)
        after_snapshot = copy.deepcopy(AFTER)
        RegressionDiffer.diff(BEFORE, AFTER)
        self.assertEqual(BEFORE, before_snapshot)
        self.assertEqual(AFTER, after_snapshot)

    def test_criterion_diff_to_dict_shape(self) -> None:
        record = CriterionDiff(
            id="x",
            name="X",
            before=2,
            after=4,
            delta=2,
            change=constants.CHANGE_IMPROVED,
        )
        self.assertEqual(
            record.to_dict(),
            {
                "id": "x",
                "name": "X",
                "before": 2,
                "after": 4,
                "delta": 2,
                "change": constants.CHANGE_IMPROVED,
            },
        )


if __name__ == "__main__":
    unittest.main()
