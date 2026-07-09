from __future__ import annotations

import asyncio
import importlib.util
import unittest

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
    "redteam_template", "redteam_check", "trajectory",
    "calibrate", "calibrate_one",
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

    def test_pydantic_validation_rejects_bad_input(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            self.m.Pricing(input_per_million="cheap")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
