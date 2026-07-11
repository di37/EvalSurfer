"""Reference-text metric value objects.

Frozen dataclasses only: :class:`RougeScore` carries the precision / recall / F1
for a ROUGE variant. The calculations that produce it live in
:mod:`evalsurfer.metrics.quality.text.service`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RougeScore:
    """Precision, recall, and F1 for a ROUGE variant."""

    precision: float
    recall: float
    f1: float
