from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import json
from math import inf, nan
import os
import tempfile
import unittest

from evalsurfer.interface.cli.metrics import build_report, main
from evalsurfer.metrics.operational.metrics import (
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

    def test_trace_mapping_rejects_out_of_order_timestamps(self) -> None:
        # Clock skew (completion before start) fails fast at the boundary with a
        # clear message, not deep inside summarize().
        with self.assertRaises(ValueError):
            RequestTrace.from_mapping(
                {
                    "started_at": "2026-07-08T12:00:02Z",
                    "completed_at": "2026-07-08T12:00:00Z",
                }
            )
        # A first token before the request start is also rejected.
        with self.assertRaises(ValueError):
            RequestTrace.from_mapping(
                {
                    "started_at": "2026-07-08T12:00:02Z",
                    "first_token_at": "2026-07-08T12:00:00Z",
                    "completed_at": "2026-07-08T12:00:05Z",
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


class NewInferenceMetricComputationTest(unittest.TestCase):
    """Direct assertions on the raw values behind the four new criteria."""

    def _trace(self, **overrides) -> RequestTrace:
        # 200 ms TTFT, 1200 ms end-to-end -> 1000 ms generation window;
        # 101 output tokens -> 100 inter-token intervals.
        base = dict(
            request_started_at=0,
            first_token_at=0.2,
            response_completed_at=1.2,
            input_tokens=1000,
            output_tokens=101,
        )
        base.update(overrides)
        return RequestTrace(**base)

    def test_inter_token_latency_is_generation_over_intervals(self) -> None:
        # 1000 ms generation / (101 - 1) intervals = 10 ms.
        self.assertEqual(OperationalMetrics.inter_token_latency_ms(self._trace()), 10.0)

    def test_inter_token_latency_none_with_one_or_zero_tokens(self) -> None:
        self.assertIsNone(
            OperationalMetrics.inter_token_latency_ms(self._trace(output_tokens=1))
        )
        self.assertIsNone(
            OperationalMetrics.inter_token_latency_ms(self._trace(output_tokens=0))
        )

    def test_inter_token_latency_none_without_first_token(self) -> None:
        self.assertIsNone(
            OperationalMetrics.inter_token_latency_ms(self._trace(first_token_at=None))
        )

    def test_cost_per_million_tokens_is_blended(self) -> None:
        # input 1000*2/1e6 + output 500*8/1e6 = 0.006 over 1500 tokens -> $4/M.
        summary = OperationalMetrics.summarize(
            [self._trace(output_tokens=500)],
            pricing=Pricing(input_per_million=2.0, output_per_million=8.0),
        )
        self.assertAlmostEqual(summary.cost_per_million_tokens or 0.0, 4.0)

    def test_cost_per_million_tokens_none_without_pricing(self) -> None:
        self.assertIsNone(OperationalMetrics.summarize([self._trace()]).cost_per_million_tokens)

    def test_tail_latency_ratio_is_one_for_a_single_request(self) -> None:
        # One sample: p99 == p50, so the tail ratio is exactly 1.0.
        self.assertEqual(OperationalMetrics.summarize([self._trace()]).tail_latency_ratio, 1.0)

    def test_tail_latency_ratio_is_p99_over_nearest_rank_p50(self) -> None:
        values = [100, 200, 300, 400, 5000]  # a heavy tail
        traces = [
            RequestTrace(request_started_at=0, response_completed_at=t / 1000.0)
            for t in values
        ]
        summary = OperationalMetrics.summarize(traces)
        assert summary.latency is not None and summary.tail_latency_ratio is not None
        p50 = OperationalMetrics.percentile(values, 50)
        self.assertEqual(summary.tail_latency_ratio, summary.latency.p99_ms / p50)
        self.assertGreater(summary.tail_latency_ratio, 1.0)

    def test_tail_latency_ratio_uses_nearest_rank_p50_not_interpolated_median(self) -> None:
        # Even-sized sample: statistics.median interpolates the two middle values
        # (250), but the nearest-rank P50 is 200. The ratio must divide by the
        # nearest-rank P50 so it is consistent with the nearest-rank P99.
        values = [100, 200, 300, 400]
        traces = [
            RequestTrace(request_started_at=0, response_completed_at=t / 1000.0)
            for t in values
        ]
        summary = OperationalMetrics.summarize(traces)
        assert summary.latency is not None and summary.tail_latency_ratio is not None
        p50 = OperationalMetrics.percentile(values, 50)
        self.assertEqual(p50, 200)
        self.assertNotEqual(summary.latency.median_ms, p50)  # median interpolates to 250
        self.assertEqual(summary.tail_latency_ratio, summary.latency.p99_ms / p50)

    def test_itl_stats_present_when_measurable_and_absent_otherwise(self) -> None:
        self.assertIsNotNone(OperationalMetrics.summarize([self._trace()]).itl)
        self.assertIsNone(
            OperationalMetrics.summarize([self._trace(output_tokens=1)]).itl
        )

    def test_output_throughput_is_tokens_per_second_over_the_summary(self) -> None:
        # 500 tokens over a 1000 ms generation window -> 500 tok/s (the value the
        # output_throughput criterion is scored against).
        summary = OperationalMetrics.summarize([self._trace(output_tokens=500)])
        self.assertAlmostEqual(summary.average_tokens_per_second or 0.0, 500.0)


if __name__ == "__main__":
    unittest.main()
