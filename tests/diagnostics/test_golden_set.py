from __future__ import annotations

import copy
import unittest
from dataclasses import replace

import evalsurfer.constants as constants
from evalsurfer.core.planner import Signals

from evalsurfer.diagnostics.golden_set import GOLDEN_CASES, GoldenCase, GoldenSet


def _cases_by_name() -> dict[str, GoldenCase]:
    return {case.name: case for case in GOLDEN_CASES}


class GoldenSetOracleTest(unittest.TestCase):
    def test_run_all_reports_every_case_ok(self) -> None:
        results = GoldenSet.run_all()
        self.assertEqual(len(results), len(GOLDEN_CASES))
        for result in results:
            self.assertTrue(
                result["ok"],
                msg=f"{result['name']} failed: {result['failures']}",
            )
            self.assertEqual(result["failures"], [])

    def test_result_names_match_cases_in_order(self) -> None:
        names = [result["name"] for result in GoldenSet.run_all()]
        self.assertEqual(names, [case.name for case in GOLDEN_CASES])

    def test_run_case_result_shape(self) -> None:
        result = GoldenSet.run_case(GOLDEN_CASES[0])
        self.assertEqual(set(result), {"name", "ok", "failures"})
        self.assertIsInstance(result["ok"], bool)
        self.assertIsInstance(result["failures"], list)

    def test_golden_set_has_three_or_four_cases(self) -> None:
        self.assertIn(len(GOLDEN_CASES), (3, 4))
        self.assertEqual(len({case.name for case in GOLDEN_CASES}), len(GOLDEN_CASES))


class GoldenSetExpectedValuesTest(unittest.TestCase):
    """Pin the hand-computed expectations so the oracle stays meaningful."""

    def test_clean_rag_case_expects_pass(self) -> None:
        case = _cases_by_name()["clean_rag_pass"]
        self.assertEqual(case.expected_decision, "pass")
        self.assertEqual(case.expected_applicable_pillars, frozenset({"quality", "safety"}))

    def test_ungrounded_rag_case_expects_fail(self) -> None:
        case = _cases_by_name()["ungrounded_rag_fail"]
        self.assertEqual(case.expected_decision, "fail")
        self.assertEqual(
            case.criterion_scores["quality"]["groundedness_faithfulness"], 1
        )

    def test_agent_case_expects_pass_with_fixes(self) -> None:
        case = _cases_by_name()["agent_pass_with_fixes"]
        self.assertEqual(case.expected_decision, "pass_with_fixes")
        self.assertTrue(case.signals.tool_calls)
        self.assertTrue(case.signals.tool_failure)

    def test_operational_only_case_skips_safety_and_quality(self) -> None:
        case = _cases_by_name()["operational_only"]
        self.assertEqual(case.expected_applicable_pillars, frozenset({"operational"}))
        self.assertEqual(case.expected_decision, "pass_with_fixes")
        self.assertNotIn("safety", case.criterion_scores)


class GoldenSetNonTautologicalTest(unittest.TestCase):
    """A wrong expectation must surface as a real, described failure."""

    def test_wrong_expected_decision_is_flagged(self) -> None:
        base = _cases_by_name()["clean_rag_pass"]
        broken = replace(base, expected_decision="fail")
        result = GoldenSet.run_case(broken)
        self.assertFalse(result["ok"])
        self.assertTrue(any("decision" in f for f in result["failures"]))

    def test_wrong_expected_pillars_is_flagged(self) -> None:
        base = _cases_by_name()["clean_rag_pass"]
        broken = replace(base, expected_applicable_pillars=frozenset({"operational"}))
        result = GoldenSet.run_case(broken)
        self.assertFalse(result["ok"])
        self.assertTrue(any("applicable pillars" in f for f in result["failures"]))

    def test_both_wrong_records_two_failures(self) -> None:
        base = _cases_by_name()["agent_pass_with_fixes"]
        broken = replace(
            base,
            expected_decision="pass",
            expected_applicable_pillars=frozenset({"operational"}),
        )
        result = GoldenSet.run_case(broken)
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["failures"]), 2)


class GoldenSetEdgeCaseTest(unittest.TestCase):
    def test_none_scores_are_excluded_from_pillar(self) -> None:
        # groundedness None must be ignored; remaining 5s keep quality at 10.0
        # so the decision is still a clean pass.
        case = GoldenCase(
            name="none_score_excluded",
            signals=Signals(answer=True, retrieved_context=True, citations=True),
            criterion_scores={
                "quality": {
                    "correctness_accuracy": 5,
                    "groundedness_faithfulness": None,
                    "citation_accuracy": 5,
                },
                "safety": {"toxicity": 5, "harmful_content": 5},
            },
            expected_applicable_pillars=frozenset({"quality", "safety"}),
            expected_decision="pass",
        )
        self.assertTrue(GoldenSet.run_case(case)["ok"])

    def test_all_none_pillar_is_treated_as_unscored(self) -> None:
        # A pillar with only None scores yields no pillar score; with no safety
        # score the operational-only target still lands on pass_with_fixes.
        case = GoldenCase(
            name="all_none_operational",
            signals=Signals(operational_traces=True),
            criterion_scores={
                "operational": {
                    "end_to_end_latency": None,
                    "cost_per_request": None,
                },
            },
            expected_applicable_pillars=frozenset({"operational"}),
            expected_decision="pass_with_fixes",
        )
        self.assertTrue(GoldenSet.run_case(case)["ok"])

    def test_empty_criterion_scores_yield_pass_with_fixes(self) -> None:
        # No scores at all -> overall None, safety None -> pass_with_fixes.
        case = GoldenCase(
            name="empty_scores",
            signals=Signals(operational_traces=True),
            criterion_scores={},
            expected_applicable_pillars=frozenset({"operational"}),
            expected_decision="pass_with_fixes",
        )
        self.assertTrue(GoldenSet.run_case(case)["ok"])

    def test_empty_signals_have_no_applicable_pillars(self) -> None:
        case = GoldenCase(
            name="empty_signals",
            signals=Signals(),
            criterion_scores={},
            expected_applicable_pillars=frozenset(),
            expected_decision="pass_with_fixes",
        )
        result = GoldenSet.run_case(case)
        self.assertTrue(result["ok"])


class GoldenSetImmutabilityTest(unittest.TestCase):
    def test_run_case_does_not_mutate_inputs(self) -> None:
        case = _cases_by_name()["clean_rag_pass"]
        before = copy.deepcopy(case.criterion_scores)
        GoldenSet.run_case(case)
        self.assertEqual(case.criterion_scores, before)

    def test_run_all_leaves_golden_cases_unchanged(self) -> None:
        snapshot = tuple(
            (c.name, copy.deepcopy(dict(c.criterion_scores)), c.expected_decision)
            for c in GOLDEN_CASES
        )
        GoldenSet.run_all()
        after = tuple(
            (c.name, copy.deepcopy(dict(c.criterion_scores)), c.expected_decision)
            for c in GOLDEN_CASES
        )
        self.assertEqual(snapshot, after)


class GoldenSetValidationTest(unittest.TestCase):
    def _valid_kwargs(self) -> dict:
        return {
            "name": "probe",
            "signals": Signals(answer=True),
            "criterion_scores": {"quality": {"correctness_accuracy": 4}},
            "expected_applicable_pillars": frozenset({"quality", "safety"}),
            "expected_decision": "pass_with_fixes",
        }

    def test_valid_case_constructs(self) -> None:
        self.assertIsInstance(GoldenCase(**self._valid_kwargs()), GoldenCase)

    def test_blank_name_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["name"] = "   "
        with self.assertRaises(ValueError):
            GoldenCase(**kwargs)

    def test_non_signals_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["signals"] = {"answer": True}
        with self.assertRaises(TypeError):
            GoldenCase(**kwargs)

    def test_unknown_pillar_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["criterion_scores"] = {"speed": {"x": 4}}
        with self.assertRaises(ValueError):
            GoldenCase(**kwargs)

    def test_out_of_range_score_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["criterion_scores"] = {"quality": {"correctness_accuracy": 7}}
        with self.assertRaises(ValueError):
            GoldenCase(**kwargs)

    def test_bool_score_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["criterion_scores"] = {"quality": {"correctness_accuracy": True}}
        with self.assertRaises(TypeError):
            GoldenCase(**kwargs)

    def test_non_frozenset_expected_pillars_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["expected_applicable_pillars"] = {"quality"}
        with self.assertRaises(TypeError):
            GoldenCase(**kwargs)

    def test_unknown_expected_pillar_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["expected_applicable_pillars"] = frozenset({"speed"})
        with self.assertRaises(ValueError):
            GoldenCase(**kwargs)

    def test_invalid_decision_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["expected_decision"] = "maybe"
        with self.assertRaises(ValueError):
            GoldenCase(**kwargs)

    def test_run_case_rejects_non_case(self) -> None:
        with self.assertRaises(TypeError):
            GoldenSet.run_case({"name": "not-a-case"})


class GoldenSetPublicApiTest(unittest.TestCase):
    def test_decisions_constant(self) -> None:
        self.assertEqual(constants.DECISIONS, ("pass", "pass_with_fixes", "fail"))

    def test_goldenset_exposes_static_runners(self) -> None:
        self.assertTrue(callable(GoldenSet.run_case))
        self.assertTrue(callable(GoldenSet.run_all))


if __name__ == "__main__":
    unittest.main()
