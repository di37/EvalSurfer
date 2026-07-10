"""The shared FastMCP instance and its agent-facing instructions.

Kept in its own module so every tool module can ``from evalsurfer.mcp.instance
import mcp`` and register its ``@mcp.tool()`` functions on the one shared server
without a circular import through :mod:`evalsurfer.mcp.server`.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

INSTRUCTIONS = (
    "EvalSurfer: you are the judge. Read the AI output, then use these tools for "
    "the deterministic parts of evaluation. Typical flow: `plan` to see which "
    "criteria apply, score each applicable quality/safety criterion 1-5 with "
    "evidence yourself, `evaluate` to assemble the report, `diagnose`/`explain` to "
    "understand it, and `gate`/`guardrail_gate` to decide what ships. Operational "
    "criteria come from traces via `metrics`/`operational_score` — do not judge "
    "those. No tool calls a model: the judgment is yours."
)

mcp = FastMCP("EvalSurfer", instructions=INSTRUCTIONS)
