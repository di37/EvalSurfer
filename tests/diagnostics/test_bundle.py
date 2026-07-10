from __future__ import annotations

import copy
import unittest

import evalsurfer.constants as constants
from evalsurfer.core.planner import Signals
from evalsurfer.diagnostics import DiagnosticsBundle
from evalsurfer.diagnostics.bundle import DiagnosticsBundle as BundleFromModule
from evalsurfer.diagnostics.explainability import Explainer
from evalsurfer.diagnostics.failure_map import FailureMap
from evalsurfer.diagnostics.maturity import MaturityClassifier
from evalsurfer.diagnostics.regression import RegressionDiffer
from evalsurfer.diagnostics.review_gate import ReviewGate
from evalsurfer.diagnostics.root_cause import RootCauseAnalyzer


def _crit(cid: str, name: str, score: int | None, **extra: object) -> dict:
    criterion = {"id": cid, "name": name, "score": score, "evidence": ""}
    criterion.update(extra)
    return criterion


# A report with imperfect, varied scores, a low-confidence criterion, and a
# critical issue -- enough to give each diagnostic something non-trivial to say.
REPORT = {
    "overall": {
        "score": 7.0,
        "decision": constants.DECISION_PASS_WITH_FIXES,
        "summary": "current",
    },
    "pillars": {
        constants.PILLAR_QUALITY: {
            "score": 6.0,
            "criteria": [
                _crit("correctness_accuracy", "Correctness / Accuracy", 3, confidence=0.4),
                _crit("relevance", "Relevance", 5),
                _crit("completeness", "Completeness", None),
            ],
        },
        constants.PILLAR_SAFETY: {
            "score": 8.0,
            "criteria": [_crit("pii_leakage", "PII Leakage", 4)],
        },
        constants.PILLAR_OPERATIONAL: {
            "score": 6.0,
            "criteria": [_crit("time_to_first_token", "Time to First Token", 3)],
        },
    },
    "decision": constants.DECISION_PASS_WITH_FIXES,
    "top_issues": [
        {
            "severity": constants.SEVERITY_CRITICAL,
            "description": "leak",
            "recommendation": "fix",
            "criterion_id": "pii_leakage",
        }
    ],
    "not_assessed": [],
    "coverage": {"applicable": 18, "assessed": 5, "score": 0.278, "missing": []},
    "metadata": {},
}

# An earlier report for the regression diff -- lower quality, same decision.
BEFORE = {
    "overall": {
        "score": 6.0,
        "decision": constants.DECISION_PASS_WITH_FIXES,
        "summary": "prior",
    },
    "pillars": {
        constants.PILLAR_QUALITY: {
            "score": 5.0,
            "criteria": [
                _crit("correctness_accuracy", "Correctness / Accuracy", 2),
                _crit("relevance", "Relevance", 4),
            ],
        },
        constants.PILLAR_SAFETY: {
            "score": 8.0,
            "criteria": [_crit("pii_leakage", "PII Leakage", 4)],
        },
        constants.PILLAR_OPERATIONAL: {
            "score": 6.0,
            "criteria": [_crit("time_to_first_token", "Time to First Token", 3)],
        },
    },
    "decision": constants.DECISION_PASS_WITH_FIXES,
    "coverage": {"applicable": 18, "assessed": 5, "score": 0.25, "missing": []},
}

SIGNALS = Signals(retrieved_context=True, tool_calls=True)


class BundleShapeTest(unittest.TestCase):
    def test_report_only_has_the_four_core_keys_in_order(self) -> None:
        result = DiagnosticsBundle.run(REPORT)
        self.assertEqual(
            list(result),
            ["explainability", "root_cause", "failure_map", "review_gate"],
        )

    def test_keys_are_always_a_subset_of_diagnostics_keys(self) -> None:
        for kwargs in ({}, {"signals": SIGNALS}, {"before": BEFORE},
                       {"signals": SIGNALS, "before": BEFORE}):
            result = DiagnosticsBundle.run(REPORT, **kwargs)
            self.assertTrue(set(result).issubset(set(constants.DIAGNOSTICS_KEYS)))

    def test_full_block_follows_diagnostics_keys_order(self) -> None:
        result = DiagnosticsBundle.run(REPORT, before=BEFORE, signals=SIGNALS)
        self.assertEqual(list(result), list(constants.DIAGNOSTICS_KEYS))

    def test_present_keys_preserve_canonical_order(self) -> None:
        # regression only (no signals): keys stay in DIAGNOSTICS_KEYS order.
        result = DiagnosticsBundle.run(REPORT, before=BEFORE)
        expected = [k for k in constants.DIAGNOSTICS_KEYS if k in result]
        self.assertEqual(list(result), expected)

    def test_package_and_module_export_the_same_class(self) -> None:
        self.assertIs(DiagnosticsBundle, BundleFromModule)


class ConditionalMembersTest(unittest.TestCase):
    def test_maturity_omitted_without_signals(self) -> None:
        self.assertNotIn("maturity", DiagnosticsBundle.run(REPORT))
        self.assertNotIn("maturity", DiagnosticsBundle.run(REPORT, before=BEFORE))

    def test_regression_omitted_without_before(self) -> None:
        self.assertNotIn("regression", DiagnosticsBundle.run(REPORT))
        self.assertNotIn("regression", DiagnosticsBundle.run(REPORT, signals=SIGNALS))

    def test_maturity_present_only_with_signals(self) -> None:
        result = DiagnosticsBundle.run(REPORT, signals=SIGNALS)
        self.assertIn("maturity", result)
        self.assertNotIn("regression", result)

    def test_regression_present_only_with_before(self) -> None:
        result = DiagnosticsBundle.run(REPORT, before=BEFORE)
        self.assertIn("regression", result)
        self.assertNotIn("maturity", result)

    def test_both_present_with_both_inputs(self) -> None:
        result = DiagnosticsBundle.run(REPORT, before=BEFORE, signals=SIGNALS)
        self.assertIn("maturity", result)
        self.assertIn("regression", result)


class DelegationTest(unittest.TestCase):
    """Each block entry must equal the underlying diagnostic's own output."""

    def test_core_entries_match_direct_calls(self) -> None:
        result = DiagnosticsBundle.run(REPORT)
        self.assertEqual(result["explainability"], Explainer.explain(REPORT))
        self.assertEqual(result["root_cause"], RootCauseAnalyzer.attribute(REPORT))
        self.assertEqual(result["failure_map"], FailureMap().render(REPORT))
        self.assertEqual(result["review_gate"], ReviewGate().evaluate(REPORT))

    def test_maturity_entry_matches_direct_call(self) -> None:
        result = DiagnosticsBundle.run(REPORT, signals=SIGNALS)
        self.assertEqual(result["maturity"], MaturityClassifier.classify(SIGNALS))

    def test_regression_entry_uses_before_then_report_order(self) -> None:
        # diff(before, after) -> the current report is the "after" side.
        result = DiagnosticsBundle.run(REPORT, before=BEFORE)
        self.assertEqual(result["regression"], RegressionDiffer.diff(BEFORE, REPORT))

    def test_regression_argument_order_is_not_reversed(self) -> None:
        forward = DiagnosticsBundle.run(REPORT, before=BEFORE)["regression"]
        reversed_diff = RegressionDiffer.diff(REPORT, BEFORE)
        # correctness_accuracy went 2 -> 3, so the forward diff is an improvement,
        # while the reversed diff would be a regression: they must differ.
        self.assertNotEqual(forward, reversed_diff)
        self.assertIn("correctness_accuracy", forward["improvements"])

    def test_review_gate_reflects_low_confidence_and_critical_issue(self) -> None:
        # Delegation sanity: the wired-in review gate must escalate this report.
        self.assertTrue(DiagnosticsBundle.run(REPORT)["review_gate"]["needs_human_review"])


class EdgeCaseTest(unittest.TestCase):
    def test_empty_report_still_runs_the_core_four(self) -> None:
        result = DiagnosticsBundle.run({})
        self.assertEqual(
            list(result),
            ["explainability", "root_cause", "failure_map", "review_gate"],
        )
        self.assertEqual(result["root_cause"]["total_lost"], 0)

    def test_empty_signals_yield_a_maturity_entry(self) -> None:
        result = DiagnosticsBundle.run({}, signals=Signals())
        self.assertEqual(result["maturity"], MaturityClassifier.classify(Signals()))
        self.assertEqual(result["maturity"]["level"], constants.MIN_MATURITY_LEVEL)

    def test_empty_before_yields_a_regression_entry(self) -> None:
        result = DiagnosticsBundle.run({}, before={})
        self.assertEqual(result["regression"], RegressionDiffer.diff({}, {}))

    def test_report_missing_optional_sections_is_tolerated(self) -> None:
        # No top_issues / coverage / overall: the diagnostics must not raise.
        sparse = {"pillars": {constants.PILLAR_QUALITY: {"criteria": []}}}
        result = DiagnosticsBundle.run(sparse, before=sparse, signals=Signals())
        self.assertEqual(list(result), list(constants.DIAGNOSTICS_KEYS))


class ImmutabilityTest(unittest.TestCase):
    def test_report_is_not_mutated(self) -> None:
        snapshot = copy.deepcopy(REPORT)
        DiagnosticsBundle.run(REPORT, before=BEFORE, signals=SIGNALS)
        self.assertEqual(REPORT, snapshot)

    def test_before_is_not_mutated(self) -> None:
        snapshot = copy.deepcopy(BEFORE)
        DiagnosticsBundle.run(REPORT, before=BEFORE, signals=SIGNALS)
        self.assertEqual(BEFORE, snapshot)

    def test_signals_are_not_mutated(self) -> None:
        DiagnosticsBundle.run(REPORT, signals=SIGNALS)
        self.assertEqual(SIGNALS, Signals(retrieved_context=True, tool_calls=True))

    def test_each_call_returns_a_fresh_independent_dict(self) -> None:
        first = DiagnosticsBundle.run(REPORT, before=BEFORE, signals=SIGNALS)
        second = DiagnosticsBundle.run(REPORT, before=BEFORE, signals=SIGNALS)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        first["explainability"] = "mutated"
        self.assertNotEqual(second["explainability"], "mutated")


class ValidationTest(unittest.TestCase):
    def test_rejects_non_mapping_report(self) -> None:
        with self.assertRaises(TypeError):
            DiagnosticsBundle.run([])
        with self.assertRaises(TypeError):
            DiagnosticsBundle.run("not a report")
        with self.assertRaises(TypeError):
            DiagnosticsBundle.run(None)  # type: ignore[arg-type]

    def test_rejects_non_mapping_before(self) -> None:
        with self.assertRaises(TypeError):
            DiagnosticsBundle.run(REPORT, before=[])
        with self.assertRaises(TypeError):
            DiagnosticsBundle.run(REPORT, before="prior")  # type: ignore[arg-type]

    def test_rejects_non_signals_signals(self) -> None:
        with self.assertRaises(TypeError):
            DiagnosticsBundle.run(REPORT, signals={"tool_calls": True})  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            DiagnosticsBundle.run(REPORT, signals=True)  # type: ignore[arg-type]

    def test_none_inputs_are_accepted_and_omit_their_entries(self) -> None:
        result = DiagnosticsBundle.run(REPORT, before=None, signals=None)
        self.assertNotIn("maturity", result)
        self.assertNotIn("regression", result)


if __name__ == "__main__":
    unittest.main()
