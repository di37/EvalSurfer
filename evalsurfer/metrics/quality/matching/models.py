"""Match & classification metric value objects.

Frozen dataclasses only: :class:`ClassificationReport` carries the aggregate and
per-label classification scores. The calculations that produce it live in
:mod:`evalsurfer.metrics.quality.matching.service`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassificationReport:
    """Aggregate and per-label classification scores."""

    accuracy: float
    precision: float
    recall: float
    f1: float
    average: str
    support: int
    per_label: dict[str, dict[str, float]]
