"""Operational tools — latency/throughput/cost metrics and SLO scoring."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from evalsurfer.interface.mcp import models as m
from evalsurfer.interface.mcp.instance import mcp
from evalsurfer.metrics.operational.metrics import OperationalMetrics, Pricing, RequestTrace
from evalsurfer.metrics.operational.slo import OperationalScorer


def _to_dict(value: Any) -> Any:
    """Recursively convert dataclasses to plain dicts."""
    if is_dataclass(value):
        return {key: _to_dict(nested) for key, nested in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _to_dict(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_to_dict(item) for item in value]
    return value


@mcp.tool()
def metrics(payload: m.TracesPayload) -> dict:
    """Operational metrics from request traces: latency, TTFT, ITL, throughput, cost,
    failure rate, and latency-under-load."""
    data = payload.model_dump(exclude_none=True)
    traces = [RequestTrace.from_mapping(item) for item in data.get("traces") or []]
    pricing = None
    price = data.get("pricing")
    if isinstance(price, dict):
        pricing = Pricing(
            input_per_million=float(price["input_per_million"]),
            output_per_million=float(price["output_per_million"]),
        )
    summary = OperationalMetrics.summarize(traces, pricing=pricing)
    return {
        "summary": _to_dict(summary),
        "latency_under_load": _to_dict(OperationalMetrics.latency_under_load(traces)),
    }


@mcp.tool()
def operational_score(payload: m.TracesPayload, slo: m.SLO) -> dict:
    """Auto-score the operational category 1-5 by comparing measured metrics to an SLO."""
    return OperationalScorer(slo.model_dump(exclude_none=True)).score(
        payload.model_dump(exclude_none=True)
    )


@mcp.tool()
def cost_per_request(input_tokens: int, output_tokens: int, pricing: m.Pricing) -> float:
    """Per-request token cost in USD from token counts and pricing."""
    return OperationalMetrics.cost_per_request_usd(
        input_tokens, output_tokens, Pricing(**pricing.model_dump())
    )


@mcp.tool()
def token_efficiency(useful_output_tokens: int, input_tokens: int, output_tokens: int) -> float:
    """Useful-output ratio against total tokens spent (0-1)."""
    return OperationalMetrics.token_efficiency(useful_output_tokens, input_tokens, output_tokens)
