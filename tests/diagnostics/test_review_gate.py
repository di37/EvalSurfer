from __future__ import annotations

import copy
import unittest

import evalsurfer.constants as constants
from evalsurfer.diagnostics.review_gate import ReviewGate


def _report(criteria_by_pillar=None, top_issues=None):
    """Build a minimal report with the given pillar criteria and top issues."""

    pillars = {}
    for pillar_id, criteria in (criteria_by_pillar or {}).items():
        pillars[pillar_id] = {"score": None, "criteria": list(criteria)}
    report = {"pillars": pillars}
    if top_issues is not None:
        report["top_issues"] = list(top_issues)
    return report


class ReviewGateTest(unittest.TestCase):
    def test_flags_criterion_below_threshold(self) -> None:
        report = _report(
            {
                "quality": [
                    {"id": "relevance", "score": 4, "confidence": 0.55},
                    {"id": "completeness", "score": 5, "confidence": 0.95},
                ]
            }
        )
        result = ReviewGate().evaluate(report)
        self.assertTrue(result["needs_human_review"])
        self.assertEqual(result["low_confidence_count"], 1)
        self.assertEqual(
            result["flagged_criteria"],
            [{"id": "relevance", "confidence": 0.55}],
        )
        self.assertEqual(len(result["reasons"]), 1)
        self.assertIn("relevance", result["reasons"][0])
        self.assertIn("0.550", result["reasons"][0])

    def test_reads_confidence_from_evidence_mapping(self) -> None:
        report = _report(
            {
                "safety": [
                    {
                        "id": "toxicity",
                        "score": 3,
                        "evidence": {"confidence": 0.4, "quote": "..."},
                    }
                ]
            }
        )
        result = ReviewGate().evaluate(report)
        self.assertTrue(result["needs_human_review"])
        self.assertEqual(
            result["flagged_criteria"], [{"id": "toxicity", "confidence": 0.4}]
        )

    def test_direct_confidence_takes_precedence_over_evidence(self) -> None:
        report = _report(
            {
                "quality": [
                    {
                        "id": "correctness_accuracy",
                        "confidence": 0.9,
                        "evidence": {"confidence": 0.1},
                    }
                ]
            }
        )
        result = ReviewGate().evaluate(report)
        # Direct 0.9 is above threshold, so evidence's 0.1 must be ignored.
        self.assertFalse(result["needs_human_review"])
        self.assertEqual(result["flagged_criteria"], [])

    def test_criteria_without_confidence_are_skipped(self) -> None:
        report = _report(
            {
                "quality": [
                    {"id": "relevance", "score": 2, "evidence": "a plain string"},
                    {"id": "completeness", "score": None},
                ]
            }
        )
        result = ReviewGate().evaluate(report)
        self.assertFalse(result["needs_human_review"])
        self.assertEqual(result["low_confidence_count"], 0)
        self.assertEqual(result["reasons"], [])

    def test_confidence_equal_to_threshold_is_not_flagged(self) -> None:
        report = _report({"quality": [{"id": "relevance", "confidence": 0.7}]})
        result = ReviewGate(confidence_threshold=0.7).evaluate(report)
        self.assertFalse(result["needs_human_review"])
        self.assertEqual(result["flagged_criteria"], [])

    def test_zero_confidence_is_flagged(self) -> None:
        report = _report({"quality": [{"id": "relevance", "confidence": 0.0}]})
        result = ReviewGate().evaluate(report)
        self.assertTrue(result["needs_human_review"])
        self.assertEqual(
            result["flagged_criteria"], [{"id": "relevance", "confidence": 0.0}]
        )

    def test_confidence_is_rounded_to_three_decimals(self) -> None:
        report = _report({"quality": [{"id": "relevance", "confidence": 0.123456}]})
        result = ReviewGate().evaluate(report)
        self.assertEqual(
            result["flagged_criteria"], [{"id": "relevance", "confidence": 0.123}]
        )

    def test_critical_issue_triggers_review_without_low_confidence(self) -> None:
        report = _report(
            {"quality": [{"id": "relevance", "confidence": 0.99}]},
            top_issues=[
                {
                    "severity": "critical",
                    "description": "PII leaked in the answer",
                    "criterion_id": "pii_leakage",
                },
                {"severity": "minor", "description": "slightly verbose"},
            ],
        )
        result = ReviewGate().evaluate(report)
        self.assertTrue(result["needs_human_review"])
        self.assertEqual(result["low_confidence_count"], 0)
        self.assertEqual(result["flagged_criteria"], [])
        self.assertEqual(len(result["reasons"]), 1)
        self.assertIn("pii_leakage", result["reasons"][0])
        self.assertIn("PII leaked in the answer", result["reasons"][0])

    def test_non_critical_issues_do_not_trigger_review(self) -> None:
        report = _report(
            {"quality": [{"id": "relevance", "confidence": 0.99}]},
            top_issues=[
                {"severity": "major", "description": "missing a caveat"},
                {"severity": "minor", "description": "typo"},
            ],
        )
        result = ReviewGate().evaluate(report)
        self.assertFalse(result["needs_human_review"])
        self.assertEqual(result["reasons"], [])

    def test_low_confidence_and_critical_issue_combine(self) -> None:
        report = _report(
            {
                "quality": [{"id": "relevance", "confidence": 0.3}],
                "safety": [{"id": "toxicity", "confidence": 0.6}],
            },
            top_issues=[{"severity": "critical", "description": "harmful content"}],
        )
        result = ReviewGate().evaluate(report)
        self.assertTrue(result["needs_human_review"])
        self.assertEqual(result["low_confidence_count"], 2)
        # Two low-confidence reasons plus one critical-issue reason, in order.
        self.assertEqual(len(result["reasons"]), 3)
        self.assertIn("harmful content", result["reasons"][-1])

    def test_custom_threshold_changes_flagging(self) -> None:
        report = _report({"quality": [{"id": "relevance", "confidence": 0.65}]})
        self.assertFalse(
            ReviewGate(confidence_threshold=0.5).evaluate(report)["needs_human_review"]
        )
        self.assertTrue(
            ReviewGate(confidence_threshold=0.8).evaluate(report)["needs_human_review"]
        )

    def test_empty_report_needs_no_review(self) -> None:
        result = ReviewGate().evaluate({})
        self.assertEqual(
            result,
            {
                "needs_human_review": False,
                "reasons": [],
                "flagged_criteria": [],
                "low_confidence_count": 0,
            },
        )

    def test_tolerates_missing_and_malformed_keys(self) -> None:
        # No pillars, top_issues is not a list, stray keys present.
        report = {"top_issues": None, "metadata": {"model": "x"}}
        result = ReviewGate().evaluate(report)
        self.assertFalse(result["needs_human_review"])
        self.assertEqual(result["flagged_criteria"], [])

    def test_missing_criterion_id_becomes_none(self) -> None:
        report = _report({"quality": [{"confidence": 0.2}]})
        result = ReviewGate().evaluate(report)
        self.assertEqual(
            result["flagged_criteria"], [{"id": None, "confidence": 0.2}]
        )
        self.assertIn("unknown criterion", result["reasons"][0])

    def test_boolean_and_string_confidence_are_ignored(self) -> None:
        report = _report(
            {
                "quality": [
                    {"id": "a", "confidence": True},
                    {"id": "b", "confidence": "0.1"},
                ]
            }
        )
        result = ReviewGate().evaluate(report)
        self.assertFalse(result["needs_human_review"])
        self.assertEqual(result["low_confidence_count"], 0)

    def test_input_report_is_not_mutated(self) -> None:
        report = _report(
            {"quality": [{"id": "relevance", "confidence": 0.2}]},
            top_issues=[{"severity": "critical", "description": "bad"}],
        )
        snapshot = copy.deepcopy(report)
        ReviewGate().evaluate(report)
        self.assertEqual(report, snapshot)

    def test_result_is_deterministic(self) -> None:
        report = _report(
            {"quality": [{"id": "relevance", "confidence": 0.2}]},
            top_issues=[{"severity": "critical", "description": "bad"}],
        )
        gate = ReviewGate()
        self.assertEqual(gate.evaluate(report), gate.evaluate(report))

    def test_default_threshold_constant(self) -> None:
        self.assertEqual(constants.DEFAULT_CONFIDENCE_THRESHOLD, 0.7)
        self.assertEqual(
            ReviewGate().confidence_threshold, constants.DEFAULT_CONFIDENCE_THRESHOLD
        )

    def test_invalid_threshold_type_raises(self) -> None:
        with self.assertRaises(TypeError):
            ReviewGate(confidence_threshold="high")
        with self.assertRaises(TypeError):
            ReviewGate(confidence_threshold=True)

    def test_out_of_range_threshold_raises(self) -> None:
        with self.assertRaises(ValueError):
            ReviewGate(confidence_threshold=1.5)
        with self.assertRaises(ValueError):
            ReviewGate(confidence_threshold=-0.1)

    def test_non_mapping_report_raises(self) -> None:
        with self.assertRaises(TypeError):
            ReviewGate().evaluate(["not", "a", "mapping"])


if __name__ == "__main__":
    unittest.main()
