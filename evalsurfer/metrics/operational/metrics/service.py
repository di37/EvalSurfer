"""The operational-metric calculations over request traces.

:class:`OperationalMetrics` groups the stateless calculations (latency, TTFT,
throughput, cost, failure rate, percentiles) into a single cohesive namespace.
All methods are static: the calculations carry no per-instance state, operate on
the value objects in :mod:`evalsurfer.metrics.operational.metrics.models`, and
make no model calls. Magic values are sourced from :mod:`constants`.
"""

from __future__ import annotations

from math import ceil, isfinite
from statistics import mean, median
from typing import Iterable, Sequence

import evalsurfer.constants as constants
from evalsurfer.metrics.operational.metrics.helpers import (
    coerce_non_negative_int,
    duration_ms,
)
from evalsurfer.metrics.operational.metrics.models import (
    LatencyStats,
    OperationalSummary,
    Pricing,
    RequestTrace,
)


class OperationalMetrics:
    """Stateless operational-metric calculations over request traces.

    All methods are static: the calculations carry no per-instance state, so the
    class is a cohesive namespace rather than something to instantiate.
    """

    @staticmethod
    def end_to_end_latency_ms(trace: RequestTrace) -> float | None:
        """Total time from user request start to final response completion.

        Args:
            trace: The request trace.

        Returns:
            The latency in milliseconds, or ``None`` if the response never
            completed.
        """
        if trace.response_completed_at is None:
            return None
        return duration_ms(trace.request_started_at, trace.response_completed_at)

    @staticmethod
    def ttft_ms(trace: RequestTrace) -> float | None:
        """Time to first token for streaming responses.

        Args:
            trace: The request trace.

        Returns:
            The time to first token in milliseconds, or ``None`` if no first
            token was recorded.
        """
        if trace.first_token_at is None:
            return None
        return duration_ms(trace.request_started_at, trace.first_token_at)

    @staticmethod
    def generation_duration_ms(trace: RequestTrace) -> float | None:
        """Time from first token to response completion.

        Args:
            trace: The request trace.

        Returns:
            The generation duration in milliseconds, or ``None`` if either the
            first token or the completion timestamp is missing.
        """
        if trace.first_token_at is None or trace.response_completed_at is None:
            return None
        return duration_ms(trace.first_token_at, trace.response_completed_at)

    @staticmethod
    def tokens_per_second(trace: RequestTrace) -> float | None:
        """Output generation speed after the first token arrives.

        Args:
            trace: The request trace.

        Returns:
            The output tokens per second, or ``None`` if the generation window or
            output token count is not positive.
        """
        generation_ms = OperationalMetrics.generation_duration_ms(trace)
        if generation_ms is None or generation_ms == 0 or trace.output_tokens <= 0:
            return None
        return trace.output_tokens / (
            generation_ms / constants.MILLISECONDS_PER_SECOND
        )

    @staticmethod
    def inter_token_latency_ms(trace: RequestTrace) -> float | None:
        """Average time between successive streamed output tokens (excludes TTFT).

        Inter-token latency (ITL) is the generation window divided by the number
        of inter-token intervals (``output_tokens - 1``). It is the latency view
        of streaming speed; ``TPS ≈ 1000 / ITL_ms``.

        Args:
            trace: The request trace.

        Returns:
            The inter-token latency in milliseconds, or ``None`` when the
            generation window is unavailable or fewer than two tokens were
            produced (there is then no interval to measure).
        """
        generation_ms = OperationalMetrics.generation_duration_ms(trace)
        if generation_ms is None or trace.output_tokens <= 1:
            return None
        return generation_ms / (trace.output_tokens - 1)

    @staticmethod
    def cost_per_request_usd(
        input_tokens: int,
        output_tokens: int,
        pricing: Pricing,
    ) -> float:
        """Calculate request cost from token counts and per-million pricing.

        Args:
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            pricing: Per-million-token input and output prices.

        Returns:
            The request cost in US dollars.

        Raises:
            ValueError: If a token count or pricing value is negative, or if a
                pricing value is not finite.
            TypeError: If a token count has an unsupported type.
        """
        input_tokens = coerce_non_negative_int(input_tokens, "input_tokens")
        output_tokens = coerce_non_negative_int(output_tokens, "output_tokens")
        if pricing.input_per_million < 0 or pricing.output_per_million < 0:
            raise ValueError("pricing values must be non-negative")
        if not isfinite(pricing.input_per_million) or not isfinite(
            pricing.output_per_million
        ):
            raise ValueError("pricing values must be finite")

        input_cost = (
            input_tokens / constants.TOKENS_PER_MILLION * pricing.input_per_million
        )
        output_cost = (
            output_tokens / constants.TOKENS_PER_MILLION * pricing.output_per_million
        )
        return input_cost + output_cost

    @staticmethod
    def token_efficiency(
        useful_output_tokens: int,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Ratio of useful output tokens to all tokens spent.

        Args:
            useful_output_tokens: Output tokens that contributed to the answer.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            The efficiency ratio, or ``0.0`` when no tokens were spent.

        Raises:
            ValueError: If any token count is negative.
        """
        if useful_output_tokens < 0 or input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts must be non-negative")

        total_tokens = input_tokens + output_tokens
        if total_tokens == 0:
            return 0.0
        return min(useful_output_tokens, output_tokens) / total_tokens

    @staticmethod
    def failure_rate(traces: Sequence[RequestTrace]) -> float:
        """Fraction of requests that failed, timed out, or returned bad output.

        Args:
            traces: The request traces.

        Returns:
            The failure rate in ``[0, 1]``, or ``0.0`` when there are no traces.
        """
        if not traces:
            return 0.0
        return sum(1 for trace in traces if trace.failed) / len(traces)

    @staticmethod
    def percentile(values: Sequence[float], percentile_value: float) -> float:
        """Nearest-rank percentile for latency SLO reporting.

        Args:
            values: The distribution to summarize.
            percentile_value: The percentile to compute, between 0 and 100.

        Returns:
            The value at the requested percentile.

        Raises:
            ValueError: If ``values`` is empty or ``percentile_value`` is out of
                range.
        """
        if not values:
            raise ValueError("values must not be empty")
        if not 0 <= percentile_value <= 100:
            raise ValueError("percentile_value must be between 0 and 100")

        ordered = sorted(values)
        rank = ceil((percentile_value / 100) * len(ordered))
        return ordered[max(rank - 1, 0)]

    @staticmethod
    def latency_stats(values_ms: Iterable[float]) -> LatencyStats | None:
        """Compute common latency summary statistics.

        Args:
            values_ms: Latency samples in milliseconds.

        Returns:
            The :class:`LatencyStats`, or ``None`` when there are no samples.
        """
        values = list(values_ms)
        if not values:
            return None

        p90, p95, p99 = constants.DEFAULT_PERCENTILES
        return LatencyStats(
            count=len(values),
            min_ms=min(values),
            max_ms=max(values),
            mean_ms=mean(values),
            median_ms=median(values),
            p90_ms=OperationalMetrics.percentile(values, p90),
            p95_ms=OperationalMetrics.percentile(values, p95),
            p99_ms=OperationalMetrics.percentile(values, p99),
        )

    @staticmethod
    def latency_under_load(
        traces: Sequence[RequestTrace],
    ) -> dict[int, LatencyStats]:
        """Group end-to-end latency statistics by concurrency level.

        Args:
            traces: The request traces; traces without a concurrency level or a
                completed response are skipped.

        Returns:
            A mapping of concurrency level to its :class:`LatencyStats`, ordered
            by ascending concurrency.
        """
        grouped: dict[int, list[float]] = {}
        for trace in traces:
            if trace.concurrency is None:
                continue
            latency = OperationalMetrics.end_to_end_latency_ms(trace)
            if latency is None:
                continue
            grouped.setdefault(trace.concurrency, []).append(latency)

        return {
            concurrency: stats
            for concurrency, values in sorted(grouped.items())
            if (stats := OperationalMetrics.latency_stats(values)) is not None
        }

    @staticmethod
    def summarize(
        traces: Sequence[RequestTrace],
        pricing: Pricing | None = None,
    ) -> OperationalSummary:
        """Summarize latency, TTFT, cost, throughput, and failure rate.

        Args:
            traces: The request traces to summarize.
            pricing: Optional token pricing; when provided, per-request and total
                costs are computed.

        Returns:
            The aggregated :class:`OperationalSummary`.
        """
        latencies = [
            latency
            for trace in traces
            if (latency := OperationalMetrics.end_to_end_latency_ms(trace)) is not None
        ]
        ttfts = [
            latency
            for trace in traces
            if (latency := OperationalMetrics.ttft_ms(trace)) is not None
        ]
        token_rates = [
            rate
            for trace in traces
            if (rate := OperationalMetrics.tokens_per_second(trace)) is not None
        ]

        itls = [
            value
            for trace in traces
            if (value := OperationalMetrics.inter_token_latency_ms(trace)) is not None
        ]

        costs = None
        if pricing is not None:
            costs = [
                OperationalMetrics.cost_per_request_usd(
                    trace.input_tokens, trace.output_tokens, pricing
                )
                for trace in traces
            ]

        latency = OperationalMetrics.latency_stats(latencies)
        total_cost = sum(costs) if costs else None
        total_tokens = sum(trace.input_tokens + trace.output_tokens for trace in traces)
        cost_per_million = (
            total_cost / total_tokens * constants.TOKENS_PER_MILLION
            if total_cost is not None and total_tokens > 0
            else None
        )
        # Tail ratio is documented as P99/P50. Use a nearest-rank P50 (not the
        # interpolated ``statistics.median`` in ``median_ms``) so it matches the
        # nearest-rank P99 computed above -- otherwise even-sized samples divide
        # a nearest-rank P99 by an interpolated P50.
        tail_ratio = None
        if latency is not None:
            p50 = OperationalMetrics.percentile(latencies, 50)
            if p50 > 0:
                tail_ratio = latency.p99_ms / p50

        failure_count = sum(1 for trace in traces if trace.failed)
        return OperationalSummary(
            request_count=len(traces),
            success_count=len(traces) - failure_count,
            failure_count=failure_count,
            failure_rate=OperationalMetrics.failure_rate(traces),
            latency=latency,
            ttft=OperationalMetrics.latency_stats(ttfts),
            average_cost_usd=mean(costs) if costs else None,
            total_cost_usd=total_cost,
            average_tokens_per_second=mean(token_rates) if token_rates else None,
            itl=OperationalMetrics.latency_stats(itls),
            cost_per_million_tokens=cost_per_million,
            tail_latency_ratio=tail_ratio,
        )
