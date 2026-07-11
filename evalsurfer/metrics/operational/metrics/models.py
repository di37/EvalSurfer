"""Operational value objects -- immutable, provider-agnostic containers.

The frozen dataclasses that carry operational data: :class:`Pricing`,
:class:`RequestTrace` (plus its :meth:`RequestTrace.from_mapping` parser),
:class:`LatencyStats`, and :class:`OperationalSummary`. The stateless
calculations that consume them live in
:mod:`evalsurfer.metrics.operational.metrics.service`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from evalsurfer.metrics.operational.metrics.helpers import (
    Timestamp,
    coerce_non_negative_int,
    coerce_optional_concurrency,
    get_nested,
    parse_bool,
    validate_timestamp_order,
)


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
            ValueError: If the request start timestamp is missing, the
                timestamps are out of chronological order, or a token count,
                failure flag, or concurrency value is invalid.
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
        first_token_at = get_nested(
            data,
            ("first_token_at", "ttft_at", "timing.first_token_at"),
        )

        # Fail fast at the boundary: a log record with out-of-order timestamps is
        # caught here with a clear message rather than raising deep inside
        # OperationalMetrics.summarize.
        validate_timestamp_order(started_at, first_token_at, completed_at)

        return cls(
            request_started_at=started_at,
            response_completed_at=completed_at,
            first_token_at=first_token_at,
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
    itl: LatencyStats | None
    cost_per_million_tokens: float | None
    tail_latency_ratio: float | None
