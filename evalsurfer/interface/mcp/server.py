"""EvalSurfer MCP server — every deterministic function as a tool.

This is the on-thesis interface. The harness LLM (your coding agent) is the
**judge**; it calls these tools for every part of an evaluation that must be
**deterministic**. No external model is ever called — the judgment stays in the
agent, the measurement is these tools. The ``SKILL.md`` workflow tells the agent
which tool to reach for.

Importing the tool functions below runs each tool module's ``@mcp.tool()``
decorators, registering them on the shared :data:`evalsurfer.interface.mcp.instance.mcp`
server, and re-exports every tool as an attribute of this module (so
``server.rubric`` and friends are callable directly). Tool inputs use pydantic
models (:mod:`evalsurfer.interface.mcp.models`) so each tool has a clean, validated schema.
Optional: requires ``pip install "evalsurfer[mcp]"``. The ``evalsurfer``
package never imports ``mcp`` or ``pydantic`` — only this subpackage does — so the
package stays zero-dependency.

Run it (stdio transport):

    evalsurfer-mcp
"""

from __future__ import annotations

from evalsurfer.interface.mcp.instance import mcp
from evalsurfer.interface.mcp.tools.interface.adapters import (
    adapter_langfuse,
    adapter_langsmith,
    adapter_otel,
    adapter_promptfoo,
    adapter_ragas,
)
from evalsurfer.interface.mcp.tools.analysis.calibration import (
    calibrate,
    calibrate_one,
    cohen_kappa,
    fleiss_kappa,
    harness_invariance,
    krippendorff_alpha,
    reference_calibrate,
)
from evalsurfer.interface.mcp.tools.analysis.diagnostics import (
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
from evalsurfer.interface.mcp.tools.assurance.tools import (
    guardrail_gate,
    redteam_check,
    redteam_template,
    trajectory,
)
from evalsurfer.interface.mcp.tools.core.assemble import (
    coverage,
    decide,
    gate,
    plan,
    rubric,
    score_overall,
    score_category,
    score_report,
    validate_report,
)
from evalsurfer.interface.mcp.tools.interface.evaluate import evaluate
from evalsurfer.interface.mcp.tools.metrics.dataset import (
    dataset_contamination,
    dataset_coverage,
    dataset_diff,
    dataset_from_traces,
)
from evalsurfer.interface.mcp.tools.metrics.operational import (
    cost_per_request,
    metrics,
    operational_score,
    token_efficiency,
)
from evalsurfer.interface.mcp.tools.metrics.quality import (
    match_metrics,
    retrieval_metrics,
    text_metrics,
)

__all__ = [
    "mcp",
    "main",
    # rubric & scope
    "rubric",
    "plan",
    "coverage",
    # scoring (Core)
    "score_category",
    "score_overall",
    "decide",
    "score_report",
    # full run (Interface pipeline)
    "evaluate",
    # assemble / gate (Core)
    "validate_report",
    "gate",
    # diagnostics (Analysis)
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
    # assurance
    "guardrail_gate",
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
    "harness_invariance",
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
    "adapter_langfuse",
]


def main() -> None:
    """Console-script entry point: run the EvalSurfer MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
