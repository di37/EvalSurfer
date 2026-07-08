from __future__ import annotations

import unittest

from evalsurfer.diagnostics.maturity import MaturityClassifier, MaturityLevel
from evalsurfer.core.planner import Signals

LEVELS = MaturityClassifier.LEVELS


class MaturityCatalogTest(unittest.TestCase):
    def test_ladder_has_six_named_levels(self) -> None:
        self.assertEqual(len(LEVELS), 6)
        self.assertEqual([stage.level for stage in LEVELS], [1, 2, 3, 4, 5, 6])
        self.assertEqual(
            {stage.level: stage.name for stage in LEVELS},
            {
                1: "Prompt App",
                2: "Prompt + RAG",
                3: "Agent",
                4: "Multi-Agent",
                5: "Production AI System",
                6: "Self-Improving",
            },
        )

    def test_bounds_match_ladder_ends(self) -> None:
        self.assertEqual(LEVELS[0].level, 1)
        self.assertEqual(LEVELS[-1].level, 6)

    def test_only_top_level_has_empty_recommendation(self) -> None:
        for stage in LEVELS[:-1]:
            self.assertNotEqual(stage.recommendation, "")
        self.assertEqual(LEVELS[-1].recommendation, "")

    def test_level_dataclass_is_frozen(self) -> None:
        stage = LEVELS[0]
        self.assertIsInstance(stage, MaturityLevel)
        with self.assertRaises(Exception):
            stage.level = 99  # type: ignore[misc]


class MaturityLevelSelectionTest(unittest.TestCase):
    def test_empty_signals_is_prompt_app(self) -> None:
        result = MaturityClassifier.classify(Signals())
        self.assertEqual(result["level"], 1)
        self.assertEqual(result["name"], "Prompt App")

    def test_retrieved_context_is_rag(self) -> None:
        result = MaturityClassifier.classify(Signals(retrieved_context=True))
        self.assertEqual(result["level"], 2)
        self.assertEqual(result["name"], "Prompt + RAG")

    def test_tool_calls_is_agent(self) -> None:
        result = MaturityClassifier.classify(Signals(tool_calls=True))
        self.assertEqual(result["level"], 3)
        self.assertEqual(result["name"], "Agent")

    def test_multi_agent_flag_is_multi_agent(self) -> None:
        result = MaturityClassifier.classify(Signals(), multi_agent=True)
        self.assertEqual(result["level"], 4)
        self.assertEqual(result["name"], "Multi-Agent")

    def test_agent_with_traces_is_production(self) -> None:
        result = MaturityClassifier.classify(
            Signals(tool_calls=True, operational_traces=True)
        )
        self.assertEqual(result["level"], 5)
        self.assertEqual(result["name"], "Production AI System")

    def test_multi_agent_with_traces_is_production(self) -> None:
        result = MaturityClassifier.classify(
            Signals(operational_traces=True), multi_agent=True
        )
        self.assertEqual(result["level"], 5)

    def test_self_improving_is_top_level(self) -> None:
        result = MaturityClassifier.classify(Signals(), self_improving=True)
        self.assertEqual(result["level"], 6)
        self.assertEqual(result["name"], "Self-Improving")
        self.assertEqual(result["next_recommendation"], "")


class MaturityMaxLevelRuleTest(unittest.TestCase):
    def test_takes_the_max_level_reached(self) -> None:
        # retrieved_context (2) and tool_calls (3) -> the higher wins.
        result = MaturityClassifier.classify(
            Signals(retrieved_context=True, tool_calls=True)
        )
        self.assertEqual(result["level"], 3)

    def test_traces_alone_do_not_reach_production(self) -> None:
        # operational_traces needs an agentic base (level >= 3) to bump to 5.
        result = MaturityClassifier.classify(Signals(operational_traces=True))
        self.assertEqual(result["level"], 1)

    def test_traces_on_rag_only_stay_at_rag(self) -> None:
        # level 2 (< 3) so the operational_traces gate does not fire.
        result = MaturityClassifier.classify(
            Signals(retrieved_context=True, operational_traces=True)
        )
        self.assertEqual(result["level"], 2)

    def test_self_improving_overrides_everything(self) -> None:
        result = MaturityClassifier.classify(
            Signals(
                retrieved_context=True,
                tool_calls=True,
                operational_traces=True,
            ),
            multi_agent=True,
            self_improving=True,
        )
        self.assertEqual(result["level"], 6)

    def test_full_stack_without_self_improving_is_production(self) -> None:
        result = MaturityClassifier.classify(
            Signals(
                retrieved_context=True,
                tool_calls=True,
                operational_traces=True,
            ),
            multi_agent=True,
        )
        self.assertEqual(result["level"], 5)


class MaturityOutputShapeTest(unittest.TestCase):
    def test_result_has_exactly_the_four_keys(self) -> None:
        result = MaturityClassifier.classify(Signals(tool_calls=True))
        self.assertEqual(
            set(result),
            {"level", "name", "rationale", "next_recommendation"},
        )
        self.assertIsInstance(result["level"], int)
        self.assertIsInstance(result["name"], str)
        self.assertIsInstance(result["rationale"], str)
        self.assertIsInstance(result["next_recommendation"], str)

    def test_rationale_names_active_signals(self) -> None:
        result = MaturityClassifier.classify(
            Signals(tool_calls=True, operational_traces=True)
        )
        self.assertIn("tool_calls", result["rationale"])
        self.assertIn("operational_traces", result["rationale"])
        self.assertIn("Level 5", result["rationale"])

    def test_rationale_reports_no_active_signals_at_base(self) -> None:
        result = MaturityClassifier.classify(Signals())
        self.assertIn("none", result["rationale"])

    def test_next_recommendation_points_to_the_next_level(self) -> None:
        self.assertIn(
            "level 2",
            MaturityClassifier.classify(Signals())["next_recommendation"],
        )
        self.assertIn(
            "level 3",
            MaturityClassifier.classify(Signals(retrieved_context=True))[
                "next_recommendation"
            ],
        )
        self.assertIn(
            "level 5",
            MaturityClassifier.classify(Signals(), multi_agent=True)[
                "next_recommendation"
            ],
        )

    def test_returns_a_fresh_independent_dict_each_call(self) -> None:
        first = MaturityClassifier.classify(Signals(tool_calls=True))
        second = MaturityClassifier.classify(Signals(tool_calls=True))
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        first["level"] = 99
        self.assertEqual(second["level"], 3)  # unchanged by mutating the other

    def test_does_not_mutate_input_signals(self) -> None:
        signals = Signals(tool_calls=True, operational_traces=True)
        MaturityClassifier.classify(signals, multi_agent=True)
        self.assertEqual(
            signals, Signals(tool_calls=True, operational_traces=True)
        )


class MaturityValidationTest(unittest.TestCase):
    def test_rejects_non_signals_input(self) -> None:
        with self.assertRaises(TypeError):
            MaturityClassifier.classify({"tool_calls": True})  # type: ignore[arg-type]

    def test_rejects_non_bool_multi_agent(self) -> None:
        with self.assertRaises(TypeError):
            MaturityClassifier.classify(Signals(), multi_agent=1)  # type: ignore[arg-type]

    def test_rejects_non_bool_self_improving(self) -> None:
        with self.assertRaises(TypeError):
            MaturityClassifier.classify(Signals(), self_improving="yes")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
