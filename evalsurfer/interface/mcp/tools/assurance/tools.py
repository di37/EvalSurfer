"""Assurance tools — red-team, trajectory, and guardrail policy."""

from __future__ import annotations

from evalsurfer.assurance.policy.guardrails import GuardrailPolicy, Guardrails
from evalsurfer.assurance.safety.redteam import RedTeam
from evalsurfer.assurance.trajectory.agent_trace import TrajectoryEvaluator
from evalsurfer.interface.mcp import models as m
from evalsurfer.interface.mcp.instance import mcp


@mcp.tool()
def guardrail_gate(
    report: m.Report,
    policy: m.GuardrailPolicyInput,
    changed_files: list[str] | None = None,
    attempt: int | None = None,
) -> dict:
    """Enforce a full Assurance guardrail policy (floors, denylist, attempt cap)."""
    return Guardrails.check(
        report.model_dump(),
        GuardrailPolicy.from_mapping(policy.model_dump(exclude_none=True)),
        changed_files=tuple(changed_files or ()),
        attempt=attempt,
    )


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
