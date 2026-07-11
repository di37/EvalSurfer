"""Interface-layer MCP tools — full CIMAA evaluate pipeline."""

from __future__ import annotations

from evalsurfer.interface.pipeline import evaluate as run_evaluate
from evalsurfer.interface.mcp import models as m
from evalsurfer.interface.mcp.instance import mcp


@mcp.tool()
def evaluate(request: m.EvaluateRequest) -> dict:
    """Full CIMAA run: Metrics ops enrich → Core assemble → Analysis diagnostics."""
    return run_evaluate(request.model_dump(exclude_none=True))
