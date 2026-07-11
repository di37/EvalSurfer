"""The per-stage diagnosis value object.

:class:`StageDiagnosis` records the health of one pipeline stage after projecting
a report onto it. The projection logic that produces these lives in
:mod:`evalsurfer.analysis.diagnostics.failure_map.map`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StageDiagnosis:
    """The health of one pipeline stage after projecting a report onto it."""

    stage: str
    status: str
    weak_criteria: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Render the diagnosis as a JSON-ready dict.

        Returns:
            ``{"stage", "status", "weak_criteria"}`` with ``weak_criteria`` as a
            list.
        """
        return {
            "stage": self.stage,
            "status": self.status,
            "weak_criteria": list(self.weak_criteria),
        }
