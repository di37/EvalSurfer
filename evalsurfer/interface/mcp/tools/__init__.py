"""EvalSurfer MCP tool modules, nested by CIMAA layer.

Importing each module runs its ``@mcp.tool()`` decorators, registering that
domain's tools on the shared :data:`evalsurfer.interface.mcp.instance.mcp` server.
:mod:`evalsurfer.interface.mcp.server` imports them all.

Layout::

    tools/core/assemble.py              — Core (plan, score, validate, gate)
    tools/interface/evaluate.py         — Interface full-run ``evaluate``
    tools/interface/adapters.py         — Interface adapters
    tools/metrics/                      — Metrics (operational, quality, dataset)
    tools/analysis/                     — Analysis (diagnostics, calibration)
    tools/assurance/tools.py            — Assurance (guardrail_gate, redteam, trajectory)
"""
