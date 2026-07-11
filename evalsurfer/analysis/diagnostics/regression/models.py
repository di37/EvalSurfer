"""The per-criterion diff value object.

:class:`CriterionDiff` records how one criterion moved between two reports,
matched by id within a single category. The diff logic that produces these lives in
:mod:`evalsurfer.analysis.diagnostics.regression.differ`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CriterionDiff:
    """How one criterion moved, matched by id within a single category."""

    id: str
    name: str
    before: int | None
    after: int | None
    delta: int | None
    change: str

    def to_dict(self) -> dict[str, Any]:
        """Render the criterion diff as a JSON-ready dict.

        Returns:
            A dict with ``id``, ``name``, ``before``, ``after``, ``delta``, and
            ``change`` keys.
        """
        return {
            "id": self.id,
            "name": self.name,
            "before": self.before,
            "after": self.after,
            "delta": self.delta,
            "change": self.change,
        }
