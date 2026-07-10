from __future__ import annotations

import unittest

import evalsurfer.constants as constants
from evalsurfer.adapters import (
    LangSmithAdapter,
    OtelAdapter,
    PromptfooAdapter,
    RagasAdapter,
)
from evalsurfer.operational.metrics import OperationalMetrics, RequestTrace


class RagasAdapterTest(unittest.TestCase):
    def test_maps_known_metrics_to_scores(self) -> None:
        criteria = RagasAdapter.to_criteria(
            {
                "faithfulness": 1.0,
                "answer_relevancy": 0.0,
                "context_precision": 0.5,
                "context_recall": 0.75,
            }
        )
        by_id = {entry["id"]: entry["score"] for entry in criteria}
        self.assertEqual(by_id["groundedness_faithfulness"], 5)  # round(1 + 1.0*4)
        self.assertEqual(by_id["relevance"], 1)  # round(1 + 0.0*4)
        self.assertEqual(by_id["context_relevance"], 3)  # round(1 + 0.5*4)
        self.assertEqual(by_id["retrieval_recall"], 4)  # round(1 + 0.75*4)

    def test_entry_has_the_four_keys_name_and_evidence(self) -> None:
        (entry,) = RagasAdapter.to_criteria({"faithfulness": 0.9})
        self.assertEqual(set(entry), {"id", "name", "score", "evidence"})
        self.assertEqual(entry["id"], "groundedness_faithfulness")
        self.assertEqual(entry["name"], "Groundedness / Faithfulness")
        self.assertIn("faithfulness", entry["evidence"])
        self.assertIn("0.9", entry["evidence"])

    def test_unknown_metrics_are_skipped(self) -> None:
        criteria = RagasAdapter.to_criteria(
            {"faithfulness": 0.8, "totally_made_up": 0.9}
        )
        self.assertEqual([e["id"] for e in criteria], ["groundedness_faithfulness"])

    def test_empty_mapping_returns_empty_list(self) -> None:
        self.assertEqual(RagasAdapter.to_criteria({}), [])

    def test_none_valued_metric_is_skipped(self) -> None:
        self.assertEqual(RagasAdapter.to_criteria({"faithfulness": None}), [])

    def test_scores_clamp_into_the_one_to_five_range(self) -> None:
        low = RagasAdapter.to_criteria({"faithfulness": -3.0})[0]["score"]
        high = RagasAdapter.to_criteria({"faithfulness": 3.0})[0]["score"]
        self.assertEqual(low, constants.CRITERION_MIN_SCORE)
        self.assertEqual(high, constants.CRITERION_MAX_SCORE)

    def test_output_order_is_canonical_not_input_order(self) -> None:
        criteria = RagasAdapter.to_criteria(
            {"context_recall": 0.5, "faithfulness": 0.5}
        )
        self.assertEqual(
            [e["id"] for e in criteria],
            ["groundedness_faithfulness", "retrieval_recall"],
        )

    def test_rejects_non_mapping(self) -> None:
        with self.assertRaises(TypeError):
            RagasAdapter.to_criteria([("faithfulness", 0.5)])  # type: ignore[arg-type]

    def test_rejects_non_numeric_value(self) -> None:
        with self.assertRaises(TypeError):
            RagasAdapter.to_criteria({"faithfulness": "high"})

    def test_rejects_boolean_value(self) -> None:
        with self.assertRaises(TypeError):
            RagasAdapter.to_criteria({"faithfulness": True})

    def test_does_not_mutate_input(self) -> None:
        metrics = {"faithfulness": 0.9, "unknown": 0.1}
        RagasAdapter.to_criteria(metrics)
        self.assertEqual(metrics, {"faithfulness": 0.9, "unknown": 0.1})


class PromptfooAdapterTest(unittest.TestCase):
    def test_all_passing_scores_five(self) -> None:
        report = PromptfooAdapter.to_report(
            {"results": [{"success": True}, {"success": True}]}
        )
        quality = report["pillars"][constants.PILLAR_QUALITY]
        (criterion,) = quality["criteria"]
        self.assertEqual(criterion["id"], "correctness_accuracy")
        self.assertEqual(criterion["name"], "Correctness / Accuracy")
        self.assertEqual(criterion["score"], 5)
        self.assertEqual(quality["score"], 10.0)
        self.assertEqual(report["overall"]["score"], 10.0)

    def test_all_failing_scores_one_and_fails(self) -> None:
        report = PromptfooAdapter.to_report(
            {"results": [{"success": False}, {"success": False}]}
        )
        (criterion,) = report["pillars"][constants.PILLAR_QUALITY]["criteria"]
        self.assertEqual(criterion["score"], 1)
        self.assertEqual(report["decision"], constants.DECISION_FAIL)

    def test_half_passing_maps_to_mid_score(self) -> None:
        report = PromptfooAdapter.to_report(
            {"results": [{"success": True}, {"success": False}]}
        )
        (criterion,) = report["pillars"][constants.PILLAR_QUALITY]["criteria"]
        self.assertEqual(criterion["score"], 3)  # round(1 + 0.5*4)
        self.assertEqual(report["metadata"]["pass_count"], 1)
        self.assertEqual(report["metadata"]["case_count"], 2)

    def test_report_has_required_keys_and_consistent_decision(self) -> None:
        report = PromptfooAdapter.to_report({"results": [{"success": True}]})
        for key in ("overall", "pillars", "decision", "top_issues"):
            self.assertIn(key, report)
        self.assertIn(report["decision"], constants.DECISIONS)
        self.assertEqual(report["overall"]["decision"], report["decision"])
        self.assertEqual(report["metadata"]["source"], constants.ADAPTER_PROMPTFOO)
        # No safety pillar assessed, so a full "pass" is never reached.
        self.assertEqual(report["decision"], constants.DECISION_PASS_WITH_FIXES)

    def test_accepts_a_bare_list_of_cases(self) -> None:
        report = PromptfooAdapter.to_report([{"success": True}])
        (criterion,) = report["pillars"][constants.PILLAR_QUALITY]["criteria"]
        self.assertEqual(criterion["score"], 5)

    def test_string_false_success_counts_as_failure(self) -> None:
        report = PromptfooAdapter.to_report({"results": [{"success": "false"}]})
        (criterion,) = report["pillars"][constants.PILLAR_QUALITY]["criteria"]
        self.assertEqual(criterion["score"], 1)

    def test_missing_success_counts_as_failure(self) -> None:
        report = PromptfooAdapter.to_report({"results": [{}]})
        (criterion,) = report["pillars"][constants.PILLAR_QUALITY]["criteria"]
        self.assertEqual(criterion["score"], 1)

    def test_missing_results_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            PromptfooAdapter.to_report({})

    def test_empty_results_raises(self) -> None:
        with self.assertRaises(ValueError):
            PromptfooAdapter.to_report({"results": []})

    def test_rejects_bad_top_level_type(self) -> None:
        with self.assertRaises(TypeError):
            PromptfooAdapter.to_report(42)  # type: ignore[arg-type]

    def test_rejects_non_mapping_case(self) -> None:
        with self.assertRaises(TypeError):
            PromptfooAdapter.to_report({"results": ["nope"]})

    def test_does_not_mutate_input(self) -> None:
        payload = {"results": [{"success": True}, {"success": False}]}
        PromptfooAdapter.to_report(payload)
        self.assertEqual(
            payload, {"results": [{"success": True}, {"success": False}]}
        )


class OtelAdapterTest(unittest.TestCase):
    def test_converts_nanosecond_timestamps_to_seconds(self) -> None:
        (trace,) = OtelAdapter.to_traces(
            [
                {
                    "startTimeUnixNano": 1_000_000_000,  # 1.0 s
                    "endTimeUnixNano": 3_500_000_000,  # 3.5 s
                }
            ]
        )
        self.assertEqual(trace["request_started_at"], 1.0)
        self.assertEqual(trace["response_completed_at"], 3.5)

    def test_lifts_tokens_from_mapping_attributes(self) -> None:
        (trace,) = OtelAdapter.to_traces(
            [
                {
                    "startTimeUnixNano": 0,
                    "endTimeUnixNano": 1_000_000_000,
                    "attributes": {
                        "gen_ai.usage.input_tokens": 12,
                        "gen_ai.usage.output_tokens": 34,
                    },
                }
            ]
        )
        self.assertEqual(trace["input_tokens"], 12)
        self.assertEqual(trace["output_tokens"], 34)

    def test_lifts_tokens_from_otlp_list_attributes(self) -> None:
        (trace,) = OtelAdapter.to_traces(
            [
                {
                    "startTimeUnixNano": "0",
                    "endTimeUnixNano": "2000000000",
                    "attributes": [
                        {"key": "input_tokens", "value": {"intValue": "7"}},
                        {"key": "output_tokens", "value": {"intValue": "9"}},
                    ],
                }
            ]
        )
        self.assertEqual(trace["response_completed_at"], 2.0)
        self.assertEqual(trace["input_tokens"], "7")
        self.assertEqual(trace["output_tokens"], "9")

    def test_output_is_accepted_by_request_trace(self) -> None:
        traces = OtelAdapter.to_traces(
            [
                {
                    "startTimeUnixNano": 0,
                    "endTimeUnixNano": 2_000_000_000,
                    "attributes": {"input_tokens": 5, "output_tokens": 10},
                }
            ]
        )
        parsed = RequestTrace.from_mapping(traces[0])
        self.assertEqual(OperationalMetrics.end_to_end_latency_ms(parsed), 2000)
        self.assertEqual(parsed.input_tokens, 5)
        self.assertEqual(parsed.output_tokens, 10)

    def test_span_without_end_or_attributes(self) -> None:
        (trace,) = OtelAdapter.to_traces([{"startTimeUnixNano": 1_000_000_000}])
        self.assertEqual(trace, {"request_started_at": 1.0})

    def test_empty_spans_returns_empty_list(self) -> None:
        self.assertEqual(OtelAdapter.to_traces([]), [])

    def test_missing_start_raises(self) -> None:
        with self.assertRaises(ValueError):
            OtelAdapter.to_traces([{"endTimeUnixNano": 1_000_000_000}])

    def test_rejects_non_mapping_span(self) -> None:
        with self.assertRaises(TypeError):
            OtelAdapter.to_traces([42])  # type: ignore[list-item]

    def test_rejects_non_list_input(self) -> None:
        with self.assertRaises(TypeError):
            OtelAdapter.to_traces({"startTimeUnixNano": 0})  # type: ignore[arg-type]

    def test_does_not_mutate_input(self) -> None:
        spans = [{"startTimeUnixNano": 0, "attributes": {"input_tokens": 1}}]
        OtelAdapter.to_traces(spans)
        self.assertEqual(
            spans, [{"startTimeUnixNano": 0, "attributes": {"input_tokens": 1}}]
        )


class LangSmithAdapterTest(unittest.TestCase):
    def test_maps_timestamps_and_top_level_tokens(self) -> None:
        (trace,) = LangSmithAdapter.to_traces(
            [
                {
                    "start_time": "2026-07-08T12:00:00Z",
                    "end_time": "2026-07-08T12:00:02Z",
                    "prompt_tokens": 40,
                    "completion_tokens": 12,
                }
            ]
        )
        self.assertEqual(trace["request_started_at"], "2026-07-08T12:00:00Z")
        self.assertEqual(trace["response_completed_at"], "2026-07-08T12:00:02Z")
        self.assertEqual(trace["input_tokens"], 40)
        self.assertEqual(trace["output_tokens"], 12)

    def test_reads_nested_usage_metadata(self) -> None:
        (trace,) = LangSmithAdapter.to_traces(
            [
                {
                    "start_time": "2026-07-08T12:00:00Z",
                    "usage_metadata": {"input_tokens": 3, "output_tokens": 4},
                }
            ]
        )
        self.assertEqual(trace["input_tokens"], 3)
        self.assertEqual(trace["output_tokens"], 4)

    def test_output_is_accepted_by_request_trace(self) -> None:
        traces = LangSmithAdapter.to_traces(
            [
                {
                    "start_time": "2026-07-08T12:00:00Z",
                    "end_time": "2026-07-08T12:00:03Z",
                    "input_tokens": 5,
                    "output_tokens": 10,
                }
            ]
        )
        parsed = RequestTrace.from_mapping(traces[0])
        self.assertEqual(OperationalMetrics.end_to_end_latency_ms(parsed), 3000)
        self.assertEqual(parsed.input_tokens, 5)
        self.assertEqual(parsed.output_tokens, 10)

    def test_run_without_end_or_tokens(self) -> None:
        (trace,) = LangSmithAdapter.to_traces(
            [{"start_time": "2026-07-08T12:00:00Z"}]
        )
        self.assertEqual(trace, {"request_started_at": "2026-07-08T12:00:00Z"})

    def test_empty_runs_returns_empty_list(self) -> None:
        self.assertEqual(LangSmithAdapter.to_traces([]), [])

    def test_missing_start_raises(self) -> None:
        with self.assertRaises(ValueError):
            LangSmithAdapter.to_traces([{"end_time": "2026-07-08T12:00:02Z"}])

    def test_rejects_non_mapping_run(self) -> None:
        with self.assertRaises(TypeError):
            LangSmithAdapter.to_traces(["nope"])  # type: ignore[list-item]

    def test_rejects_non_list_input(self) -> None:
        with self.assertRaises(TypeError):
            LangSmithAdapter.to_traces({"start_time": "x"})  # type: ignore[arg-type]

    def test_does_not_mutate_input(self) -> None:
        runs = [{"start_time": "2026-07-08T12:00:00Z", "input_tokens": 1}]
        LangSmithAdapter.to_traces(runs)
        self.assertEqual(
            runs, [{"start_time": "2026-07-08T12:00:00Z", "input_tokens": 1}]
        )


if __name__ == "__main__":
    unittest.main()
