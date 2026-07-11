"""Ecosystem adapter tools — import RAGAS / promptfoo / OTel / LangSmith data."""

from __future__ import annotations

from evalsurfer.interface.adapters import (
    LangSmithAdapter,
    OtelAdapter,
    PromptfooAdapter,
    RagasAdapter,
)
from evalsurfer.interface.mcp.instance import mcp


@mcp.tool()
def adapter_ragas(metrics: dict[str, float]) -> list[dict]:
    """Import RAGAS metrics (0-1) as EvalSurfer rubric criteria (1-5)."""
    return RagasAdapter.to_criteria(metrics)


@mcp.tool()
def adapter_promptfoo(results: dict | list) -> dict:
    """Import promptfoo results as a minimal EvalSurfer report."""
    return PromptfooAdapter.to_report(results)


@mcp.tool()
def adapter_otel(spans: list[dict]) -> list[dict]:
    """Import OpenTelemetry spans as EvalSurfer request traces."""
    return OtelAdapter.to_traces(spans)


@mcp.tool()
def adapter_langsmith(runs: list[dict]) -> list[dict]:
    """Import LangSmith runs as EvalSurfer request traces."""
    return LangSmithAdapter.to_traces(runs)
