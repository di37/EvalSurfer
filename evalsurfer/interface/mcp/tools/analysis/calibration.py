"""Calibration tools — the "eval of the eval" (judge-vs-oracle, agreement stats)."""

from __future__ import annotations

from evalsurfer.analysis.calibration.agreement import AgreementStats
from evalsurfer.analysis.calibration.calibrate import CalibrationCase, Calibrator
from evalsurfer.analysis.calibration.reference import ReferenceCalibrator
from evalsurfer.core.planner import Signals
from evalsurfer.interface.mcp import models as m
from evalsurfer.interface.mcp.instance import mcp


def _case(case: m.CalibrationCaseInput) -> CalibrationCase:
    """Build a core CalibrationCase from the pydantic input."""
    if case.signals is not None:
        signals = Signals(**case.signals.model_dump())
    else:
        signals = Signals.from_sample(
            case.sample.model_dump(exclude_none=True) if case.sample else {}
        )
    ranges = {cid: tuple(bounds) for cid, bounds in case.expected_score_ranges.items()}
    return CalibrationCase(
        name=case.name,
        signals=signals,
        expected_applicable_categories=frozenset(case.expected_applicable_categories),
        expected_score_ranges=ranges,
        expected_decision=case.expected_decision,
        expected_top_issue_severity=case.expected_top_issue_severity,
        expected_safety_escalation=case.expected_safety_escalation,
    )


@mcp.tool()
def calibrate(case: m.CalibrationCaseInput, judge_reports: list[m.Report]) -> dict:
    """Score a judge across many runs vs an oracle: agreement, false-pass/fail, variance."""
    return Calibrator.summarize(_case(case), [report.model_dump() for report in judge_reports])


@mcp.tool()
def calibrate_one(case: m.CalibrationCaseInput, judge_report: m.Report) -> dict:
    """Check one judge report against an oracle (per-match breakdown)."""
    return Calibrator.check_report(_case(case), judge_report.model_dump())


@mcp.tool()
def cohen_kappa(rater_a: list[str | int], rater_b: list[str | int]) -> float:
    """Cohen's kappa (2 raters) — chance-corrected agreement of two label sequences."""
    return AgreementStats.cohen_kappa(rater_a, rater_b)


@mcp.tool()
def fleiss_kappa(ratings: list[dict[str, int]]) -> float:
    """Fleiss' kappa (n raters) — chance-corrected agreement from per-item label counts."""
    return AgreementStats.fleiss_kappa(ratings)


@mcp.tool()
def krippendorff_alpha(reliability_data: list[list[str | int | None]]) -> float | None:
    """Krippendorff's alpha (nominal) — chance-corrected agreement; handles missing ratings.

    Returns ``null`` when there is no pairable data (no unit has two or more valid ratings).
    """
    return AgreementStats.krippendorff_alpha(reliability_data)


@mcp.tool()
def reference_calibrate(judge: dict[str, float], gold: dict[str, float]) -> dict:
    """Validate judge scores against human/gold: per-criterion error, MAE, rank correlation."""
    return ReferenceCalibrator.compare(judge, gold)
