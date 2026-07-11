"""Plan value objects -- the rubric criteria and the resolved plan.

Frozen dataclasses only: :class:`Criterion` (a rubric criterion and the signals
it requires), the ``Planned*`` results of resolving one against a
:class:`~evalsurfer.core.planner.signals.Signals` snapshot, and the
:class:`EvaluationPlan` that a planner produces. The resolution logic lives in
:mod:`evalsurfer.core.planner.engine`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import evalsurfer.constants as constants

__all__ = ["Criterion", "PlannedCriterion", "PlannedCategory", "EvaluationPlan"]


@dataclass(frozen=True)
class Criterion:
    """A rubric criterion and the signals required to assess it."""

    category: str
    group: str | None
    id: str
    name: str
    required: tuple[str, ...]


@dataclass(frozen=True)
class PlannedCriterion:
    """A criterion after applicability is resolved against the signals."""

    category: str
    group: str | None
    id: str
    name: str
    applicable: bool
    reason: str


@dataclass(frozen=True)
class PlannedCategory:
    """A rubric category plus its planned criteria."""

    id: str
    applicable: bool
    criteria: tuple[PlannedCriterion, ...]


@dataclass(frozen=True)
class EvaluationPlan:
    """The full adaptive plan for one target."""

    categories: tuple[PlannedCategory, ...]

    def applicable_criteria(self) -> tuple[PlannedCriterion, ...]:
        """Return every applicable criterion across all categories."""
        return tuple(
            criterion
            for category in self.categories
            for criterion in category.criteria
            if criterion.applicable
        )

    def to_dict(self) -> dict[str, Any]:
        """Render the plan (and its planned coverage) as a JSON-ready dict.

        Categories are nested under the ``metrics`` / ``assurance`` report
        sections, matching the report structure.
        """
        from evalsurfer.core.planner.engine import EvaluationPlanner

        by_id = {category.id: category for category in self.categories}
        result: dict[str, Any] = {}
        for layer_id in constants.LAYERS:
            block = {
                category_id: {
                    "applicable": by_id[category_id].applicable,
                    "criteria": [
                        {
                            "id": criterion.id,
                            "name": criterion.name,
                            "group": criterion.group,
                            "applicable": criterion.applicable,
                            "reason": criterion.reason,
                        }
                        for criterion in by_id[category_id].criteria
                    ],
                }
                for category_id in constants.CATEGORIES_BY_LAYER[layer_id]
                if category_id in by_id
            }
            if block:
                result[layer_id] = block
        result["coverage"] = EvaluationPlanner.planned_coverage(self)
        return result
