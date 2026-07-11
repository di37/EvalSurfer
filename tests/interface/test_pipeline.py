from __future__ import annotations

import unittest

from evalsurfer.interface.pipeline import evaluate as run_evaluate

_RAG_REQUEST = {
    "sample": {
        "query": "refund policy?",
        "answer": "Refunds in 30 days.",
        "retrieved_docs": ["Refunds within 14 days."],
    },
    "scores": {
        "correctness_accuracy": 2,
        "groundedness_faithfulness": 2,
        "context_relevance": 5,
        "toxicity": 5,
        "pii_leakage": 5,
        "harmful_content": 5,
        "bias_fairness": 5,
        "prompt_injection_resistance": 5,
    },
    "traces": {
        "traces": [
            {
                "request_started_at": "2026-07-08T12:00:00Z",
                "first_token_at": "2026-07-08T12:00:00.8Z",
                "response_completed_at": "2026-07-08T12:00:03Z",
                "input_tokens": 1200,
                "output_tokens": 300,
                "concurrency": 10,
            }
        ],
        "pricing": {"input_per_million": 2.0, "output_per_million": 8.0},
    },
    "slo": {"p95_latency_ms": 3000, "ttft_ms": 1000, "max_failure_rate": 0.02},
}


class PipelineEvaluateTest(unittest.TestCase):
    def test_assembles_full_report(self) -> None:
        report = run_evaluate(_RAG_REQUEST)
        self.assertIn(report["decision"], ("pass", "pass_with_fixes", "fail"))
        self.assertEqual(report["overall"]["decision"], report["decision"])
        self.assertIn("quality", report["metrics"])
        self.assertIn("safety", report["assurance"])
        self.assertIn("operational", report["metrics"])
        self.assertIn("coverage", report)
        for key in ("explainability", "root_cause", "failure_map", "review_gate", "maturity"):
            self.assertIn(key, report["diagnostics"])

    def test_operational_category_is_auto_scored(self) -> None:
        report = run_evaluate(_RAG_REQUEST)
        op = report["metrics"]["operational"]
        latency = next(c for c in op["criteria"] if c["id"] == "end_to_end_latency")
        self.assertEqual(latency["score"], 3)
        self.assertIsNotNone(op["score"])

    def test_no_traces_means_no_operational_category(self) -> None:
        request = {"sample": {"answer": "hi"}, "scores": {"correctness_accuracy": 5}}
        report = run_evaluate(request)
        self.assertNotIn("operational", report["metrics"])

    def test_critical_safety_issue_forces_fail(self) -> None:
        request = {
            "sample": {"answer": "bad"},
            "scores": {"correctness_accuracy": 5, "pii_leakage": 1},
            "top_issues": [
                {"severity": "critical", "description": "leaked PII", "criterion_id": "pii_leakage"}
            ],
        }
        self.assertEqual(run_evaluate(request)["decision"], "fail")


if __name__ == "__main__":
    unittest.main()
