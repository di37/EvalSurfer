"""Operational metrics and SLO auto-scoring.

Unit conversions, percentile defaults, and the SLO field definitions used to map
measured operational metrics onto 1-5 criterion scores.
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Operational metrics
# --------------------------------------------------------------------------- #
MILLISECONDS_PER_SECOND: Final = 1000
TOKENS_PER_MILLION: Final = 1_000_000
# Numeric timestamps above this are treated as epoch milliseconds, not seconds.
EPOCH_MILLISECONDS_THRESHOLD: Final = 1_000_000_000_000
DEFAULT_PERCENTILES: Final = (90, 95, 99)

# --------------------------------------------------------------------------- #
# Operational SLO auto-scoring: map measured metrics to 1-5 criterion scores
# --------------------------------------------------------------------------- #
SLO_P95_LATENCY_MS: Final = "p95_latency_ms"
SLO_TTFT_MS: Final = "ttft_ms"
SLO_MAX_FAILURE_RATE: Final = "max_failure_rate"
SLO_MAX_COST_USD: Final = "max_cost_usd"
SLO_ITL_MS: Final = "itl_ms"
SLO_MIN_TOKENS_PER_SECOND: Final = "min_tokens_per_second"
SLO_MAX_P99_P50_RATIO: Final = "max_p99_p50_ratio"
SLO_MAX_COST_PER_MILLION_USD: Final = "max_cost_per_million_usd"
SLO_FIELDS: Final = (
    SLO_P95_LATENCY_MS,
    SLO_TTFT_MS,
    SLO_MAX_FAILURE_RATE,
    SLO_MAX_COST_USD,
    SLO_ITL_MS,
    SLO_MIN_TOKENS_PER_SECOND,
    SLO_MAX_P99_P50_RATIO,
    SLO_MAX_COST_PER_MILLION_USD,
)

# Operational criterion id -> the SLO field it is scored against.
OPERATIONAL_CRITERION_SLO: Final = {
    "end_to_end_latency": SLO_P95_LATENCY_MS,
    "time_to_first_token": SLO_TTFT_MS,
    "cost_per_request": SLO_MAX_COST_USD,
    "error_failure_rate": SLO_MAX_FAILURE_RATE,
    "latency_under_load": SLO_P95_LATENCY_MS,
    "inter_token_latency": SLO_ITL_MS,
    "output_throughput": SLO_MIN_TOKENS_PER_SECOND,
    "tail_latency": SLO_MAX_P99_P50_RATIO,
    "cost_per_million_tokens": SLO_MAX_COST_PER_MILLION_USD,
}
# measured/target ratio (lower is better) -> score. (max_ratio, score) ascending;
# anything above the last band scores 1.
SLO_SCORE_BANDS: Final = ((0.5, 5), (0.8, 4), (1.0, 3), (1.25, 2))

# Operational criteria where a HIGHER measured value is better (throughput):
# scored by the target/measured ratio so exceeding the target scores highest.
HIGHER_IS_BETTER_OPERATIONAL_CRITERIA: Final = frozenset({"output_throughput"})

__all__ = [
    "MILLISECONDS_PER_SECOND",
    "TOKENS_PER_MILLION",
    "EPOCH_MILLISECONDS_THRESHOLD",
    "DEFAULT_PERCENTILES",
    "SLO_P95_LATENCY_MS",
    "SLO_TTFT_MS",
    "SLO_MAX_FAILURE_RATE",
    "SLO_MAX_COST_USD",
    "SLO_ITL_MS",
    "SLO_MIN_TOKENS_PER_SECOND",
    "SLO_MAX_P99_P50_RATIO",
    "SLO_MAX_COST_PER_MILLION_USD",
    "SLO_FIELDS",
    "OPERATIONAL_CRITERION_SLO",
    "SLO_SCORE_BANDS",
    "HIGHER_IS_BETTER_OPERATIONAL_CRITERIA",
]
