"""Diagnostics tools — individual analyses and the bundled runner."""

from __future__ import annotations

from evalsurfer.core.planner import Signals as CoreSignals
from evalsurfer.analysis.diagnostics import (
    Evidence,
    Explainer,
    FailureMap,
    IndustryProfiler,
    MaturityClassifier,
    PersonaAggregator,
    RegressionDiffer,
    ReviewGate,
    RootCauseAnalyzer,
)
from evalsurfer.analysis.diagnostics.bundle import DiagnosticsBundle
from evalsurfer.analysis.diagnostics.golden_set import GoldenSet
from evalsurfer.interface.mcp import models as m
from evalsurfer.interface.mcp.instance import mcp


@mcp.tool()
def explain(report: m.Report) -> dict:
    """Attribute the gap from a perfect 10 to individual criteria (SHAP-style)."""
    return Explainer.explain(report.model_dump())


@mcp.tool()
def root_cause(report: m.Report) -> dict:
    """Attribute lost points by pillar and criterion group, with a top contributor."""
    return RootCauseAnalyzer.attribute(report.model_dump())


@mcp.tool()
def regression_diff(before: m.Report, after: m.Report) -> dict:
    """Diff two reports: improvements, regressions, deltas, and any decision change."""
    return RegressionDiffer.diff(before.model_dump(), after.model_dump())


@mcp.tool()
def maturity(signals: m.Signals, multi_agent: bool = False, self_improving: bool = False) -> dict:
    """Classify the app's maturity level (1-6) from its evidence signals."""
    return MaturityClassifier.classify(
        CoreSignals(**signals.model_dump()),
        multi_agent=multi_agent,
        self_improving=self_improving,
    )


@mcp.tool()
def industry_profiles() -> list[str]:
    """List the available industry weighting profiles."""
    return list(IndustryProfiler.available_profiles())


@mcp.tool()
def industry_profile(profile: str, pillar_scores: m.PillarScores) -> dict:
    """Re-weight the overall score using an industry profile's pillar weights."""
    weighted = IndustryProfiler(profile).weighted_overall(pillar_scores.model_dump())
    return {"profile": profile, "weighted_overall": weighted}


@mcp.tool()
def review_gate(report: m.Report) -> dict:
    """Recommend human review (critical issues, low-confidence criteria)."""
    return ReviewGate().evaluate(report.model_dump())


@mcp.tool()
def personas(reports: dict[str, m.Report]) -> dict:
    """Aggregate per-persona reports into agreement / min / mean across personas."""
    return PersonaAggregator.aggregate(
        {name: report.model_dump() for name, report in reports.items()}
    )


@mcp.tool()
def failure_map(report: m.Report) -> dict:
    """Diagnose which pipeline stage (retriever / ranker / generator / tool) is weak."""
    return FailureMap().render(report.model_dump())


@mcp.tool()
def diagnose(
    report: m.Report, before: m.Report | None = None, signals: m.Signals | None = None
) -> dict:
    """Run the full diagnostics bundle: explainability, root cause, failure map, and
    review gate; plus maturity when `signals` is given and regression when `before` is."""
    return DiagnosticsBundle.run(
        report.model_dump(),
        before=before.model_dump() if before else None,
        signals=CoreSignals(**signals.model_dump()) if signals else None,
    )


@mcp.tool()
def golden_set() -> list[dict]:
    """Run the golden set — validate the deterministic layer against known cases."""
    return GoldenSet.run_all()


@mcp.tool()
def build_evidence(evidence: m.EvidenceInput) -> dict:
    """Build a structured evidence record from claim / context / mismatch / confidence."""
    return Evidence.to_dict(
        Evidence(
            claim=evidence.claim,
            supporting_context=evidence.supporting_context,
            mismatch=evidence.mismatch,
            confidence=evidence.confidence,
        )
    )
