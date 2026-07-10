from __future__ import annotations

import asyncio
import importlib.util
import unittest

import evalsurfer.constants as constants

_HAS_MCP = importlib.util.find_spec("mcp") is not None

# Every deterministic functionality is exposed as a tool.
_TOOLS = {
    "rubric", "plan", "coverage",
    "score_pillar", "score_overall", "decide", "score_report",
    "evaluate", "validate_report", "gate", "guardrail_gate",
    "explain", "root_cause", "regression_diff", "maturity",
    "industry_profiles", "industry_profile", "review_gate", "personas",
    "failure_map", "diagnose", "golden_set", "build_evidence",
    "metrics", "operational_score", "cost_per_request", "token_efficiency",
    "retrieval_metrics", "match_metrics", "text_metrics",
    "redteam_template", "redteam_check", "trajectory",
    "calibrate", "calibrate_one",
    "cohen_kappa", "fleiss_kappa", "krippendorff_alpha", "reference_calibrate",
    "dataset_from_traces", "dataset_diff", "dataset_contamination", "dataset_coverage",
    "adapter_ragas", "adapter_promptfoo", "adapter_otel", "adapter_langsmith",
}


@unittest.skipUnless(_HAS_MCP, "mcp SDK not installed (optional [mcp] extra)")
class McpServerTest(unittest.TestCase):
    """Guard the MCP wiring where the SDK is available; skipped otherwise."""

    def setUp(self) -> None:
        import evalsurfer.mcp_server as server  # lazy: needs the mcp SDK
        from evalsurfer import mcp_models as models

        self.s = server
        self.m = models

    def test_every_functionality_is_registered_as_a_tool(self) -> None:
        tools = asyncio.run(self.s.mcp.list_tools())
        self.assertEqual(_TOOLS, {tool.name for tool in tools})

    def test_tools_call_the_deterministic_layer(self) -> None:
        s, m = self.s, self.m

        self.assertEqual(len(s.rubric()), 29)
        self.assertEqual(
            s.plan(m.Sample(answer="a", retrieved_docs=["d"]))["plan"]["coverage"]["applicable_criteria"],
            12,
        )
        self.assertEqual(s.score_pillar([4, 2, None]), 6.0)
        self.assertEqual(s.decide(m.DecideInput(overall=9.0, safety=6.0)), "fail")

        report = s.evaluate(
            m.EvaluateRequest(sample=m.Sample(answer="a"), scores={"correctness_accuracy": 5})
        )
        wrapped = m.Report(**report)
        self.assertIn("decision", report)
        self.assertIn("passed", s.gate(wrapped, "fail"))
        self.assertEqual(s.explain(wrapped)["perfect"], 10.0)
        self.assertIn("needs_human_review", s.review_gate(wrapped))

        self.assertEqual(
            s.trajectory({"tool_calls": [{"name": "x"}]}, {"required_tools": ["y"]})["findings"][0]["type"],
            "missing_tool",
        )
        self.assertEqual(len(s.adapter_ragas({"faithfulness": 0.4})), 1)
        self.assertEqual(
            s.cost_per_request(1000, 500, m.Pricing(input_per_million=2.0, output_per_million=8.0)),
            0.006,
        )

        # Quality reference metrics (v0.1.3).
        self.assertEqual(
            s.retrieval_metrics(
                m.RetrievalMetricsInput(cases=[m.RetrievalCaseInput(retrieved=["d1", "d2"], relevant=["d1"])])
            )["mrr"],
            1.0,
        )
        self.assertEqual(
            s.match_metrics(
                m.MatchMetricsInput(predictions=["cat", "dog"], references=["cat", "dog"], task="extraction")
            )["exact_match_accuracy"],
            1.0,
        )
        self.assertEqual(
            s.text_metrics(
                m.TextMetricsInput(items=[m.TextItemInput(candidate="the cat", references=["the cat"])], metrics=["bleu"])
            )["corpus_bleu"],
            1.0,
        )

        # Chance-corrected agreement + judge-vs-human (v0.1.3).
        self.assertEqual(s.cohen_kappa(["a", "a", "b", "b"], ["a", "a", "b", "b"]), 1.0)
        self.assertEqual(s.krippendorff_alpha([[1, 2], [2, 1]]), -0.5)
        self.assertEqual(
            s.reference_calibrate({"correctness": 5, "relevance": 4}, {"correctness": 5, "relevance": 3})[
                constants.METRIC_JUDGE_HUMAN_MAE
            ],
            0.5,
        )

        # Golden dataset (v0.1.3).
        built = s.dataset_from_traces([{"query": "q1"}, {"query": "q1"}, {"query": "q2"}], name="d", version="v1")
        self.assertEqual(len(built["cases"]), 2)  # dedup by content hash
        self.assertEqual(s.dataset_coverage(built)["total"], 2)

    def test_pydantic_validation_rejects_bad_input(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            self.m.Pricing(input_per_million="cheap")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
