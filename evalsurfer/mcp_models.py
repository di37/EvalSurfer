"""Pydantic input models for the EvalSurfer MCP tools (optional ``[mcp]`` extra).

These give every tool a clean, validated, self-documenting JSON schema for the
agent. They mirror EvalSurfer's inputs; the core package keeps its own
frozen-dataclass value objects and never imports pydantic, so the core stays
zero-dependency. Only this module (and ``evalsurfer.mcp_server``) needs pydantic.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

import evalsurfer.constants as constants


class Sample(BaseModel):
    """One evaluation target — whatever evidence you have about an AI output."""

    model_config = ConfigDict(extra="allow")

    query: str | None = None
    answer: str | None = None
    retrieved_docs: list[str] | None = None
    citations: list[str] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    conversation_history: list[dict[str, Any]] | None = None
    safety_relevant: bool = True


class Signals(BaseModel):
    """Explicit evidence flags (for `plan` / `maturity` when you set them directly)."""

    answer: bool = False
    retrieved_context: bool = False
    citations: bool = False
    tool_calls: bool = False
    tool_failure: bool = False
    multi_turn: bool = False
    operational_traces: bool = False
    safety_relevant: bool = True


class Pricing(BaseModel):
    """Token pricing, in USD per one million tokens."""

    input_per_million: float
    output_per_million: float


class Trace(BaseModel):
    """One request trace. Extra fields (e.g. `usage`, `timed_out`) pass through."""

    model_config = ConfigDict(extra="allow")

    request_started_at: Any
    first_token_at: Any | None = None
    response_completed_at: Any | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    concurrency: int | None = None
    failed: bool | None = None
    error: str | None = None


class TracesPayload(BaseModel):
    """A batch of request traces with optional pricing."""

    traces: list[Trace]
    pricing: Pricing | None = None


class SLO(BaseModel):
    """Service-level-objective targets. Only the fields you set are scored."""

    p95_latency_ms: float | None = None
    ttft_ms: float | None = None
    max_failure_rate: float | None = None
    max_cost_usd: float | None = None
    itl_ms: float | None = None
    min_tokens_per_second: float | None = None
    max_p99_p50_ratio: float | None = None
    max_cost_per_million_usd: float | None = None


class TopIssue(BaseModel):
    """A prioritised finding."""

    severity: str = Field(description="critical | major | minor")
    description: str
    recommendation: str | None = None
    criterion_id: str | None = None


class EvidenceInput(BaseModel):
    """Structured evidence for one judged criterion."""

    claim: str
    supporting_context: str = ""
    mismatch: str = ""
    confidence: float | None = None


class EvaluateRequest(BaseModel):
    """Everything needed to assemble a report from your (the judge's) scores."""

    sample: Sample
    scores: dict[str, Any] = Field(
        default_factory=dict,
        description="criterion_id -> 1-5, or pillar -> {criterion_id: 1-5}",
    )
    evidence: dict[str, Any] = Field(default_factory=dict, description="criterion_id -> evidence")
    top_issues: list[TopIssue] = Field(default_factory=list)
    traces: TracesPayload | None = None
    slo: SLO | None = None
    summary: str | None = None


class DecideInput(BaseModel):
    """Inputs to the pass/fix/fail decision."""

    overall: float | None = None
    safety: float | None = None
    critical_safety_issue: bool = False
    failure_rate: float | None = None
    p95_within_slo: bool | None = None
    core_task_failed: bool = False


class GuardrailPolicyInput(BaseModel):
    """A release guardrail policy."""

    min_decision: str = constants.DECISION_PASS_WITH_FIXES
    min_safety: float | None = None
    coverage_floor: float | None = None
    block_on_critical_issue: bool = False
    sensitive_paths: list[str] = Field(default_factory=list)
    max_fix_attempts: int | None = None


class PillarScores(BaseModel):
    """The three pillar scores on a 0-10 scale (any may be null)."""

    quality: float | None = None
    safety: float | None = None
    operational: float | None = None


class CalibrationCaseInput(BaseModel):
    """A hand-authored oracle for what a trustworthy judge should conclude."""

    name: str = "calibration-case"
    signals: Signals | None = None
    sample: Sample | None = None
    expected_applicable_pillars: list[str] = Field(default_factory=list)
    expected_score_ranges: dict[str, list[int]] = Field(default_factory=dict)
    expected_decision: str = constants.DECISION_PASS_WITH_FIXES
    expected_top_issue_severity: str | None = None
    expected_safety_escalation: bool = False


class Report(BaseModel):
    """A produced report — pass through what a prior tool returned. Permissive."""

    model_config = ConfigDict(extra="allow")

    overall: dict[str, Any] | None = None
    pillars: dict[str, Any] | None = None
    decision: str | None = None
    top_issues: list[dict[str, Any]] | None = None
    coverage: dict[str, Any] | None = None


# --------------------------------------------------------------------------- #
# Deterministic quality metrics (reference-based / programmatic)
# --------------------------------------------------------------------------- #
class RetrievalCaseInput(BaseModel):
    """One query's ranked retrieval outcome against its gold-relevant ids."""

    retrieved: list[str | int] = Field(
        default_factory=list, description="ranked retrieved ids, best first"
    )
    relevant: list[str | int] = Field(
        default_factory=list, description="gold-relevant ids"
    )
    k: int | None = Field(default=None, description="rank cutoff; null uses the whole list")


class RetrievalMetricsInput(BaseModel):
    """A batch of retrieval cases with an optional global rank cutoff."""

    cases: list[RetrievalCaseInput]
    k: int | None = None


class MatchMetricsInput(BaseModel):
    """Predicted vs gold values for extraction or classification scoring."""

    predictions: list[Any]
    references: list[Any]
    task: str = Field(default="extraction", description="'extraction' or 'classification'")
    average: str = Field(
        default=constants.AVERAGE_MACRO, description="'macro' or 'micro' (classification)"
    )
    positive_label: str | int | None = Field(
        default=None, description="report this label's binary P/R/F1 (classification)"
    )


class TextItemInput(BaseModel):
    """One candidate string and its reference(s) for text metrics."""

    candidate: str
    references: list[str] | None = Field(default=None, description="reference(s); BLEU allows several")
    reference: str | None = Field(default=None, description="a single reference (alias)")


class TextMetricsInput(BaseModel):
    """Candidate/reference items with the reference-text metrics to compute."""

    items: list[TextItemInput]
    task: str | None = Field(
        default=None, description="translation | summarization | generation (picks defaults)"
    )
    metrics: list[str] | None = Field(
        default=None, description="explicit metric ids: bleu / rouge_n / rouge_l / meteor"
    )
    n: int = Field(default=constants.ROUGE_DEFAULT_N, description="ROUGE-N order")
