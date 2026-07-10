from __future__ import annotations

import copy
import unittest
from statistics import pvariance

import evalsurfer.constants as constants
from evalsurfer.analysis.calibration import CalibrationCase, Calibrator
from evalsurfer.core.planner import Signals


def _base_case_kwargs() -> dict:
    """Return kwargs for a valid, representative calibration case."""
    return {
        "name": "agent_case",
        "signals": Signals(answer=True),
        "expected_applicable_pillars": frozenset({"quality", "safety"}),
        "expected_score_ranges": {
            "correctness_accuracy": (3, 5),
            "relevance": (2, 4),
        },
        "expected_decision": "pass_with_fixes",
        "expected_top_issue_severity": "major",
        "expected_safety_escalation": False,
    }


def _matching_report() -> dict:
    """Build a judge report that satisfies every expectation of the base case."""
    return {
        "decision": "pass_with_fixes",
        "overall": {"score": 7.5, "decision": "pass_with_fixes"},
        "pillars": {
            "quality": {
                "score": 7.0,
                "criteria": [
                    {"id": "correctness_accuracy", "score": 4},
                    {"id": "relevance", "score": 3},
                ],
            },
            "safety": {
                "score": 8.0,
                "criteria": [{"id": "toxicity", "score": 4}],
            },
        },
        "top_issues": [
            {
                "severity": "major",
                "description": "missing a caveat",
                "criterion_id": "relevance",
            }
        ],
    }


def _run(decision, overall_score=None) -> dict:
    """Build a minimal judge report carrying only a decision and overall score."""
    report = {"decision": decision}
    if overall_score is not None:
        report["overall"] = {"score": overall_score, "decision": decision}
    return report


class CheckReportTest(unittest.TestCase):
    def test_full_agreement(self) -> None:
        result = Calibrator.check_report(
            CalibrationCase(**_base_case_kwargs()), _matching_report()
        )
        self.assertTrue(result["agreement"])
        self.assertTrue(result["plan_match"])
        self.assertTrue(result["decision_match"])
        self.assertTrue(result["top_issue_match"])
        self.assertTrue(result["safety_escalation_match"])
        self.assertTrue(result["scores_within_range"])
        self.assertEqual(
            result["per_criterion"],
            {"correctness_accuracy": True, "relevance": True},
        )

    def test_result_shape(self) -> None:
        result = Calibrator.check_report(
            CalibrationCase(**_base_case_kwargs()), _matching_report()
        )
        self.assertEqual(
            set(result),
            {
                "plan_match",
                "per_criterion",
                "scores_within_range",
                "decision_match",
                "top_issue_match",
                "safety_escalation_match",
                "agreement",
            },
        )
        self.assertIsInstance(result["agreement"], bool)
        self.assertIsInstance(result["per_criterion"], dict)

    def test_plan_match_derives_from_signals_not_report(self) -> None:
        kwargs = _base_case_kwargs()
        kwargs["expected_applicable_pillars"] = frozenset({"operational"})
        result = Calibrator.check_report(CalibrationCase(**kwargs), _matching_report())
        self.assertFalse(result["plan_match"])
        self.assertFalse(result["agreement"])

    def test_score_out_of_range_does_not_break_agreement(self) -> None:
        # The four categorical matches still hold, so agreement is True even
        # though a criterion score fell outside its expected band.
        report = _matching_report()
        report["pillars"]["quality"]["criteria"][0]["score"] = 1
        result = Calibrator.check_report(CalibrationCase(**_base_case_kwargs()), report)
        self.assertFalse(result["per_criterion"]["correctness_accuracy"])
        self.assertTrue(result["per_criterion"]["relevance"])
        self.assertFalse(result["scores_within_range"])
        self.assertTrue(result["agreement"])

    def test_missing_judged_score_is_out_of_range(self) -> None:
        report = _matching_report()
        report["pillars"]["quality"]["criteria"] = [
            {"id": "correctness_accuracy", "score": 4}
        ]
        result = Calibrator.check_report(CalibrationCase(**_base_case_kwargs()), report)
        self.assertFalse(result["per_criterion"]["relevance"])
        self.assertFalse(result["scores_within_range"])

    def test_range_bounds_are_inclusive(self) -> None:
        kwargs = _base_case_kwargs()
        kwargs["expected_score_ranges"] = {"correctness_accuracy": (3, 5)}
        for score in (3, 5):
            report = _matching_report()
            report["pillars"]["quality"]["criteria"][0]["score"] = score
            result = Calibrator.check_report(CalibrationCase(**kwargs), report)
            self.assertTrue(result["per_criterion"]["correctness_accuracy"])

    def test_boolean_score_is_not_within_range(self) -> None:
        report = _matching_report()
        report["pillars"]["quality"]["criteria"][0]["score"] = True
        result = Calibrator.check_report(CalibrationCase(**_base_case_kwargs()), report)
        self.assertFalse(result["per_criterion"]["correctness_accuracy"])

    def test_empty_expected_ranges_are_vacuously_within_range(self) -> None:
        kwargs = _base_case_kwargs()
        kwargs["expected_score_ranges"] = {}
        result = Calibrator.check_report(CalibrationCase(**kwargs), _matching_report())
        self.assertEqual(result["per_criterion"], {})
        self.assertTrue(result["scores_within_range"])

    def test_decision_mismatch(self) -> None:
        report = _matching_report()
        report["decision"] = "fail"
        result = Calibrator.check_report(CalibrationCase(**_base_case_kwargs()), report)
        self.assertFalse(result["decision_match"])
        self.assertFalse(result["agreement"])

    def test_top_issue_uses_highest_severity(self) -> None:
        kwargs = _base_case_kwargs()
        kwargs["expected_top_issue_severity"] = "critical"
        report = _matching_report()
        report["top_issues"] = [
            {"severity": "minor", "description": "typo"},
            {
                "severity": "critical",
                "description": "wrong answer",
                "criterion_id": "correctness_accuracy",
            },
            {"severity": "major", "description": "missing caveat"},
        ]
        result = Calibrator.check_report(CalibrationCase(**kwargs), report)
        self.assertTrue(result["top_issue_match"])
        # The critical issue is on a quality criterion, so it is NOT a safety
        # escalation and the (False) expectation still matches.
        self.assertTrue(result["safety_escalation_match"])
        self.assertTrue(result["agreement"])

    def test_no_top_issues_matches_none_expectation(self) -> None:
        kwargs = _base_case_kwargs()
        kwargs["expected_top_issue_severity"] = None
        for report in (_matching_report(), _matching_report()):
            report["top_issues"] = []
            result = Calibrator.check_report(CalibrationCase(**kwargs), report)
            self.assertTrue(result["top_issue_match"])
        # Also matches when the section is absent entirely.
        report = _matching_report()
        del report["top_issues"]
        result = Calibrator.check_report(CalibrationCase(**kwargs), report)
        self.assertTrue(result["top_issue_match"])

    def test_critical_safety_issue_is_an_escalation(self) -> None:
        kwargs = _base_case_kwargs()
        kwargs["expected_top_issue_severity"] = "critical"
        kwargs["expected_safety_escalation"] = True
        report = _matching_report()
        report["top_issues"] = [
            {
                "severity": "critical",
                "description": "PII leaked in the answer",
                "criterion_id": "pii_leakage",
            }
        ]
        result = Calibrator.check_report(CalibrationCase(**kwargs), report)
        self.assertTrue(result["safety_escalation_match"])
        self.assertTrue(result["top_issue_match"])
        self.assertTrue(result["agreement"])

    def test_critical_non_safety_issue_is_not_an_escalation(self) -> None:
        kwargs = _base_case_kwargs()
        kwargs["expected_top_issue_severity"] = "critical"
        kwargs["expected_safety_escalation"] = True  # but the issue is not safety
        report = _matching_report()
        report["top_issues"] = [
            {
                "severity": "critical",
                "description": "task not completed",
                "criterion_id": "task_completion",
            }
        ]
        result = Calibrator.check_report(CalibrationCase(**kwargs), report)
        self.assertFalse(result["safety_escalation_match"])
        self.assertFalse(result["agreement"])

    def test_expected_safety_escalation_missing_is_mismatch(self) -> None:
        kwargs = _base_case_kwargs()
        kwargs["expected_safety_escalation"] = True
        # The base report's worst issue is only major, so no critical safety.
        result = Calibrator.check_report(
            CalibrationCase(**kwargs), _matching_report()
        )
        self.assertFalse(result["safety_escalation_match"])
        self.assertFalse(result["agreement"])

    def test_empty_report(self) -> None:
        result = Calibrator.check_report(CalibrationCase(**_base_case_kwargs()), {})
        # Plan is derived from the case signals, so it still matches.
        self.assertTrue(result["plan_match"])
        self.assertEqual(
            result["per_criterion"],
            {"correctness_accuracy": False, "relevance": False},
        )
        self.assertFalse(result["scores_within_range"])
        self.assertFalse(result["decision_match"])
        self.assertFalse(result["top_issue_match"])
        # No critical safety issue and the case did not expect one.
        self.assertTrue(result["safety_escalation_match"])
        self.assertFalse(result["agreement"])

    def test_tolerates_malformed_top_issues(self) -> None:
        kwargs = _base_case_kwargs()
        kwargs["expected_top_issue_severity"] = "critical"
        report = _matching_report()
        report["top_issues"] = [
            "not a mapping",
            {"severity": "unknown"},
            {"severity": "critical", "criterion_id": "harmful_content"},
        ]
        result = Calibrator.check_report(CalibrationCase(**kwargs), report)
        self.assertTrue(result["top_issue_match"])

    def test_top_issues_not_a_list_is_treated_as_none(self) -> None:
        kwargs = _base_case_kwargs()
        kwargs["expected_top_issue_severity"] = None
        report = _matching_report()
        report["top_issues"] = None
        result = Calibrator.check_report(CalibrationCase(**kwargs), report)
        self.assertTrue(result["top_issue_match"])

    def test_does_not_mutate_report(self) -> None:
        case = CalibrationCase(**_base_case_kwargs())
        report = _matching_report()
        snapshot = copy.deepcopy(report)
        Calibrator.check_report(case, report)
        self.assertEqual(report, snapshot)

    def test_is_deterministic(self) -> None:
        case = CalibrationCase(**_base_case_kwargs())
        report = _matching_report()
        self.assertEqual(
            Calibrator.check_report(case, report),
            Calibrator.check_report(case, report),
        )

    def test_rejects_non_case(self) -> None:
        with self.assertRaises(TypeError):
            Calibrator.check_report({"name": "x"}, {})

    def test_rejects_non_mapping_report(self) -> None:
        with self.assertRaises(TypeError):
            Calibrator.check_report(
                CalibrationCase(**_base_case_kwargs()), ["not", "a", "map"]
            )


class SummarizeTest(unittest.TestCase):
    def test_agreement_fraction(self) -> None:
        case = CalibrationCase(**{**_base_case_kwargs(), "expected_decision": "pass"})
        reports = [_run("pass", 9.0), _run("fail", 5.0), _run("pass", 8.5)]
        summary = Calibrator.summarize(case, reports)
        self.assertEqual(summary["runs"], 3)
        self.assertEqual(summary["agreement"], round(2 / 3, constants.SHARE_PRECISION))

    def test_summary_keys_match_metrics_constant(self) -> None:
        case = CalibrationCase(**_base_case_kwargs())
        summary = Calibrator.summarize(case, [_run("pass", 8.0)])
        self.assertEqual(set(summary), {"name", "runs", *constants.CALIBRATION_METRICS})
        self.assertEqual(summary["name"], "agent_case")

    def test_false_pass_rate_when_expected_fail(self) -> None:
        case = CalibrationCase(**{**_base_case_kwargs(), "expected_decision": "fail"})
        reports = [
            _run("fail", 5.0),
            _run("pass", 9.0),
            _run("pass_with_fixes", 7.0),
            _run("fail", 6.0),
        ]
        summary = Calibrator.summarize(case, reports)
        self.assertEqual(summary["agreement"], 0.5)
        self.assertEqual(summary["false_pass_rate"], 0.5)
        # A false-fail cannot occur when the case expects a fail.
        self.assertEqual(summary["false_fail_rate"], 0.0)

    def test_false_fail_rate_when_expected_pass(self) -> None:
        for expected in ("pass", "pass_with_fixes"):
            case = CalibrationCase(
                **{**_base_case_kwargs(), "expected_decision": expected}
            )
            reports = [_run("pass", 9.0), _run("fail", 5.0), _run("fail", 4.0)]
            summary = Calibrator.summarize(case, reports)
            self.assertEqual(
                summary["false_fail_rate"], round(2 / 3, constants.SHARE_PRECISION)
            )
            # A false-pass cannot occur when the case expects a (conditional) pass.
            self.assertEqual(summary["false_pass_rate"], 0.0)

    def test_score_variance_simple(self) -> None:
        case = CalibrationCase(**{**_base_case_kwargs(), "expected_decision": "pass"})
        summary = Calibrator.summarize(case, [_run("pass", 8.0), _run("pass", 9.0)])
        self.assertEqual(summary["score_variance"], 0.25)

    def test_score_variance_matches_pvariance(self) -> None:
        case = CalibrationCase(**{**_base_case_kwargs(), "expected_decision": "pass"})
        reports = [_run("pass", 8.0), _run("fail", 5.0), _run("pass", 8.5)]
        summary = Calibrator.summarize(case, reports)
        self.assertEqual(
            summary["score_variance"],
            round(pvariance([8.0, 5.0, 8.5]), constants.SHARE_PRECISION),
        )

    def test_score_variance_needs_two_scores(self) -> None:
        case = CalibrationCase(**{**_base_case_kwargs(), "expected_decision": "pass"})
        self.assertEqual(
            Calibrator.summarize(case, [_run("pass", 8.0)])["score_variance"], 0.0
        )
        # A report missing an overall score is excluded, leaving fewer than two.
        self.assertEqual(
            Calibrator.summarize(case, [_run("pass", 8.0), _run("pass")])[
                "score_variance"
            ],
            0.0,
        )

    def test_empty_reports_yield_zeroed_metrics(self) -> None:
        case = CalibrationCase(**_base_case_kwargs())
        summary = Calibrator.summarize(case, [])
        self.assertEqual(summary["runs"], 0)
        self.assertEqual(summary["agreement"], 0.0)
        self.assertEqual(summary["false_pass_rate"], 0.0)
        self.assertEqual(summary["false_fail_rate"], 0.0)
        self.assertEqual(summary["score_variance"], 0.0)

    def test_decision_read_from_top_level_field(self) -> None:
        # Only overall.decision is present; the top-level decision drives the
        # metric, so agreement stays at zero.
        case = CalibrationCase(**{**_base_case_kwargs(), "expected_decision": "pass"})
        reports = [{"overall": {"score": 9.0, "decision": "pass"}}]
        summary = Calibrator.summarize(case, reports)
        self.assertEqual(summary["agreement"], 0.0)

    def test_does_not_mutate_reports(self) -> None:
        case = CalibrationCase(**_base_case_kwargs())
        reports = [_run("pass", 8.0), _run("fail", 5.0)]
        snapshot = copy.deepcopy(reports)
        Calibrator.summarize(case, reports)
        self.assertEqual(reports, snapshot)

    def test_rejects_non_case(self) -> None:
        with self.assertRaises(TypeError):
            Calibrator.summarize({"name": "x"}, [])

    def test_rejects_non_sequence(self) -> None:
        case = CalibrationCase(**_base_case_kwargs())
        with self.assertRaises(TypeError):
            Calibrator.summarize(case, 5)

    def test_rejects_string_sequence(self) -> None:
        case = CalibrationCase(**_base_case_kwargs())
        with self.assertRaises(TypeError):
            Calibrator.summarize(case, "not a list of reports")

    def test_rejects_non_mapping_entry(self) -> None:
        case = CalibrationCase(**_base_case_kwargs())
        with self.assertRaises(TypeError):
            Calibrator.summarize(case, [{"decision": "pass"}, "bad"])


class CalibrationCaseValidationTest(unittest.TestCase):
    def test_valid_case_constructs(self) -> None:
        self.assertIsInstance(
            CalibrationCase(**_base_case_kwargs()), CalibrationCase
        )

    def test_blank_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CalibrationCase(**{**_base_case_kwargs(), "name": "   "})

    def test_non_signals_rejected(self) -> None:
        with self.assertRaises(TypeError):
            CalibrationCase(**{**_base_case_kwargs(), "signals": {"answer": True}})

    def test_non_frozenset_pillars_rejected(self) -> None:
        with self.assertRaises(TypeError):
            CalibrationCase(
                **{**_base_case_kwargs(), "expected_applicable_pillars": {"quality"}}
            )

    def test_unknown_pillar_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CalibrationCase(
                **{
                    **_base_case_kwargs(),
                    "expected_applicable_pillars": frozenset({"speed"}),
                }
            )

    def test_score_range_not_tuple_rejected(self) -> None:
        with self.assertRaises(TypeError):
            CalibrationCase(
                **{**_base_case_kwargs(), "expected_score_ranges": {"relevance": [2, 4]}}
            )

    def test_score_range_wrong_length_rejected(self) -> None:
        with self.assertRaises(TypeError):
            CalibrationCase(
                **{**_base_case_kwargs(), "expected_score_ranges": {"relevance": (2,)}}
            )

    def test_score_range_out_of_scale_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CalibrationCase(
                **{**_base_case_kwargs(), "expected_score_ranges": {"relevance": (1, 7)}}
            )

    def test_score_range_min_greater_than_max_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CalibrationCase(
                **{**_base_case_kwargs(), "expected_score_ranges": {"relevance": (5, 3)}}
            )

    def test_score_range_bool_bound_rejected(self) -> None:
        with self.assertRaises(TypeError):
            CalibrationCase(
                **{
                    **_base_case_kwargs(),
                    "expected_score_ranges": {"relevance": (True, 5)},
                }
            )

    def test_invalid_decision_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CalibrationCase(**{**_base_case_kwargs(), "expected_decision": "maybe"})

    def test_invalid_severity_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CalibrationCase(
                **{**_base_case_kwargs(), "expected_top_issue_severity": "huge"}
            )

    def test_none_severity_allowed(self) -> None:
        case = CalibrationCase(
            **{**_base_case_kwargs(), "expected_top_issue_severity": None}
        )
        self.assertIsNone(case.expected_top_issue_severity)

    def test_non_bool_escalation_rejected(self) -> None:
        with self.assertRaises(TypeError):
            CalibrationCase(
                **{**_base_case_kwargs(), "expected_safety_escalation": "yes"}
            )

    def test_empty_score_ranges_allowed(self) -> None:
        case = CalibrationCase(**{**_base_case_kwargs(), "expected_score_ranges": {}})
        self.assertEqual(dict(case.expected_score_ranges), {})


class PublicApiTest(unittest.TestCase):
    def test_calibration_metrics_constant(self) -> None:
        self.assertEqual(
            constants.CALIBRATION_METRICS,
            ("agreement", "false_pass_rate", "false_fail_rate", "score_variance"),
        )

    def test_exposes_callables(self) -> None:
        self.assertTrue(callable(Calibrator.check_report))
        self.assertTrue(callable(Calibrator.summarize))

    def test_importable_from_package(self) -> None:
        from evalsurfer.analysis.calibration import CalibrationCase as CaseAlias
        from evalsurfer.analysis.calibration import Calibrator as CalibratorAlias

        self.assertIs(CaseAlias, CalibrationCase)
        self.assertIs(CalibratorAlias, Calibrator)


if __name__ == "__main__":
    unittest.main()
