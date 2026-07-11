"""Core evaluation tools: rubric & scope, scoring, assemble, validate, gate."""

from __future__ import annotations

import evalsurfer.constants as constants
from evalsurfer.interface.cli import plan as plan_cli
from evalsurfer.core.evaluate import Evaluator
from evalsurfer.core.planner import EvaluationPlanner, Signals as CoreSignals
from evalsurfer.core.report import Gate, ReportValidator
from evalsurfer.core.scoring import ScoringModel
from evalsurfer.interface.mcp import models as m
from evalsurfer.interface.mcp.instance import mcp
from evalsurfer.assurance.policy.guardrails import GuardrailPolicy, Guardrails


# --------------------------------------------------------------------------- #
# Rubric & adaptive planning
# --------------------------------------------------------------------------- #
@mcp.tool()
def rubric() -> list[dict]:
    """List the full rubric — every criterion's id, name, category, and group."""
    return [
        {"id": c.id, "name": c.name, "category": c.category, "group": c.group}
        for c in EvaluationPlanner.CRITERIA
    ]


@mcp.tool()
def plan(sample: m.Sample) -> dict:
    """Infer which categories and criteria apply to a sample, plus a coverage score."""
    return plan_cli.build_report({"sample": sample.model_dump(exclude_none=True)})


@mcp.tool()
def coverage(sample: m.Sample, report: m.Report) -> dict:
    """How much of the applicable rubric a report actually assessed."""
    plan_obj = EvaluationPlanner.plan(
        CoreSignals.from_sample(sample.model_dump(exclude_none=True))
    )
    return EvaluationPlanner.coverage(plan_obj, report.model_dump())


# --------------------------------------------------------------------------- #
# Scoring primitives
# --------------------------------------------------------------------------- #
@mcp.tool()
def score_category(scores: list[int | None]) -> float | None:
    """Category score: mean of the 1-5 criterion scores, scaled to 0-10 (None excluded)."""
    return ScoringModel.category_score(scores)


@mcp.tool()
def score_overall(category_scores: list[float | None]) -> float | None:
    """Overall score: mean of the category scores on 0-10 (None excluded)."""
    return ScoringModel.overall_score(category_scores)


@mcp.tool()
def decide(inputs: m.DecideInput) -> str:
    """The pass / pass_with_fixes / fail decision from overall, safety, and gates."""
    return ScoringModel.decide(
        inputs.overall,
        inputs.safety,
        critical_safety_issue=inputs.critical_safety_issue,
        failure_rate=inputs.failure_rate,
        p95_within_slo=inputs.p95_within_slo,
        core_task_failed=inputs.core_task_failed,
    )


@mcp.tool()
def score_report(report: m.Report) -> dict:
    """Recompute category/overall scores and the decision from a report's criteria."""
    return ScoringModel.score(report.model_dump())


# --------------------------------------------------------------------------- #
# Assemble, validate, gate
# --------------------------------------------------------------------------- #
@mcp.tool()
def evaluate(request: m.EvaluateRequest) -> dict:
    """Assemble a full report from the scores you (the judge) produced."""
    return Evaluator.evaluate(request.model_dump(exclude_none=True))


@mcp.tool()
def validate_report(report: m.Report) -> dict:
    """Structurally validate a report. Returns {"valid": bool, "errors": [...]}."""
    return ReportValidator.validate(report.model_dump())


@mcp.tool()
def gate(report: m.Report, min_decision: str = constants.DECISION_PASS_WITH_FIXES) -> dict:
    """Release gate: does the report clear a minimum decision ("pass"/"pass_with_fixes"/"fail")?"""
    return Gate.evaluate(report.model_dump(), min_decision)


@mcp.tool()
def guardrail_gate(
    report: m.Report,
    policy: m.GuardrailPolicyInput,
    changed_files: list[str] | None = None,
    attempt: int | None = None,
) -> dict:
    """Enforce a full guardrail policy (floors, sensitive-path denylist, attempt cap)."""
    return Guardrails.check(
        report.model_dump(),
        GuardrailPolicy.from_mapping(policy.model_dump(exclude_none=True)),
        changed_files=tuple(changed_files or ()),
        attempt=attempt,
    )
