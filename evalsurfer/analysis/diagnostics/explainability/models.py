"""The deduction value object.

:class:`Deduction` records one assessed criterion's contribution to the points
lost from perfect. The attribution logic that produces these lives in
:mod:`evalsurfer.analysis.diagnostics.explainability.explainer`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Deduction:
    """One assessed criterion's contribution to the points lost from perfect."""

    id: str | None
    name: str
    category: str
    score: int
    points_lost: float

    def to_dict(self) -> dict[str, Any]:
        """Render this deduction as a plain dict for JSON output.

        Returns:
            A dict with ``id``, ``name``, ``category``, ``score``, and
            ``points_lost`` keys.
        """
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "score": self.score,
            "points_lost": self.points_lost,
        }
