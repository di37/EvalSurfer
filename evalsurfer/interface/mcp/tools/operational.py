"""Operational tools — latency/throughput/cost metrics and SLO scoring."""

from __future__ import annotations

from evalsurfer.interface.cli import metrics as metrics_cli
from evalsurfer.interface.mcp import models as m
from evalsurfer.interface.mcp.instance import mcp
from evalsurfer.metrics.operational.metrics import OperationalMetrics, Pricing as CorePricing
from evalsurfer.metrics.operational.slo import OperationalScorer


@mcp.tool()
def metrics(payload: m.TracesPayload) -> dict:
    """Operational metrics from request traces: latency, TTFT, ITL, throughput, cost,
    failure rate, and latency-under-load."""
    return metrics_cli.build_report(payload.model_dump(exclude_none=True))


@mcp.tool()
def operational_score(payload: m.TracesPayload, slo: m.SLO) -> dict:
    """Auto-score the operational pillar 1-5 by comparing measured metrics to an SLO."""
    return OperationalScorer(slo.model_dump(exclude_none=True)).score(
        payload.model_dump(exclude_none=True)
    )


@mcp.tool()
def cost_per_request(input_tokens: int, output_tokens: int, pricing: m.Pricing) -> float:
    """Per-request token cost in USD from token counts and pricing."""
    return OperationalMetrics.cost_per_request_usd(
        input_tokens, output_tokens, CorePricing(**pricing.model_dump())
    )


@mcp.tool()
def token_efficiency(useful_output_tokens: int, input_tokens: int, output_tokens: int) -> float:
    """Useful-output ratio against total tokens spent (0-1)."""
    return OperationalMetrics.token_efficiency(useful_output_tokens, input_tokens, output_tokens)
