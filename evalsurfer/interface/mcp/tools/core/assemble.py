"""Core MCP tools: rubric & scope, scoring, validate, gate."""

from __future__ import annotations

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner, Signals
from evalsurfer.core.report import Gate, ReportValidator
from evalsurfer.core.scoring import ScoringModel
from evalsurfer.interface.mcp import models as m
from evalsurfer.interface.mcp.instance import mcp


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
    signals = Signals.from_sample(sample.model_dump(exclude_none=True))
    plan_obj = EvaluationPlanner.plan(signals)
    return {"signals": vars(signals), "plan": plan_obj.to_dict()}


@mcp.tool()
def coverage(sample: m.Sample, report: m.Report) -> dict:
    """How much of the applicable rubric a report actually assessed."""
    plan_obj = EvaluationPlanner.plan(
        Signals.from_sample(sample.model_dump(exclude_none=True))
    )
    return EvaluationPlanner.coverage(plan_obj, report.model_dump())


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
    """The pass / pass_with_fixes / fail decision from overall score and thresholds."""
    return ScoringModel.decide(
        inputs.overall,
        inputs.safety,
        critical_safety_issue=inputs.critical_safety_issue,
        failure_rate=inputs.failure_rate,
        p95_within_slo=inputs.p95_within_slo,
        task_failed=inputs.task_failed,
    )


@mcp.tool()
def score_report(report: m.Report) -> dict:
    """Recompute category/overall scores and the decision from a report's criteria."""
    return ScoringModel.score(report.model_dump())


@mcp.tool()
def validate_report(report: m.Report) -> dict:
    """Structurally validate a report. Returns {"valid": bool, "errors": [...]}."""
    return ReportValidator.validate(report.model_dump())


@mcp.tool()
def gate(report: m.Report, min_decision: str = constants.DECISION_PASS_WITH_FIXES) -> dict:
    """Core gate: does the report's decision meet or exceed the minimum bar?"""
    return Gate.evaluate(report.model_dump(), min_decision)
