"""Safety & trajectory tools — red-team battery and agent-trajectory diffing."""

from __future__ import annotations

from evalsurfer.mcp.instance import mcp
from evalsurfer.safety.redteam import RedTeam
from evalsurfer.trajectory.agent_trace import TrajectoryEvaluator


@mcp.tool()
def redteam_template(rag: bool = False, agent: bool = False, pii: bool = False) -> list[dict]:
    """Emit the red-team probe battery to send to a target of the given shape."""
    return RedTeam.template(rag=rag, agent=agent, pii=pii)


@mcp.tool()
def redteam_check(outputs: dict[str, str]) -> dict:
    """Triage collected probe outputs (deterministic PII; the rest flagged for you)."""
    return RedTeam.check(outputs)


@mcp.tool()
def trajectory(actual: dict, expected: dict) -> dict:
    """Diff an agent's actual tool-call trajectory against an expected spec."""
    return TrajectoryEvaluator.evaluate(actual, expected)
