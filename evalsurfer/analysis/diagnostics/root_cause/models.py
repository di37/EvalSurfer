"""The contribution value object.

:class:`Contribution` records lost points attributed to one category or rubric
group. The attribution logic that produces these lives in
:mod:`evalsurfer.analysis.diagnostics.root_cause.analyzer`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Contribution:
    """Lost points attributed to one category or rubric group."""

    label: str
    lost: int
    share: float

    def as_dict(self, key: str) -> dict[str, Any]:
        """Render the contribution as a plain dict keyed by ``key``.

        Args:
            key: The label field name, either ``"category"`` or ``"group"``.

        Returns:
            ``{key: label, "lost": lost, "share": share}``.
        """
        return {key: self.label, "lost": self.lost, "share": self.share}
