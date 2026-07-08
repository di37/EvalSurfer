from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import json
from math import inf, nan
import os
import tempfile
import unittest

from evalsurfer.cli.metrics import build_report, main
from evalsurfer.operational.metrics import (
    OperationalMetrics,
    Pricing,
    RequestTrace,
)


class OperationalMetricsTest(unittest.TestCase):
    def test_calculates_end_to_end_latency_and_ttft(self) -> None:
        trace = RequestTrace(
            request_started_at="2026-07-08T12:00:00Z",
            first_token_at="2026-07-08T12:00:01.250Z",
            response_completed_at="2026-07-08T12:00:04Z",
            output_tokens=55,
        )

        self.assertEqual(OperationalMetrics.end_to_end_latency_ms(trace), 4000)
        self.assertEqual(OperationalMetrics.ttft_ms(trace), 1250)
        self.assertEqual(OperationalMetrics.tokens_per_second(trace), 20)

    def test_calculates_request_cost(self) -> None:
        pricing = Pricing(input_per_million=2.0, output_per_million=8.0)

        cost = OperationalMetrics.cost_per_request_usd(
            input_tokens=1_000,
            output_tokens=500,
            pricing=pricing,
        )

        self.assertEqual(cost, 0.006)

    def test_rejects_negative_pricing(self) -> None:
        with self.assertRaises(ValueError):
            OperationalMetrics.cost_per_request_usd(
                input_tokens=1_000,
                output_tokens=500,
                pricing=Pricing(input_per_million=-1.0, output_per_million=8.0),
            )

    def test_rejects_non_finite_pricing(self) -> None:
        with self.assertRaises(ValueError):
            OperationalMetrics.cost_per_request_usd(
                input_tokens=1_000,
                output_tokens=500,
                pricing=Pricing(input_per_million=nan, output_per_million=8.0),
            )

        with self.assertRaises(ValueError):
            OperationalMetrics.cost_per_request_usd(
                input_tokens=1_000,
                output_tokens=500,
                pricing=Pricing(input_per_million=1.0, output_per_million=inf),
            )

    def test_calculates_token_efficiency(self) -> None:
        efficiency = OperationalMetrics.token_efficiency(
            useful_output_tokens=80,
            input_tokens=120,
            output_tokens=100,
        )

        self.assertAlmostEqual(efficiency, 80 / 220)

    def test_calculates_failure_rate(self) -> None:
        traces = [
            RequestTrace("2026-07-08T12:00:00Z", failed=False),
            RequestTrace("2026-07-08T12:00:01Z", failed=True),
            RequestTrace("2026-07-08T12:00:02Z", failed=True),
        ]

        self.assertEqual(OperationalMetrics.failure_rate(traces), 2 / 3)

    def test_summarizes_operational_metrics(self) -> None:
        traces = [
            RequestTrace(
                request_started_at=0,
                first_token_at=0.2,
                response_completed_at=1,
                input_tokens=100,
                output_tokens=40,
            ),
            RequestTrace(
                request_started_at=1,
                first_token_at=1.4,
                response_completed_at=3,
                input_tokens=200,
                output_tokens=80,
                failed=True,
            ),
        ]

        summary = OperationalMetrics.summarize(
            traces,
            pricing=Pricing(input_per_million=1.0, output_per_million=2.0),
        )

        self.assertEqual(summary.request_count, 2)
        self.assertEqual(summary.failure_count, 1)
        self.assertEqual(summary.failure_rate, 0.5)
        self.assertIsNotNone(summary.latency)
        self.assertIsNotNone(summary.ttft)
        self.assertEqual(summary.latency.p95_ms if summary.latency else None, 2000)
        self.assertAlmostEqual(summary.total_cost_usd or 0, 0.00054)

    def test_groups_latency_under_load_by_concurrency(self) -> None:
        traces = [
            RequestTrace(0, response_completed_at=1, concurrency=1),
            RequestTrace(0, response_completed_at=2, concurrency=1),
            RequestTrace(0, response_completed_at=3, concurrency=10),
        ]

        grouped = OperationalMetrics.latency_under_load(traces)

        self.assertEqual(grouped[1].count, 2)
        self.assertEqual(grouped[1].p95_ms, 2000)
        self.assertEqual(grouped[10].p95_ms, 3000)

    def test_builds_trace_from_common_mapping_shapes(self) -> None:
        trace = RequestTrace.from_mapping(
            {
                "timing": {
                    "start_time": "2026-07-08T12:00:00Z",
                    "first_token_at": "2026-07-08T12:00:00.500Z",
                    "end_time": "2026-07-08T12:00:02Z",
                },
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                },
                "load": {"concurrency": 25},
            }
        )

        self.assertEqual(OperationalMetrics.ttft_ms(trace), 500)
        self.assertEqual(OperationalMetrics.end_to_end_latency_ms(trace), 2000)
        self.assertEqual(trace.input_tokens, 100)
        self.assertEqual(trace.output_tokens, 50)
        self.assertEqual(trace.concurrency, 25)

    def test_trace_mapping_preserves_explicit_zero_token_counts(self) -> None:
        trace = RequestTrace.from_mapping(
            {
                "started_at": "2026-07-08T12:00:00Z",
                "input_tokens": 0,
                "output_tokens": 0,
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                },
            }
        )

        self.assertEqual(trace.input_tokens, 0)
        self.assertEqual(trace.output_tokens, 0)

    def test_trace_mapping_rejects_invalid_token_counts(self) -> None:
        invalid_values = (1.9, True, "", "not-a-number")

        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises((TypeError, ValueError)):
                    RequestTrace.from_mapping(
                        {
                            "started_at": "2026-07-08T12:00:00Z",
                            "input_tokens": invalid_value,
                        }
                    )

    def test_trace_mapping_parses_string_failure_flags(self) -> None:
        successful_trace = RequestTrace.from_mapping(
            {
                "started_at": "2026-07-08T12:00:00Z",
                "failed": "false",
                "timed_out": "0",
            }
        )
        failed_trace = RequestTrace.from_mapping(
            {
                "started_at": "2026-07-08T12:00:00Z",
                "failed": "true",
            }
        )
        error_trace = RequestTrace.from_mapping(
            {
                "started_at": "2026-07-08T12:00:00Z",
                "error": "upstream timeout",
            }
        )

        self.assertFalse(successful_trace.failed)
        self.assertTrue(failed_trace.failed)
        self.assertTrue(error_trace.failed)

    def test_trace_mapping_rejects_unknown_failure_flags(self) -> None:
        with self.assertRaises(ValueError):
            RequestTrace.from_mapping(
                {
                    "started_at": "2026-07-08T12:00:00Z",
                    "failed": "not failed",
                }
            )

    def test_trace_mapping_coerces_concurrency(self) -> None:
        trace = RequestTrace.from_mapping(
            {
                "started_at": "2026-07-08T12:00:00Z",
                "concurrency": "10",
            }
        )

        self.assertEqual(trace.concurrency, 10)

    def test_trace_mapping_rejects_invalid_concurrency(self) -> None:
        invalid_values = ("-1", 1.9, True)

        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaises(ValueError):
                    RequestTrace.from_mapping(
                        {
                            "started_at": "2026-07-08T12:00:00Z",
                            "concurrency": invalid_value,
                        }
                    )


class OperationalMetricsCliTest(unittest.TestCase):
    def test_build_report_accepts_object_payload(self) -> None:
        report = build_report(
            {
                "pricing": {
                    "input_per_million": 2.0,
                    "output_per_million": 8.0,
                },
                "traces": [
                    {
                        "request_started_at": "2026-07-08T12:00:00Z",
                        "first_token_at": "2026-07-08T12:00:00.500Z",
                        "response_completed_at": "2026-07-08T12:00:02Z",
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "concurrency": 5,
                    }
                ],
            }
        )

        self.assertEqual(report["summary"]["request_count"], 1)
        self.assertEqual(report["summary"]["latency"]["p95_ms"], 2000)
        self.assertEqual(report["latency_under_load"]["5"]["count"], 1)

    def test_build_report_accepts_list_payload(self) -> None:
        report = build_report(
            [
                {
                    "started_at": "2026-07-08T12:00:00Z",
                    "completed_at": "2026-07-08T12:00:01Z",
                }
            ]
        )

        self.assertEqual(report["summary"]["request_count"], 1)
        self.assertIsNone(report["summary"]["average_cost_usd"])

    def test_main_writes_output_file(self) -> None:
        payload = {
            "traces": [
                {
                    "started_at": "2026-07-08T12:00:00Z",
                    "completed_at": "2026-07-08T12:00:01Z",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, "input.json")
            output_path = os.path.join(temp_dir, "output.json")
            with open(input_path, "w", encoding="utf-8") as file:
                json.dump(payload, file)

            exit_code = main([input_path, "--output", output_path, "--pretty"])

            self.assertEqual(exit_code, 0)
            with open(output_path, encoding="utf-8") as file:
                report = json.load(file)
            self.assertEqual(report["summary"]["request_count"], 1)

    def test_main_handles_missing_input_without_traceback(self) -> None:
        stderr = StringIO()

        with redirect_stderr(stderr):
            exit_code = main(["does-not-exist.json"])

        self.assertEqual(exit_code, 1)
        self.assertIn("error:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
