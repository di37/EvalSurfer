"""EvalSurfer MCP server — every deterministic function as a tool.

This is the on-thesis interface. The harness LLM (your coding agent) is the
**judge**; it calls these tools for every part of an evaluation that must be
**deterministic**. No external model is ever called — the judgment stays in the
agent, the measurement is these tools. The ``SKILL.md`` workflow tells the agent
which tool to reach for.

Importing the tool functions below runs each tool module's ``@mcp.tool()``
decorators, registering them on the shared :data:`evalsurfer.mcp.instance.mcp`
server, and re-exports every tool as an attribute of this module (so
``server.rubric`` and friends are callable directly). Tool inputs use pydantic
models (:mod:`evalsurfer.mcp.models`) so each tool has a clean, validated schema.
Optional: requires ``pip install "evalsurfer[mcp]"``. The core ``evalsurfer``
package never imports ``mcp`` or ``pydantic`` — only this subpackage does — so the
package stays zero-dependency.

Run it (stdio transport):

    evalsurfer-mcp
"""

from __future__ import annotations

from evalsurfer.mcp.instance import mcp
from evalsurfer.mcp.tools.adapters import (
    adapter_langsmith,
    adapter_otel,
    adapter_promptfoo,
    adapter_ragas,
)
from evalsurfer.mcp.tools.calibration import (
    calibrate,
    calibrate_one,
    cohen_kappa,
    fleiss_kappa,
    krippendorff_alpha,
    reference_calibrate,
)
from evalsurfer.mcp.tools.core import (
    coverage,
    decide,
    evaluate,
    gate,
    guardrail_gate,
    plan,
    rubric,
    score_overall,
    score_pillar,
    score_report,
    validate_report,
)
from evalsurfer.mcp.tools.dataset import (
    dataset_contamination,
    dataset_coverage,
    dataset_diff,
    dataset_from_traces,
)
from evalsurfer.mcp.tools.diagnostics import (
    build_evidence,
    diagnose,
    explain,
    failure_map,
    golden_set,
    industry_profile,
    industry_profiles,
    maturity,
    personas,
    regression_diff,
    review_gate,
    root_cause,
)
from evalsurfer.mcp.tools.operational import (
    cost_per_request,
    metrics,
    operational_score,
    token_efficiency,
)
from evalsurfer.mcp.tools.quality import (
    match_metrics,
    retrieval_metrics,
    text_metrics,
)
from evalsurfer.mcp.tools.safety import (
    redteam_check,
    redteam_template,
    trajectory,
)

__all__ = [
    "mcp",
    "main",
    # rubric & scope
    "rubric",
    "plan",
    "coverage",
    # scoring
    "score_pillar",
    "score_overall",
    "decide",
    "score_report",
    # assemble / gate
    "evaluate",
    "validate_report",
    "gate",
    "guardrail_gate",
    # diagnostics
    "explain",
    "root_cause",
    "regression_diff",
    "maturity",
    "industry_profiles",
    "industry_profile",
    "review_gate",
    "personas",
    "failure_map",
    "diagnose",
    "golden_set",
    "build_evidence",
    # operational
    "metrics",
    "operational_score",
    "cost_per_request",
    "token_efficiency",
    # quality metrics
    "retrieval_metrics",
    "match_metrics",
    "text_metrics",
    # safety & trajectory
    "redteam_template",
    "redteam_check",
    "trajectory",
    # calibration
    "calibrate",
    "calibrate_one",
    "cohen_kappa",
    "fleiss_kappa",
    "krippendorff_alpha",
    "reference_calibrate",
    # dataset
    "dataset_from_traces",
    "dataset_diff",
    "dataset_contamination",
    "dataset_coverage",
    # adapters
    "adapter_ragas",
    "adapter_promptfoo",
    "adapter_otel",
    "adapter_langsmith",
]


def main() -> None:
    """Console-script entry point: run the EvalSurfer MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
