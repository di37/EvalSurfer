"""End-to-end evaluation orchestrator for EvalSurfer.

:class:`Evaluator` wires the deterministic pieces around an agent-produced set of
criterion scores to assemble a complete, schema-shaped report: it infers the
plan from the sample, places the provided criterion scores, auto-scores the
operational pillar from traces against an SLO, recomputes pillar and overall
scores, derives the pass/fix/fail decision, measures coverage, and attaches the
diagnostics block.

It never runs an LLM judge -- the criterion scores for quality and safety come
from the agent/skill via the request. Everything here is deterministic, standard
library only, and makes no model calls; inputs are never mutated.
"""

from __future__ import annotations

from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner, Signals
from evalsurfer.core.scoring import ScoringModel
from evalsurfer.diagnostics.bundle import DiagnosticsBundle
from evalsurfer.operational.metrics import OperationalMetrics, Pricing, RequestTrace
from evalsurfer.operational.slo import OperationalScorer

__all__ = ["Evaluator"]

# Within-SLO threshold: an operational criterion scoring at least this (target
# met, i.e. measured <= target) counts as within the product SLO.
_WITHIN_SLO_MIN_SCORE = 3
_LATENCY_CRITERION_ID = "end_to_end_latency"

_SAFETY_CRITERION_IDS = frozenset(
    criterion.id
    for criterion in EvaluationPlanner.CRITERIA
    if criterion.pillar == constants.PILLAR_SAFETY
)


class Evaluator:
    """Assemble a complete report from a sample plus agent-produced scores.

    Stateless: every input is passed to :meth:`evaluate`, so the class is a
    cohesive namespace rather than something to instantiate.
    """

    @classmethod
    def evaluate(cls, request: Mapping[str, Any]) -> dict[str, Any]:
        """Build a complete, schema-shaped report from an evaluation request.

        The request is a mapping that may contain: the evaluation ``sample``
        (its own key, or the request itself) used to infer signals; ``scores``
        (criterion id -> 1-5 score, or pillar -> {id: score}); ``evidence``
        (criterion id -> evidence string); ``traces`` and optional ``slo`` for
        operational auto-scoring; ``top_issues``; ``not_assessed``; ``summary``;
        ``safety_relevant``; and ``before`` (a prior report, for the regression
        diagnostic).

        Args:
            request: The evaluation request mapping.

        Returns:
            A report dict with ``overall``, ``pillars``, ``decision``,
            ``top_issues``, ``not_assessed``, ``coverage``, ``diagnostics``, and
            ``metadata``.

        Raises:
            TypeError: If ``request`` is not a mapping.
        """
        if not isinstance(request, Mapping):
            raise TypeError("request must be a mapping")

        sample = request.get("sample", request)
        signals = Signals.from_sample(sample)
        plan = EvaluationPlanner.plan(signals)

        provided = cls._flatten_scores(request.get("scores"))
        evidence = request.get("evidence") or {}
        applicable = {criterion.id for criterion in plan.applicable_criteria()}

        pillars = cls._build_judged_pillars(applicable, provided, evidence, request)
        summary = cls._operational(request, pillars)

        for pillar in pillars.values():
            pillar["score"] = ScoringModel.pillar_score(
                [criterion["score"] for criterion in pillar["criteria"]]
            )
        overall = ScoringModel.overall_score(
            [pillar["score"] for pillar in pillars.values()]
        )

        top_issues = [issue for issue in (request.get("top_issues") or []) if isinstance(issue, Mapping)]
        decision = ScoringModel.decide(
            overall,
            pillars.get(constants.PILLAR_SAFETY, {}).get("score"),
            critical_safety_issue=cls._has_critical_safety_issue(top_issues),
            failure_rate=summary.failure_rate if summary is not None else None,
            p95_within_slo=cls._p95_within_slo(pillars, request.get("slo")),
        )

        report: dict[str, Any] = {
            "overall": {
                "score": overall if overall is not None else 0.0,
                "decision": decision,
                "summary": str(request.get("summary", "")),
            },
            "pillars": pillars,
            "decision": decision,
            "top_issues": [dict(issue) for issue in top_issues],
            "not_assessed": list(request.get("not_assessed") or []),
            "coverage": EvaluationPlanner.coverage(plan, {"pillars": pillars}),
            "metadata": {
                "framework": constants.FRAMEWORK_NAME,
                "version": constants.FRAMEWORK_VERSION,
            },
        }
        before = request.get("before")
        report["diagnostics"] = DiagnosticsBundle.run(
            report, before=before if isinstance(before, Mapping) else None, signals=signals
        )
        return report

    @staticmethod
    def _flatten_scores(scores: Any) -> dict[str, int]:
        """Flatten provided scores to a criterion-id -> score mapping.

        Args:
            scores: ``None``, a flat ``{criterion_id: score}`` mapping, or a
                nested ``{pillar: {criterion_id: score}}`` mapping.

        Returns:
            A flat ``{criterion_id: score}`` dict; non-int scores are dropped.
        """
        if not isinstance(scores, Mapping):
            return {}
        flat: dict[str, int] = {}
        for key, value in scores.items():
            if isinstance(value, Mapping):
                for cid, score in value.items():
                    if isinstance(score, int) and not isinstance(score, bool):
                        flat[cid] = score
            elif isinstance(value, int) and not isinstance(value, bool):
                flat[key] = value
        return flat

    @classmethod
    def _build_judged_pillars(
        cls,
        applicable: set[str],
        provided: Mapping[str, int],
        evidence: Mapping[str, Any],
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Build the quality and safety pillars from provided criterion scores.

        A criterion is included when the plan makes it applicable or a score was
        provided for it. The operational pillar is handled separately by
        :meth:`_operational`.

        Args:
            applicable: Ids of criteria the plan marks applicable.
            provided: Flat ``{criterion_id: score}`` mapping.
            evidence: ``{criterion_id: evidence}`` mapping.
            request: The full request (unused fields ignored).

        Returns:
            ``{pillar_id: {"criteria": [criterion, ...]}}`` for the non-empty
            quality and safety pillars.
        """
        pillars: dict[str, Any] = {}
        for pillar_id in (constants.PILLAR_QUALITY, constants.PILLAR_SAFETY):
            criteria = [
                {
                    "id": criterion.id,
                    "name": criterion.name,
                    "score": provided.get(criterion.id),
                    "evidence": str(evidence.get(criterion.id, "")),
                }
                for criterion in EvaluationPlanner.CRITERIA
                if criterion.pillar == pillar_id
                and (criterion.id in applicable or criterion.id in provided)
            ]
            if criteria:
                pillars[pillar_id] = {"criteria": criteria}
        return pillars

    @staticmethod
    def _operational(request: Mapping[str, Any], pillars: dict[str, Any]):
        """Auto-score the operational pillar from traces, if traces are present.

        Args:
            request: The evaluation request; ``traces`` and optional ``slo`` and
                ``pricing`` drive operational scoring.
            pillars: The pillars dict to add the operational pillar to (mutated
                in place — it is freshly built by the caller).

        Returns:
            The :class:`OperationalSummary` for the traces (for the failure rate),
            or ``None`` when no traces were supplied.
        """
        payload = request.get("traces")
        if payload is None:
            return None

        scored = OperationalScorer(request.get("slo")).score(payload)
        pillars[constants.PILLAR_OPERATIONAL] = {"criteria": scored["criteria"]}

        traces, pricing = Evaluator._parse_traces(payload)
        return OperationalMetrics.summarize(traces, pricing=pricing)

    @staticmethod
    def _parse_traces(payload: Any) -> tuple[list[RequestTrace], Pricing | None]:
        """Parse a trace payload into request traces and optional pricing.

        Args:
            payload: A list of trace mappings, or ``{"traces": [...],
                "pricing": {...}}``.

        Returns:
            A ``(traces, pricing)`` tuple.
        """
        pricing = None
        if isinstance(payload, Mapping):
            trace_items = payload.get("traces") or []
            price = payload.get("pricing")
            if isinstance(price, Mapping):
                pricing = Pricing(
                    input_per_million=float(price["input_per_million"]),
                    output_per_million=float(price["output_per_million"]),
                )
        else:
            trace_items = payload
        return [RequestTrace.from_mapping(item) for item in trace_items], pricing

    @staticmethod
    def _has_critical_safety_issue(top_issues: Any) -> bool:
        """Report whether a critical top issue names a safety criterion.

        Args:
            top_issues: The report's ``top_issues`` list.

        Returns:
            ``True`` when any issue has ``severity == "critical"`` and a
            ``criterion_id`` on the safety pillar.
        """
        return any(
            issue.get("severity") == constants.SEVERITY_CRITICAL
            and issue.get("criterion_id") in _SAFETY_CRITERION_IDS
            for issue in top_issues
            if isinstance(issue, Mapping)
        )

    @staticmethod
    def _p95_within_slo(pillars: Mapping[str, Any], slo: Any) -> bool | None:
        """Whether measured P95 latency sits within the SLO, if both are known.

        Args:
            pillars: The assembled pillars (operational criteria carry the score).
            slo: The SLO mapping, or ``None``.

        Returns:
            ``True``/``False`` when an SLO latency target and a scored
            ``end_to_end_latency`` criterion are both present, else ``None``.
        """
        if not isinstance(slo, Mapping) or constants.SLO_P95_LATENCY_MS not in slo:
            return None
        operational = pillars.get(constants.PILLAR_OPERATIONAL)
        if not isinstance(operational, Mapping):
            return None
        for criterion in operational.get("criteria", []):
            if criterion.get("id") == _LATENCY_CRITERION_ID:
                score = criterion.get("score")
                if isinstance(score, int) and not isinstance(score, bool):
                    return score >= _WITHIN_SLO_MIN_SCORE
        return None
