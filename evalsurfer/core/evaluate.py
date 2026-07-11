"""Core report assembly for EvalSurfer.

:class:`Evaluator` turns a sample plus agent-produced (and optionally
pre-scored) criterion scores into a schema-shaped report: plan → place scores →
recompute category / overall → decide → coverage. It is **CIMAA Core only** —
no Metrics or Analysis imports. Operational auto-scoring and diagnostics are
applied by the Interface pipeline (:mod:`evalsurfer.interface.pipeline`).

Everything here is deterministic, standard-library only, and makes no model
calls; inputs are never mutated.
"""

from __future__ import annotations

from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner, Signals
from evalsurfer.core.scoring import ScoringModel

__all__ = ["Evaluator"]

_SAFETY_CRITERION_IDS = frozenset(
    criterion.id
    for criterion in EvaluationPlanner.CRITERIA
    if criterion.category == constants.CATEGORY_SAFETY
)


class Evaluator:
    """Assemble a schema-shaped report from a sample plus criterion scores.

    Stateless: every input is passed to :meth:`evaluate`. Does not auto-score
    operational traces or attach diagnostics — callers that need the full CIMAA
    run should use :func:`evalsurfer.interface.pipeline.evaluate`.
    """

    @classmethod
    def evaluate(cls, request: Mapping[str, Any]) -> dict[str, Any]:
        """Build a report from an evaluation request (scores already supplied).

        The request may contain: ``sample`` (or the request itself); ``scores``;
        ``evidence``; ``top_issues``; ``not_assessed``; ``summary``;
        ``failure_rate``; ``p95_within_slo``; ``task_failed``.

        Args:
            request: The evaluation request mapping.

        Returns:
            A report dict with ``overall``, report section blocks, ``decision``,
            ``top_issues``, ``not_assessed``, ``coverage``, and ``metadata``.
            No ``diagnostics`` key — Interface attaches that.

        Raises:
            TypeError: If ``request`` is not a mapping.
        """
        if not isinstance(request, Mapping):
            raise TypeError("request must be a mapping")

        sample = request.get("sample", request)
        signals = Signals.from_sample(sample)
        plan = EvaluationPlanner.plan(signals)

        provided = cls.flatten_scores(request.get("scores"))
        evidence = request.get("evidence") or {}
        applicable = {criterion.id for criterion in plan.applicable_criteria()}

        categories = cls._build_categories(applicable, provided, evidence)

        for category in categories.values():
            category["score"] = ScoringModel.category_score(
                [criterion["score"] for criterion in category["criteria"]]
            )
        overall = ScoringModel.overall_score(
            [category["score"] for category in categories.values()]
        )

        layers = cls._nest_by_layer(categories)
        safety_score = categories.get(constants.CATEGORY_SAFETY, {}).get("score")

        top_issues = [
            issue for issue in (request.get("top_issues") or []) if isinstance(issue, Mapping)
        ]
        decision = ScoringModel.decide(
            overall,
            safety_score,
            critical_safety_issue=cls._has_critical_safety_issue(top_issues),
            failure_rate=request.get("failure_rate"),
            p95_within_slo=request.get("p95_within_slo"),
            task_failed=bool(request.get("task_failed", False)),
        )

        return {
            "overall": {
                # ``null`` (not a misleading 0.0) when nothing was assessed; the
                # report schema and ReportValidator both permit a null overall.
                "score": overall,
                "decision": decision,
                "summary": str(request.get("summary", "")),
            },
            **layers,
            "decision": decision,
            "top_issues": [dict(issue) for issue in top_issues],
            "not_assessed": list(request.get("not_assessed") or []),
            "coverage": EvaluationPlanner.coverage(plan, layers),
            "metadata": {
                "framework": constants.FRAMEWORK_NAME,
                "version": constants.FRAMEWORK_VERSION,
            },
        }

    @staticmethod
    def flatten_scores(scores: Any) -> dict[str, int]:
        """Flatten provided scores to a criterion-id -> score mapping."""
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
    def _build_categories(
        cls,
        applicable: set[str],
        provided: Mapping[str, int],
        evidence: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Build category blocks from applicable / provided criterion scores."""
        categories: dict[str, Any] = {}
        for category_id in constants.CATEGORIES:
            criteria = [
                {
                    "id": criterion.id,
                    "name": criterion.name,
                    "score": provided.get(criterion.id),
                    "evidence": str(evidence.get(criterion.id, "")),
                }
                for criterion in EvaluationPlanner.CRITERIA
                if criterion.category == category_id
                and (criterion.id in applicable or criterion.id in provided)
            ]
            if criteria:
                categories[category_id] = {"criteria": criteria}
        return categories

    @staticmethod
    def _nest_by_layer(categories: Mapping[str, Any]) -> dict[str, Any]:
        """Group scored categories under their report section keys."""
        layers: dict[str, Any] = {}
        for layer_id in constants.LAYERS:
            block = {
                category_id: categories[category_id]
                for category_id in constants.CATEGORIES_BY_LAYER[layer_id]
                if category_id in categories
            }
            if block:
                layers[layer_id] = block
        return layers

    @staticmethod
    def _has_critical_safety_issue(top_issues: Any) -> bool:
        """Whether a critical top issue names a safety-category criterion."""
        return any(
            issue.get("severity") == constants.SEVERITY_CRITICAL
            and issue.get("criterion_id") in _SAFETY_CRITERION_IDS
            for issue in top_issues
            if isinstance(issue, Mapping)
        )
