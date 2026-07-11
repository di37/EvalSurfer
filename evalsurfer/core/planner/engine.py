"""The adaptive evaluation planner.

:class:`EvaluationPlanner` resolves which categories and criteria apply for a
:class:`~evalsurfer.core.planner.signals.Signals` snapshot -- the deterministic
"methodology" layer that decides which signal gates which criterion. It is
stateless (the rubric catalog is a class attribute), makes no model calls, has
no third-party dependencies, and plans over :data:`constants.CRITERIA_CATALOG`.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.core.planner.models import (
    Criterion,
    EvaluationPlan,
    PlannedCategory,
    PlannedCriterion,
)
from evalsurfer.core.planner.signals import Signals
from evalsurfer.core.scoring import ScoringModel

__all__ = ["EvaluationPlanner"]


class EvaluationPlanner:
    """Resolve which categories and criteria apply for a set of signals.

    Stateless: the rubric catalog is a class attribute and the methods derive a
    plan or coverage without per-instance state.
    """

    #: The rubric criteria, built once from the central catalog.
    CRITERIA: tuple[Criterion, ...] = tuple(
        Criterion(category, group, cid, name, required)
        for category, group, cid, name, required in constants.CRITERIA_CATALOG
    )

    @staticmethod
    def _missing_signals(signals: Signals, required: Iterable[str]) -> list[str]:
        """Return the required signal names that are not set on ``signals``."""
        return [name for name in required if not getattr(signals, name)]

    @staticmethod
    def _reason(missing: Sequence[str]) -> str:
        """Build the human-readable reason for a criterion's applicability."""
        if not missing:
            return "Applicable — all required inputs present."
        described = ", ".join(constants.SIGNAL_DESCRIPTIONS[name] for name in missing)
        return f"Skipped — missing: {described}."

    @classmethod
    def _plan_criterion(cls, criterion: Criterion, signals: Signals) -> PlannedCriterion:
        """Resolve one criterion's applicability against the signals."""
        missing = cls._missing_signals(signals, criterion.required)
        return PlannedCriterion(
            category=criterion.category,
            group=criterion.group,
            id=criterion.id,
            name=criterion.name,
            applicable=not missing,
            reason=cls._reason(missing),
        )

    @classmethod
    def plan(cls, signals: Signals) -> EvaluationPlan:
        """Resolve which categories and criteria apply for the given signals.

        Args:
            signals: The evidence snapshot for the target.

        Returns:
            The resolved :class:`EvaluationPlan`.

        Raises:
            TypeError: If ``signals`` is not a :class:`Signals` instance.
        """
        if not isinstance(signals, Signals):
            raise TypeError("signals must be a Signals instance")

        planned = [cls._plan_criterion(criterion, signals) for criterion in cls.CRITERIA]
        categories = []
        for category_id in constants.CATEGORIES:
            members = tuple(criterion for criterion in planned if criterion.category == category_id)
            categories.append(
                PlannedCategory(
                    id=category_id,
                    applicable=any(criterion.applicable for criterion in members),
                    criteria=members,
                )
            )
        return EvaluationPlan(categories=tuple(categories))

    @staticmethod
    def planned_coverage(plan: EvaluationPlan) -> dict[str, Any]:
        """Summarise how much of the rubric the plan says applies.

        Args:
            plan: A resolved plan.

        Returns:
            Counts of applicable categories/criteria and an applicable-over-total
            ``score`` rounded to ``SHARE_PRECISION`` decimals.
        """
        criteria = [criterion for category in plan.categories for criterion in category.criteria]
        applicable = [criterion for criterion in criteria if criterion.applicable]
        applicable_categories = [category for category in plan.categories if category.applicable]
        total = len(criteria)
        return {
            "applicable_categories": len(applicable_categories),
            "total_categories": len(plan.categories),
            "applicable_criteria": len(applicable),
            "total_criteria": total,
            "score": round(len(applicable) / total, constants.SHARE_PRECISION) if total else 0.0,
        }

    @staticmethod
    def coverage(plan: EvaluationPlan, report: Mapping[str, Any]) -> dict[str, Any]:
        """Compare a plan against a produced report: applied vs assessed.

        Args:
            plan: The plan that was intended for the target.
            report: The report the judge produced.

        Returns:
            The count of applicable criteria, how many were assessed, the
            assessed-over-applicable ``score``, and the ``missing`` applicable
            criteria the report never scored.
        """
        applicable = {criterion.id for criterion in plan.applicable_criteria()}
        assessed = {
            criterion.get("id")
            for _, criterion in ScoringModel.assessed_criteria(report)
            if isinstance(criterion.get("id"), str)
        }
        covered = applicable & assessed
        return {
            "applicable": len(applicable),
            "assessed": len(covered),
            "score": round(len(covered) / len(applicable), constants.SHARE_PRECISION) if applicable else 0.0,
            "missing": sorted(applicable - assessed),
        }
