"""Operational metrics for AI application evaluations.

The value objects (:class:`Pricing`, :class:`RequestTrace`, :class:`LatencyStats`,
:class:`OperationalSummary`) are immutable, provider-agnostic containers: pass
timestamps and token counts from your API logs, tracing system, or streaming
client instrumentation. :class:`OperationalMetrics` groups the stateless
calculations (latency, TTFT, throughput, cost, failure rate, percentiles) into a
single cohesive namespace.

Everything here is pure and standard-library-only -- no model calls. Magic
values are sourced from :mod:`constants`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil, isfinite
from statistics import mean, median
from typing import Any, Iterable, Mapping, Sequence

import evalsurfer.constants as constants

__all__ = [
    "Timestamp",
    "Pricing",
    "RequestTrace",
    "LatencyStats",
    "OperationalSummary",
    "OperationalMetrics",
    "to_datetime",
    "duration_ms",
    "get_nested",
    "coerce_non_negative_int",
    "coerce_optional_concurrency",
    "parse_bool",
]

Timestamp = datetime | int | float | str


@dataclass(frozen=True)
class Pricing:
    """Token pricing in dollars per one million tokens."""

    input_per_million: float
    output_per_million: float


@dataclass(frozen=True)
class RequestTrace:
    """Minimal trace for a single AI request."""

    request_started_at: Timestamp
    response_completed_at: Timestamp | None = None
    first_token_at: Timestamp | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    failed: bool = False
    concurrency: int | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RequestTrace":
        """Build a trace from common logging or API response field names.

        Args:
            data: A request record. Timestamps, token counts, failure flags, and
                concurrency are read from the first present of several common
                aliases (e.g. ``prompt_tokens`` or ``usage.input_tokens``).

        Returns:
            The parsed :class:`RequestTrace`.

        Raises:
            ValueError: If the request start timestamp is missing, or if a token
                count, failure flag, or concurrency value is invalid.
            TypeError: If a token count has an unsupported type.
        """
        started_at = get_nested(
            data,
            ("request_started_at", "started_at", "start_time", "timing.start_time"),
        )
        completed_at = get_nested(
            data,
            (
                "response_completed_at",
                "completed_at",
                "end_time",
                "timing.end_time",
            ),
        )

        if started_at is None:
            raise ValueError("request start timestamp is required")

        input_tokens = get_nested(
            data,
            (
                "input_tokens",
                "prompt_tokens",
                "usage.input_tokens",
                "usage.prompt_tokens",
            ),
        )
        output_tokens = get_nested(
            data,
            (
                "output_tokens",
                "completion_tokens",
                "usage.output_tokens",
                "usage.completion_tokens",
            ),
        )
        error = get_nested(data, ("error",))
        failed = parse_bool(get_nested(data, ("failed",)), "failed") or parse_bool(
            get_nested(data, ("timed_out",)), "timed_out"
        )
        concurrency = get_nested(data, ("concurrency", "load.concurrency"))

        return cls(
            request_started_at=started_at,
            response_completed_at=completed_at,
            first_token_at=get_nested(
                data,
                ("first_token_at", "ttft_at", "timing.first_token_at"),
            ),
            input_tokens=coerce_non_negative_int(input_tokens, "input_tokens"),
            output_tokens=coerce_non_negative_int(output_tokens, "output_tokens"),
            failed=failed or bool(error),
            concurrency=coerce_optional_concurrency(concurrency),
        )


@dataclass(frozen=True)
class LatencyStats:
    """Summary statistics for a latency distribution."""

    count: int
    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    p90_ms: float
    p95_ms: float
    p99_ms: float


@dataclass(frozen=True)
class OperationalSummary:
    """Operational summary across many request traces."""

    request_count: int
    success_count: int
    failure_count: int
    failure_rate: float
    latency: LatencyStats | None
    ttft: LatencyStats | None
    average_cost_usd: float | None
    total_cost_usd: float | None
    average_tokens_per_second: float | None


def to_datetime(value: Timestamp) -> datetime:
    """Convert numeric epoch timestamps or ISO strings to timezone-aware UTC.

    Args:
        value: A ``datetime``, an epoch value in seconds or milliseconds, or an
            ISO-8601 string.

    Returns:
        The timezone-aware UTC ``datetime``.

    Raises:
        TypeError: If ``value`` is not a supported timestamp type.
    """
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        # Values above the epoch-milliseconds threshold are treated as ms.
        seconds = (
            value / constants.MILLISECONDS_PER_SECOND
            if value > constants.EPOCH_MILLISECONDS_THRESHOLD
            else value
        )
        return datetime.fromtimestamp(seconds, tz=timezone.utc)

    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    raise TypeError(f"Unsupported timestamp type: {type(value).__name__}")


def duration_ms(start: Timestamp, end: Timestamp) -> float:
    """Calculate elapsed milliseconds between two timestamps.

    Args:
        start: The starting timestamp.
        end: The ending timestamp.

    Returns:
        The elapsed time in milliseconds.

    Raises:
        ValueError: If ``end`` is earlier than ``start``.
    """
    elapsed = (
        (to_datetime(end) - to_datetime(start)).total_seconds()
        * constants.MILLISECONDS_PER_SECOND
    )
    if elapsed < 0:
        raise ValueError("end timestamp must be greater than or equal to start")
    return elapsed


def get_nested(data: Mapping[str, Any], paths: Sequence[str]) -> Any:
    """Fetch the first present nested value from dot-separated paths.

    Args:
        data: The mapping to search.
        paths: Dot-separated key paths tried in order.

    Returns:
        The first resolved value, or ``None`` if no path is present.
    """
    for path in paths:
        current: Any = data
        for key in path.split("."):
            if not isinstance(current, Mapping) or key not in current:
                break
            current = current[key]
        else:
            return current
    return None


def coerce_non_negative_int(value: Any, field_name: str) -> int:
    """Parse integer-like values and reject invalid or negative values.

    Args:
        value: The raw value (``None``, int, whole-number float, or digit string).
        field_name: Name used in error messages.

    Returns:
        The parsed non-negative integer (``0`` when ``value`` is ``None``).

    Raises:
        ValueError: If the value is a boolean, non-integer, or negative.
        TypeError: If the value has an unsupported type.
    """
    if value is None:
        return 0

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer, not a boolean")

    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        if not isfinite(value) or not value.is_integer():
            raise ValueError(f"{field_name} must be an integer")
        parsed = int(value)
    elif isinstance(value, str):
        normalized = value.strip()
        if not normalized or not normalized.lstrip("-").isdigit():
            raise ValueError(f"{field_name} must be an integer")
        parsed = int(normalized)
    else:
        raise TypeError(f"{field_name} must be an integer")

    if parsed < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return parsed


def coerce_optional_concurrency(value: Any) -> int | None:
    """Parse optional concurrency values from logs.

    Args:
        value: The raw concurrency value, or ``None`` when absent.

    Returns:
        The positive concurrency level, or ``None`` when ``value`` is ``None``.

    Raises:
        ValueError: If the concurrency is not a positive integer.
        TypeError: If the value has an unsupported type.
    """
    if value is None:
        return None

    concurrency = coerce_non_negative_int(value, "concurrency")
    if concurrency == 0:
        raise ValueError("concurrency must be greater than zero")
    return concurrency


def parse_bool(value: Any, field_name: str = "boolean value") -> bool:
    """Parse common boolean values from logs without treating 'false' as true.

    Args:
        value: The raw value (``None``, bool, finite number, or boolean-like
            string such as ``"true"`` or ``"off"``).
        field_name: Name used in error messages.

    Returns:
        The parsed boolean (``False`` when ``value`` is ``None``).

    Raises:
        ValueError: If a numeric value is non-finite or a string is not
            boolean-like.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if not isfinite(value):
            raise ValueError(f"{field_name} must be finite")
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "0", "false", "no", "n", "off"}:
            return False
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        raise ValueError(f"{field_name} must be boolean-like")
    return bool(value)


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

        costs = None
        if pricing is not None:
            costs = [
                OperationalMetrics.cost_per_request_usd(
                    trace.input_tokens, trace.output_tokens, pricing
                )
                for trace in traces
            ]

        failure_count = sum(1 for trace in traces if trace.failed)
        return OperationalSummary(
            request_count=len(traces),
            success_count=len(traces) - failure_count,
            failure_count=failure_count,
            failure_rate=OperationalMetrics.failure_rate(traces),
            latency=OperationalMetrics.latency_stats(latencies),
            ttft=OperationalMetrics.latency_stats(ttfts),
            average_cost_usd=mean(costs) if costs else None,
            total_cost_usd=sum(costs) if costs else None,
            average_tokens_per_second=mean(token_rates) if token_rates else None,
        )
