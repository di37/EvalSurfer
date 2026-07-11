from __future__ import annotations

import copy
import unittest

import evalsurfer.constants as constants
from evalsurfer.core.report import Gate, GateResult, ReportValidator, ValidationResult


def _valid_report():
    """Build a minimal, fully valid report."""

    return {
        "overall": {"score": 8.0, "decision": constants.DECISION_PASS, "summary": "ok"},
        "metrics": {
            "quality": {
                "score": 8.0,
                "criteria": [
                    {"id": "relevance", "name": "Relevance", "score": 4, "evidence": "..."},
                    {"id": "completeness", "name": "Completeness", "score": None, "evidence": "..."},
                ],
            },
        },
        "assurance": {
            "safety": {
                "score": 9.0,
                "criteria": [
                    {"id": "toxicity", "name": "Toxicity", "score": 5, "evidence": "..."}
                ],
            },
        },
        "decision": constants.DECISION_PASS,
        "top_issues": [{"severity": constants.SEVERITY_MINOR, "description": "verbose"}],
    }


class ReportValidatorTest(unittest.TestCase):
    def test_valid_report_passes_with_no_errors(self) -> None:
        result = ReportValidator.validate(_valid_report())
        self.assertEqual(result, {"valid": True, "errors": []})

    def test_valid_is_true_iff_no_errors(self) -> None:
        result = ReportValidator.validate(_valid_report())
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

        bad = _valid_report()
        bad["decision"] = "maybe"
        result = ReportValidator.validate(bad)
        self.assertFalse(result["valid"])
        self.assertTrue(result["errors"])

    def test_missing_each_required_key_is_reported(self) -> None:
        for key in ("overall", "decision", "top_issues"):
            report = _valid_report()
            del report[key]
            result = ReportValidator.validate(report)
            self.assertFalse(result["valid"])
            self.assertIn(f"missing required key: {key!r}", result["errors"])

    def test_empty_report_reports_all_required_keys(self) -> None:
        result = ReportValidator.validate({})
        self.assertFalse(result["valid"])
        # Exactly one "missing required key" error per required key, nothing else.
        self.assertEqual(len(result["errors"]), 3)
        for key in ("overall", "decision", "top_issues"):
            self.assertIn(f"missing required key: {key!r}", result["errors"])

    def test_invalid_top_level_decision(self) -> None:
        report = _valid_report()
        report["decision"] = "ship_it"
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("decision 'ship_it'" in e for e in result["errors"]))

    def test_invalid_overall_decision(self) -> None:
        report = _valid_report()
        report["overall"]["decision"] = "unsure"
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("overall.decision 'unsure'" in e for e in result["errors"]))

    def test_unknown_category_key(self) -> None:
        report = _valid_report()
        report["metrics"]["speed"] = {"score": 5.0, "criteria": []}
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("category key 'speed'" in e for e in result["errors"]))

    def test_all_known_category_keys_accepted(self) -> None:
        report = _valid_report()
        report["metrics"]["operational"] = {"score": 7.0, "criteria": []}
        result = ReportValidator.validate(report)
        self.assertEqual(result, {"valid": True, "errors": []})

    def test_criterion_score_out_of_range(self) -> None:
        for bad_score in (0, 6, -1, 10):
            report = _valid_report()
            report["metrics"]["quality"]["criteria"][0]["score"] = bad_score
            result = ReportValidator.validate(report)
            self.assertFalse(result["valid"], bad_score)
            self.assertTrue(
                any("criterion 'relevance'" in e for e in result["errors"]), bad_score
            )

    def test_criterion_score_boundaries_are_inclusive(self) -> None:
        for good_score in (
            constants.CRITERION_MIN_SCORE,
            constants.CRITERION_MAX_SCORE,
        ):
            report = _valid_report()
            report["metrics"]["quality"]["criteria"][0]["score"] = good_score
            result = ReportValidator.validate(report)
            self.assertTrue(result["valid"], good_score)

    def test_criterion_score_float_is_rejected(self) -> None:
        report = _valid_report()
        report["metrics"]["quality"]["criteria"][0]["score"] = 4.0
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("criterion 'relevance'" in e for e in result["errors"]))

    def test_criterion_score_bool_is_rejected(self) -> None:
        report = _valid_report()
        report["metrics"]["quality"]["criteria"][0]["score"] = True
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("criterion 'relevance'" in e for e in result["errors"]))

    def test_criterion_score_none_is_allowed(self) -> None:
        report = _valid_report()
        report["metrics"]["quality"]["criteria"][0]["score"] = None
        result = ReportValidator.validate(report)
        self.assertEqual(result, {"valid": True, "errors": []})

    def test_criterion_without_id_uses_unknown_label(self) -> None:
        report = _valid_report()
        report["metrics"]["quality"]["criteria"][0] = {"name": "x", "score": 9, "evidence": "."}
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("criterion 'unknown'" in e for e in result["errors"]))

    def test_invalid_top_issue_severity(self) -> None:
        report = _valid_report()
        report["top_issues"][0]["severity"] = "blocker"
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("severity 'blocker'" in e for e in result["errors"]))

    def test_missing_top_issue_severity_is_invalid(self) -> None:
        report = _valid_report()
        report["top_issues"][0] = {"description": "no severity"}
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("severity None" in e for e in result["errors"]))

    def test_all_known_severities_accepted(self) -> None:
        for severity in constants.SEVERITIES:
            report = _valid_report()
            report["top_issues"][0]["severity"] = severity
            result = ReportValidator.validate(report)
            self.assertTrue(result["valid"], severity)

    def test_overall_score_out_of_range(self) -> None:
        for bad_score in (-0.1, 10.1, constants.PERFECT_SCORE + 1):
            report = _valid_report()
            report["overall"]["score"] = bad_score
            result = ReportValidator.validate(report)
            self.assertFalse(result["valid"], bad_score)
            self.assertTrue(any(e.startswith("overall score") for e in result["errors"]), bad_score)

    def test_overall_score_boundaries_and_none_allowed(self) -> None:
        for good_score in (0, constants.PERFECT_SCORE, None):
            report = _valid_report()
            report["overall"]["score"] = good_score
            result = ReportValidator.validate(report)
            self.assertTrue(result["valid"], good_score)

    def test_category_score_out_of_range(self) -> None:
        report = _valid_report()
        report["metrics"]["quality"]["score"] = 11.0
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("category 'quality' score" in e for e in result["errors"]))

    def test_category_score_none_is_allowed(self) -> None:
        report = _valid_report()
        report["metrics"]["quality"]["score"] = None
        result = ReportValidator.validate(report)
        self.assertEqual(result, {"valid": True, "errors": []})

    def test_score_bool_is_rejected_for_aggregate(self) -> None:
        report = _valid_report()
        report["metrics"]["quality"]["score"] = True
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("category 'quality' score" in e for e in result["errors"]))

    def test_non_mapping_report_is_invalid_not_raised(self) -> None:
        result = ReportValidator.validate(["not", "a", "mapping"])
        self.assertEqual(result, {"valid": False, "errors": ["report must be a mapping"]})

    def test_overall_not_a_mapping(self) -> None:
        report = _valid_report()
        report["overall"] = "pass"
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertIn("overall must be a mapping", result["errors"])

    def test_metrics_layer_not_a_mapping(self) -> None:
        report = _valid_report()
        report["metrics"] = ["quality", "operational"]
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertIn("metrics must be a mapping", result["errors"])

    def test_category_value_not_a_mapping(self) -> None:
        report = _valid_report()
        report["metrics"]["quality"] = "great"
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertIn("category 'quality' must be a mapping", result["errors"])

    def test_top_issues_not_a_list(self) -> None:
        report = _valid_report()
        report["top_issues"] = {"severity": "minor"}
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertIn("top_issues must be a list", result["errors"])

    def test_top_issue_not_a_mapping(self) -> None:
        report = _valid_report()
        report["top_issues"] = ["oops"]
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("must be a mapping" in e for e in result["errors"]))

    def test_accumulates_multiple_errors(self) -> None:
        report = _valid_report()
        report["decision"] = "bad"
        report["metrics"]["speed"] = {"score": 5.0, "criteria": []}
        report["metrics"]["quality"]["criteria"][0]["score"] = 99
        report["top_issues"][0]["severity"] = "urgent"
        result = ReportValidator.validate(report)
        self.assertFalse(result["valid"])
        self.assertGreaterEqual(len(result["errors"]), 4)

    def test_input_report_is_not_mutated(self) -> None:
        report = _valid_report()
        report["decision"] = "bad"
        snapshot = copy.deepcopy(report)
        ReportValidator.validate(report)
        self.assertEqual(report, snapshot)

    def test_result_is_deterministic(self) -> None:
        report = _valid_report()
        report["metrics"]["quality"]["criteria"][0]["score"] = 42
        self.assertEqual(
            ReportValidator.validate(report), ReportValidator.validate(report)
        )

    def test_tolerates_malformed_criteria_container(self) -> None:
        report = _valid_report()
        report["metrics"]["quality"]["criteria"] = "not a list"
        # Traversal is delegated to ScoringModel; malformed criteria are skipped.
        result = ReportValidator.validate(report)
        self.assertTrue(result["valid"])

    def test_validation_result_to_dict_shape(self) -> None:
        as_dict = ValidationResult(True, ()).to_dict()
        self.assertEqual(as_dict, {"valid": True, "errors": []})


class GateTest(unittest.TestCase):
    def test_pass_meets_pass_minimum(self) -> None:
        result = Gate.evaluate({"decision": constants.DECISION_PASS}, constants.DECISION_PASS)
        self.assertTrue(result["passed"])
        self.assertEqual(result["decision"], constants.DECISION_PASS)
        self.assertEqual(result["minimum"], constants.DECISION_PASS)

    def test_pass_with_fixes_below_pass_minimum(self) -> None:
        result = Gate.evaluate(
            {"decision": constants.DECISION_PASS_WITH_FIXES}, constants.DECISION_PASS
        )
        self.assertFalse(result["passed"])

    def test_pass_with_fixes_meets_its_own_minimum(self) -> None:
        result = Gate.evaluate(
            {"decision": constants.DECISION_PASS_WITH_FIXES},
            constants.DECISION_PASS_WITH_FIXES,
        )
        self.assertTrue(result["passed"])

    def test_fail_below_pass_with_fixes(self) -> None:
        result = Gate.evaluate(
            {"decision": constants.DECISION_FAIL}, constants.DECISION_PASS_WITH_FIXES
        )
        self.assertFalse(result["passed"])

    def test_fail_meets_fail_minimum(self) -> None:
        result = Gate.evaluate({"decision": constants.DECISION_FAIL}, constants.DECISION_FAIL)
        self.assertTrue(result["passed"])

    def test_pass_clears_fail_minimum(self) -> None:
        result = Gate.evaluate({"decision": constants.DECISION_PASS}, constants.DECISION_FAIL)
        self.assertTrue(result["passed"])

    def test_result_shape_and_reason(self) -> None:
        result = Gate.evaluate({"decision": constants.DECISION_PASS}, constants.DECISION_PASS)
        self.assertEqual(set(result), {"passed", "decision", "minimum", "reason"})
        self.assertIn(constants.DECISION_PASS, result["reason"])

    def test_reason_explains_pass_and_fail(self) -> None:
        cleared = Gate.evaluate({"decision": constants.DECISION_PASS}, constants.DECISION_FAIL)
        self.assertIn("meets or exceeds", cleared["reason"])
        blocked = Gate.evaluate(
            {"decision": constants.DECISION_FAIL}, constants.DECISION_PASS
        )
        self.assertIn("is below", blocked["reason"])

    def test_invalid_minimum_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            Gate.evaluate({"decision": constants.DECISION_PASS}, "excellent")

    def test_unknown_report_decision_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            Gate.evaluate({"decision": "maybe"}, constants.DECISION_PASS)

    def test_missing_report_decision_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            Gate.evaluate({}, constants.DECISION_PASS)

    def test_non_mapping_report_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            Gate.evaluate("pass", constants.DECISION_PASS)

    def test_uses_decision_rank_ordering(self) -> None:
        # Every decision clears the lowest bar; only pass clears the highest.
        for decision in constants.DECISIONS:
            self.assertTrue(
                Gate.evaluate({"decision": decision}, constants.DECISION_FAIL)["passed"]
            )
        self.assertTrue(
            Gate.evaluate({"decision": constants.DECISION_PASS}, constants.DECISION_PASS)[
                "passed"
            ]
        )
        self.assertFalse(
            Gate.evaluate(
                {"decision": constants.DECISION_PASS_WITH_FIXES}, constants.DECISION_PASS
            )["passed"]
        )

    def test_input_report_is_not_mutated(self) -> None:
        report = {"decision": constants.DECISION_PASS_WITH_FIXES}
        snapshot = copy.deepcopy(report)
        Gate.evaluate(report, constants.DECISION_PASS)
        self.assertEqual(report, snapshot)

    def test_result_is_deterministic(self) -> None:
        report = {"decision": constants.DECISION_PASS_WITH_FIXES}
        self.assertEqual(
            Gate.evaluate(report, constants.DECISION_PASS),
            Gate.evaluate(report, constants.DECISION_PASS),
        )

    def test_gate_result_to_dict_shape(self) -> None:
        as_dict = GateResult(True, "pass", "pass", "why").to_dict()
        self.assertEqual(
            as_dict,
            {"passed": True, "decision": "pass", "minimum": "pass", "reason": "why"},
        )


if __name__ == "__main__":
    unittest.main()
