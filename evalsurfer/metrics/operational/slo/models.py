"""SLO auto-scoring value objects -- the criterion and category scores.

Frozen dataclasses only: :class:`CriterionScore` (one operational criterion's
SLO-derived score plus its evidence) and :class:`OperationalScore` (the category's
full auto-scoring result), each with a ``to_dict`` renderer. The scoring logic
that produces them lives in :mod:`evalsurfer.metrics.operational.slo.scorer`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CriterionScore:
    """One operational criterion's SLO-derived score plus its evidence."""

    id: str
    name: str
    score: int | None
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        """Render the criterion score as a JSON-ready dict.

        Returns:
            ``{"id": str, "name": str, "score": int | None, "evidence": str}``.
        """
        return {
            "id": self.id,
            "name": self.name,
            "score": self.score,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class OperationalScore:
    """The operational category's SLO auto-scoring result."""

    criteria: tuple[CriterionScore, ...]
    category_score: float | None

    def to_dict(self) -> dict[str, Any]:
        """Render the operational score as a JSON-ready dict.

        Returns:
            ``{"criteria": [...], "category_score": float | None}`` where each
            entry is a :meth:`CriterionScore.to_dict`.
        """
        return {
            "criteria": [criterion.to_dict() for criterion in self.criteria],
            "category_score": self.category_score,
        }
