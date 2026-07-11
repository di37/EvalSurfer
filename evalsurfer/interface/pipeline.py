"""Interface-layer evaluation pipeline (full CIMAA run).

Wires Metrics (operational auto-scoring) and Analysis (diagnostics) around
Core :class:`~evalsurfer.core.evaluate.Evaluator`. This is the entry point CLI
and MCP ``evaluate`` use — Core never imports Metrics or Analysis.
"""

from __future__ import annotations

from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.analysis.diagnostics.bundle import DiagnosticsBundle
from evalsurfer.core.evaluate import Evaluator
from evalsurfer.core.planner import Signals
from evalsurfer.metrics.operational.metrics import OperationalMetrics, Pricing, RequestTrace
from evalsurfer.metrics.operational.slo import OperationalScorer

__all__ = ["evaluate"]

_WITHIN_SLO_MIN_SCORE = 3
_LATENCY_CRITERION_ID = "end_to_end_latency"


def evaluate(request: Mapping[str, Any]) -> dict[str, Any]:
    """Run the full evaluation pipeline: Metrics enrich → Core assemble → Analysis diagnose.

    Args:
        request: Evaluation request (sample, scores, optional traces/slo/before).

    Returns:
        A complete report including ``diagnostics``.

    Raises:
        TypeError: If ``request`` is not a mapping.
    """
    if not isinstance(request, Mapping):
        raise TypeError("request must be a mapping")

    enriched = _enrich_with_operational(dict(request))
    report = Evaluator.evaluate(enriched)

    sample = enriched.get("sample", enriched)
    signals = Signals.from_sample(sample)
    before = enriched.get("before")
    report["diagnostics"] = DiagnosticsBundle.run(
        report, before=before if isinstance(before, Mapping) else None, signals=signals
    )
    return report


def _enrich_with_operational(request: dict[str, Any]) -> dict[str, Any]:
    """Auto-score operational criteria from traces and attach decide() inputs."""
    payload = request.get("traces")
    if payload is None:
        return request

    scored = OperationalScorer(request.get("slo")).score(payload)
    flat = Evaluator.flatten_scores(request.get("scores"))
    evidence = dict(request.get("evidence") or {})
    for criterion in scored["criteria"]:
        cid = criterion.get("id")
        score = criterion.get("score")
        if isinstance(cid, str) and isinstance(score, int) and not isinstance(score, bool):
            flat[cid] = score
        if isinstance(cid, str) and criterion.get("evidence"):
            evidence[cid] = criterion["evidence"]
    request["scores"] = flat
    request["evidence"] = evidence

    traces, pricing = _parse_traces(payload)
    summary = OperationalMetrics.summarize(traces, pricing=pricing)
    request["failure_rate"] = summary.failure_rate
    request["p95_within_slo"] = _p95_within_slo(scored["criteria"], request.get("slo"))
    return request


def _parse_traces(payload: Any) -> tuple[list[RequestTrace], Pricing | None]:
    """Parse a trace payload into request traces and optional pricing."""
    pricing = None
    if isinstance(payload, Mapping):
        trace_items = payload.get("traces") or []
        price = payload.get("pricing")
        if isinstance(price, Mapping):
            pricing = Pricing(
                input_per_million=float(price["input_per_million"]),
                output_per_million=float(price["output_per_million"]),
            )
    else:
        trace_items = payload
    return [RequestTrace.from_mapping(item) for item in trace_items], pricing


def _p95_within_slo(criteria: list[dict[str, Any]], slo: Any) -> bool | None:
    """Whether measured P95 latency sits within the SLO, if both are known."""
    if not isinstance(slo, Mapping) or constants.SLO_P95_LATENCY_MS not in slo:
        return None
    for criterion in criteria:
        if criterion.get("id") == _LATENCY_CRITERION_ID:
            score = criterion.get("score")
            if isinstance(score, int) and not isinstance(score, bool):
                return score >= _WITHIN_SLO_MIN_SCORE
    return None
