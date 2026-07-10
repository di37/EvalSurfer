"""EvalSurfer as an MCP server — every deterministic function as a tool.

This is the on-thesis interface. The harness LLM (your coding agent) is the
**judge**; it calls these tools for every part of an evaluation that must be
**deterministic**. No external model is ever called — the judgment stays in the
agent, the measurement is these tools. The ``SKILL.md`` workflow tells the agent
which tool to reach for.

Tool inputs use pydantic models (:mod:`evalsurfer.mcp_models`) so each tool has a
clean, validated schema. Optional: requires ``pip install "evalsurfer[mcp]"``.
The core ``evalsurfer`` package never imports ``mcp`` or ``pydantic`` — only this
module and ``mcp_models`` do — so the package stays zero-dependency.

Run it (stdio transport):

    evalsurfer-mcp
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

import evalsurfer.constants as constants
from evalsurfer import mcp_models as m
from evalsurfer.adapters import (
    LangSmithAdapter,
    OtelAdapter,
    PromptfooAdapter,
    RagasAdapter,
)
from evalsurfer.calibration.agreement import AgreementStats
from evalsurfer.calibration.calibrate import CalibrationCase, Calibrator
from evalsurfer.calibration.reference import ReferenceCalibrator
from evalsurfer.cli import metrics as metrics_cli
from evalsurfer.cli import plan as plan_cli
from evalsurfer.cli import quality as quality_cli
from evalsurfer.core.evaluate import Evaluator
from evalsurfer.core.planner import EvaluationPlanner, Signals as CoreSignals
from evalsurfer.core.report import Gate, ReportValidator
from evalsurfer.core.scoring import ScoringModel
from evalsurfer.diagnostics import (
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
from evalsurfer.dataset.dataset import Dataset
from evalsurfer.diagnostics.bundle import DiagnosticsBundle
from evalsurfer.diagnostics.golden_set import GoldenSet
from evalsurfer.operational.metrics import OperationalMetrics, Pricing as CorePricing
from evalsurfer.operational.slo import OperationalScorer
from evalsurfer.policy.guardrails import GuardrailPolicy, Guardrails
from evalsurfer.safety.redteam import RedTeam
from evalsurfer.trajectory.agent_trace import TrajectoryEvaluator

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


def _case(case: m.CalibrationCaseInput) -> CalibrationCase:
    """Build a core CalibrationCase from the pydantic input."""
    if case.signals is not None:
        signals = CoreSignals(**case.signals.model_dump())
    else:
        signals = CoreSignals.from_sample(
            case.sample.model_dump(exclude_none=True) if case.sample else {}
        )
    ranges = {cid: tuple(bounds) for cid, bounds in case.expected_score_ranges.items()}
    return CalibrationCase(
        name=case.name,
        signals=signals,
        expected_applicable_pillars=frozenset(case.expected_applicable_pillars),
        expected_score_ranges=ranges,
        expected_decision=case.expected_decision,
        expected_top_issue_severity=case.expected_top_issue_severity,
        expected_safety_escalation=case.expected_safety_escalation,
    )


# --------------------------------------------------------------------------- #
# Rubric & adaptive planning
# --------------------------------------------------------------------------- #
@mcp.tool()
def rubric() -> list[dict]:
    """List the full rubric — every criterion's id, name, pillar, and group."""
    return [
        {"id": c.id, "name": c.name, "pillar": c.pillar, "group": c.group}
        for c in EvaluationPlanner.CRITERIA
    ]


@mcp.tool()
def plan(sample: m.Sample) -> dict:
    """Infer which pillars and criteria apply to a sample, plus a coverage score."""
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
def score_pillar(scores: list[int | None]) -> float | None:
    """Pillar score: mean of the 1-5 criterion scores, scaled to 0-10 (None excluded)."""
    return ScoringModel.pillar_score(scores)


@mcp.tool()
def score_overall(pillar_scores: list[float | None]) -> float | None:
    """Overall score: mean of the pillar scores on 0-10 (None excluded)."""
    return ScoringModel.overall_score(pillar_scores)


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
    """Recompute pillar/overall scores and the decision from a report's criteria."""
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


# --------------------------------------------------------------------------- #
# Diagnostics — individual and bundled
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Operational
# --------------------------------------------------------------------------- #
@mcp.tool()
def metrics(payload: m.TracesPayload) -> dict:
    """Operational metrics from request traces: latency, TTFT, ITL, throughput, cost,
    failure rate, and latency-under-load."""
    return metrics_cli.build_report(payload.model_dump(exclude_none=True))


@mcp.tool()
def operational_score(payload: m.TracesPayload, slo: m.SLO) -> dict:
    """Auto-score the operational pillar 1-5 by comparing measured metrics to an SLO."""
    return OperationalScorer(slo.model_dump(exclude_none=True)).score(
        payload.model_dump(exclude_none=True)
    )


@mcp.tool()
def cost_per_request(input_tokens: int, output_tokens: int, pricing: m.Pricing) -> float:
    """Per-request token cost in USD from token counts and pricing."""
    return OperationalMetrics.cost_per_request_usd(
        input_tokens, output_tokens, CorePricing(**pricing.model_dump())
    )


@mcp.tool()
def token_efficiency(useful_output_tokens: int, input_tokens: int, output_tokens: int) -> float:
    """Useful-output ratio against total tokens spent (0-1)."""
    return OperationalMetrics.token_efficiency(useful_output_tokens, input_tokens, output_tokens)


# --------------------------------------------------------------------------- #
# Deterministic quality metrics (reference-based; zero LLM calls)
# --------------------------------------------------------------------------- #
@mcp.tool()
def retrieval_metrics(payload: m.RetrievalMetricsInput) -> dict:
    """Recall@k / Precision@k / MRR over ranked retrieved ids vs gold-relevant ids.
    Also scores tool-selection recall (a router miss is a recall error)."""
    return quality_cli.build_report(
        {"retrieval": payload.model_dump(exclude_none=True)}
    )["retrieval"]


@mcp.tool()
def match_metrics(payload: m.MatchMetricsInput) -> dict:
    """Extraction (exact-match / token-F1) or classification (accuracy, P/R/F1) scores
    of predictions against gold references."""
    return quality_cli.build_report({"match": payload.model_dump(exclude_none=True)})[
        "match"
    ]


@mcp.tool()
def text_metrics(payload: m.TextMetricsInput) -> dict:
    """Task-typed reference-text metrics: BLEU (translation), ROUGE (summarization),
    METEOR (generation) of candidates against gold references."""
    return quality_cli.build_report({"text": payload.model_dump(exclude_none=True)})[
        "text"
    ]


# --------------------------------------------------------------------------- #
# Safety & trajectory
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# Calibration — the "eval of the eval"
# --------------------------------------------------------------------------- #
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
def krippendorff_alpha(reliability_data: list[list[str | int | None]]) -> float:
    """Krippendorff's alpha (nominal) — chance-corrected agreement; handles missing ratings."""
    return AgreementStats.krippendorff_alpha(reliability_data)


@mcp.tool()
def reference_calibrate(judge: dict[str, float], gold: dict[str, float]) -> dict:
    """Validate judge scores against human/gold: per-criterion error, MAE, rank correlation."""
    return ReferenceCalibrator.compare(judge, gold)


# --------------------------------------------------------------------------- #
# Golden dataset (versioned cases + contamination controls)
# --------------------------------------------------------------------------- #
@mcp.tool()
def dataset_from_traces(traces: list[dict], name: str = "dataset", version: str = "v1") -> dict:
    """Harvest a versioned golden dataset from request traces (dedup by content hash)."""
    return Dataset.from_traces(traces, name=name, version=version).to_dict()


@mcp.tool()
def dataset_diff(before: dict, after: dict) -> dict:
    """Diff two dataset versions: added / removed / unchanged / changed case ids."""
    return Dataset.from_mapping(after).diff(Dataset.from_mapping(before))


@mcp.tool()
def dataset_contamination(
    dataset: dict, blocklist: list[str] | None = None, canaries: list[str] | None = None
) -> dict:
    """Contamination report: duplicate-content groups, blocklist hits, and canary hits."""
    return Dataset.from_mapping(dataset).contamination_report(
        blocklist=tuple(blocklist or ()), canaries=tuple(canaries or ())
    )


@mcp.tool()
def dataset_coverage(dataset: dict) -> dict:
    """Coverage summary: case counts per tag, held-out/eval split, and unique hashes."""
    return Dataset.from_mapping(dataset).coverage_summary()


# --------------------------------------------------------------------------- #
# Ecosystem adapters
# --------------------------------------------------------------------------- #
@mcp.tool()
def adapter_ragas(metrics: dict[str, float]) -> list[dict]:
    """Import RAGAS metrics (0-1) as EvalSurfer rubric criteria (1-5)."""
    return RagasAdapter.to_criteria(metrics)


@mcp.tool()
def adapter_promptfoo(results: dict | list) -> dict:
    """Import promptfoo results as a minimal EvalSurfer report."""
    return PromptfooAdapter.to_report(results)


@mcp.tool()
def adapter_otel(spans: list[dict]) -> list[dict]:
    """Import OpenTelemetry spans as EvalSurfer request traces."""
    return OtelAdapter.to_traces(spans)


@mcp.tool()
def adapter_langsmith(runs: list[dict]) -> list[dict]:
    """Import LangSmith runs as EvalSurfer request traces."""
    return LangSmithAdapter.to_traces(runs)


def main() -> None:
    """Console-script entry point: run the EvalSurfer MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
