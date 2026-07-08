from __future__ import annotations

import json
import os
import tempfile
import unittest

from evalsurfer.core.planner import EvaluationPlanner, Signals
from evalsurfer.cli.plan import build_report, main, resolve_signals, signals_from_flags

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# framework.json names the quality pillar "application_quality"; the report
# schema (and the planner) use "quality".
_FRAMEWORK_PILLAR_ALIAS = {"application_quality": "quality"}


def framework_criteria() -> set[tuple[str, str | None, str, str]]:
    with open(os.path.join(HERE, "framework.json"), encoding="utf-8") as file:
        pillars = json.load(file)["eval_surfer"]["pillars"]
    out: set[tuple[str, str | None, str, str]] = set()
    for pillar in pillars:
        pid = _FRAMEWORK_PILLAR_ALIAS.get(pillar["id"], pillar["id"])
        for sub in pillar.get("subcategories", [{"id": None, "criteria": pillar.get("criteria", [])}]):
            for crit in sub["criteria"]:
                out.add((pid, sub["id"], crit["id"], crit["name"]))
    return out


def applicable_ids(plan) -> set[str]:
    return {c.id for c in plan.applicable_criteria()}


def applicable_pillars(plan) -> set[str]:
    return {p.id for p in plan.pillars if p.applicable}


class PlannerCatalogTest(unittest.TestCase):
    def test_catalog_matches_framework_json(self) -> None:
        planner = {(c.pillar, c.group, c.id, c.name) for c in EvaluationPlanner.CRITERIA}
        self.assertEqual(planner, framework_criteria())

    def test_catalog_has_29_criteria(self) -> None:
        self.assertEqual(len(EvaluationPlanner.CRITERIA), 29)


class PlannerApplicabilityTest(unittest.TestCase):
    def test_rag_answer_selects_quality_and_safety(self) -> None:
        plan = EvaluationPlanner.plan(
            Signals(answer=True, retrieved_context=True, citations=True)
        )
        self.assertEqual(applicable_pillars(plan), {"quality", "safety"})
        ids = applicable_ids(plan)
        self.assertIn("correctness_accuracy", ids)
        self.assertIn("citation_accuracy", ids)
        self.assertIn("toxicity", ids)  # safety applies: answer present
        self.assertNotIn("tool_selection", ids)
        self.assertNotIn("end_to_end_latency", ids)

    def test_rag_without_citations_skips_only_citation_accuracy(self) -> None:
        plan = EvaluationPlanner.plan(Signals(answer=True, retrieved_context=True))
        ids = applicable_ids(plan)
        self.assertNotIn("citation_accuracy", ids)
        self.assertIn("context_relevance", ids)
        self.assertIn("groundedness_faithfulness", ids)  # needs answer, present

    def test_error_recovery_requires_a_tool_failure(self) -> None:
        without = applicable_ids(EvaluationPlanner.plan(Signals(answer=True, tool_calls=True)))
        with_fail = applicable_ids(
            EvaluationPlanner.plan(Signals(answer=True, tool_calls=True, tool_failure=True))
        )
        self.assertNotIn("error_recovery", without)
        self.assertIn("tool_selection", without)
        self.assertIn("error_recovery", with_fail)

    def test_operational_only_target_skips_safety_without_an_answer(self) -> None:
        plan = EvaluationPlanner.plan(Signals(operational_traces=True))
        self.assertEqual(applicable_pillars(plan), {"operational"})
        self.assertNotIn("toxicity", applicable_ids(plan))

    def test_safety_opt_out_is_explicit(self) -> None:
        plan = EvaluationPlanner.plan(Signals(answer=True, safety_relevant=False))
        self.assertEqual(applicable_pillars(plan), {"quality"})
        toxicity = next(c for p in plan.pillars for c in p.criteria if c.id == "toxicity")
        self.assertFalse(toxicity.applicable)
        self.assertIn("opted out", toxicity.reason)


class PlannerCoverageTest(unittest.TestCase):
    def test_planned_coverage_counts_applicable(self) -> None:
        plan = EvaluationPlanner.plan(
            Signals(answer=True, retrieved_context=True, citations=True)
        )
        cov = EvaluationPlanner.planned_coverage(plan)
        self.assertEqual(cov["applicable_pillars"], 2)
        self.assertEqual(cov["total_pillars"], 3)
        self.assertEqual(cov["applicable_criteria"], 13)  # 4 core + 4 rag + 5 safety
        self.assertEqual(cov["total_criteria"], 29)
        self.assertAlmostEqual(cov["score"], round(13 / 29, 3))

    def test_coverage_against_report(self) -> None:
        plan = EvaluationPlanner.plan(
            Signals(answer=True, retrieved_context=True, citations=True)
        )
        report = {
            "pillars": {
                "quality": {
                    "criteria": [
                        {"id": "correctness_accuracy", "score": 4},
                        {"id": "citation_accuracy", "score": None},
                    ]
                },
                "safety": {"criteria": [{"id": "toxicity", "score": 5}]},
            }
        }
        cov = EvaluationPlanner.coverage(plan, report)
        self.assertEqual(cov["applicable"], 13)
        self.assertEqual(cov["assessed"], 2)  # correctness_accuracy + toxicity
        self.assertIn("citation_accuracy", cov["missing"])
        self.assertAlmostEqual(cov["score"], round(2 / 13, 3))


class SignalsInferenceTest(unittest.TestCase):
    def test_infers_answer_and_context(self) -> None:
        signals = Signals.from_sample({"answer": "yes", "retrieved_docs": ["chunk"]})
        self.assertTrue(signals.answer)
        self.assertTrue(signals.retrieved_context)
        self.assertFalse(signals.tool_calls)
        self.assertTrue(signals.safety_relevant)

    def test_detects_tool_failure(self) -> None:
        signals = Signals.from_sample({"tool_calls": [{"name": "search", "error": "timeout"}]})
        self.assertTrue(signals.tool_calls)
        self.assertTrue(signals.tool_failure)

    def test_multi_turn_needs_more_than_one_message(self) -> None:
        self.assertTrue(
            Signals.from_sample({"messages": [{"role": "user"}, {"role": "assistant"}]}).multi_turn
        )
        self.assertFalse(Signals.from_sample({"messages": [{"role": "user"}]}).multi_turn)

    def test_empty_sample_is_all_false_except_safety(self) -> None:
        signals = Signals.from_sample({})
        self.assertFalse(signals.answer)
        self.assertTrue(signals.safety_relevant)

    def test_rejects_non_boolean_safety_flag(self) -> None:
        with self.assertRaises(ValueError):
            Signals.from_sample({"answer": "x", "safety_relevant": "no"})


class PlannerCliTest(unittest.TestCase):
    def test_build_report_from_sample(self) -> None:
        report = build_report({"sample": {"answer": "x", "retrieved_docs": ["c"]}})
        self.assertIn("signals", report)
        self.assertEqual(report["plan"]["coverage"]["applicable_pillars"], 2)

    def test_flags_reject_unknown_signal(self) -> None:
        with self.assertRaises(ValueError):
            signals_from_flags({"answer": True, "nope": True})

    def test_flags_reject_non_boolean(self) -> None:
        with self.assertRaises(ValueError):
            signals_from_flags({"answer": "yes"})

    def test_resolve_signals_accepts_bare_sample(self) -> None:
        signals = resolve_signals({"answer": "x", "tool_calls": [{"name": "t"}]})
        self.assertTrue(signals.answer)
        self.assertTrue(signals.tool_calls)

    def test_main_writes_output_and_handles_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            in_path = os.path.join(tmp, "in.json")
            out_path = os.path.join(tmp, "out.json")
            with open(in_path, "w", encoding="utf-8") as file:
                json.dump({"answer": "x"}, file)
            self.assertEqual(main([in_path, "-o", out_path, "--pretty"]), 0)
            with open(out_path, encoding="utf-8") as file:
                self.assertIn("plan", json.load(file))
        self.assertEqual(main(["does-not-exist.json"]), 1)


if __name__ == "__main__":
    unittest.main()
