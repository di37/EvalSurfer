"""The review-gate value objects.

:class:`FlaggedCriterion` records a criterion whose judged confidence fell below
the review threshold, and :class:`ReviewRecommendation` bundles whether a report
needs a human reviewer and why. The gate that produces these lives in
:mod:`evalsurfer.analysis.diagnostics.review_gate.gate`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import evalsurfer.constants as constants


@dataclass(frozen=True)
class FlaggedCriterion:
    """A criterion whose judged confidence fell below the review threshold."""

    id: str | None
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Render the flagged criterion as a JSON-ready dict.

        Returns:
            A mapping of the criterion ``id`` and its rounded ``confidence``.
        """
        return {"id": self.id, constants.CONFIDENCE_FIELD: self.confidence}


@dataclass(frozen=True)
class ReviewRecommendation:
    """Whether a report needs a human reviewer, and why."""

    needs_human_review: bool
    reasons: tuple[str, ...]
    flagged_criteria: tuple[FlaggedCriterion, ...]
    low_confidence_count: int

    def to_dict(self) -> dict[str, Any]:
        """Render the recommendation as a JSON-ready dict.

        Returns:
            ``{"needs_human_review": bool, "reasons": [...],
            "flagged_criteria": [...], "low_confidence_count": int}``.
        """
        return {
            "needs_human_review": self.needs_human_review,
            "reasons": list(self.reasons),
            "flagged_criteria": [
                criterion.to_dict() for criterion in self.flagged_criteria
            ],
            "low_confidence_count": self.low_confidence_count,
        }
