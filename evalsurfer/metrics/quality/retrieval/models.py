"""Retrieval-quality value objects -- the per-query case and its summary.

Frozen dataclasses only: :class:`RetrievalCase` (one query's ranked retrieval
outcome, validated on construction, plus its :meth:`RetrievalCase.from_mapping`
parser) and :class:`RetrievalSummary` (mean metrics across many queries). The
calculations that consume them live in
:mod:`evalsurfer.metrics.quality.retrieval.service`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from evalsurfer.metrics.quality.retrieval.helpers import _as_sequence, _validate_k


@dataclass(frozen=True)
class RetrievalCase:
    """One query's ranked retrieval outcome against its gold-relevant ids."""

    retrieved: tuple[str, ...]
    relevant: frozenset[str]
    k: int | None = None

    def __post_init__(self) -> None:
        """Validate the case on construction (any path), like CalibrationCase.

        Raises:
            TypeError: If ``retrieved`` is not a tuple or ``relevant`` is not a
                frozenset.
            ValueError: If ``k`` is not ``None`` or a positive integer.
        """
        if not isinstance(self.retrieved, tuple):
            raise TypeError("retrieved must be a tuple")
        if not isinstance(self.relevant, frozenset):
            raise TypeError("relevant must be a frozenset")
        _validate_k(self.k)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RetrievalCase":
        """Build a case from ``{"retrieved": [...], "relevant": [...], "k": n}``.

        Ids are coerced to strings so an int id and its string form compare
        equal (``3`` and ``"3"``).

        Args:
            data: The case mapping. ``retrieved`` is the ranked id list;
                ``relevant`` is the gold id set; ``k`` is an optional cutoff.

        Returns:
            The parsed :class:`RetrievalCase`.

        Raises:
            TypeError: If ``data`` is not a mapping or a field has the wrong type.
            ValueError: If ``k`` is invalid.
        """
        if not isinstance(data, Mapping):
            raise TypeError("retrieval case must be a mapping")
        retrieved = _as_sequence(data.get("retrieved", []), "retrieved")
        relevant = _as_sequence(data.get("relevant", []), "relevant")
        k = data.get("k")
        _validate_k(k)
        return cls(
            retrieved=tuple(str(doc) for doc in retrieved),
            relevant=frozenset(str(doc) for doc in relevant),
            k=k,
        )


@dataclass(frozen=True)
class RetrievalSummary:
    """Mean retrieval metrics across many queries."""

    query_count: int
    k: int | None
    mean_recall_at_k: float | None
    mean_precision_at_k: float | None
    mrr: float | None
