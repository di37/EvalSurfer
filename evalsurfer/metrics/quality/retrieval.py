"""Deterministic retrieval-quality metrics (Recall@k, Precision@k, MRR).

These score a *ranked list of retrieved document ids* against the *set of
relevant (gold) ids* for a query -- the programmatic half of RAG evaluation that
needs no judge. The same machinery scores tool selection: a tool router is
recall-oriented, so a missed expected tool is a recall error
(:meth:`RetrievalMetrics.tool_selection_recall`).

Everything here is pure and standard-library only -- no model calls. Value
objects are immutable; inputs are never mutated. Magic values come from
:mod:`evalsurfer.constants`.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence

import evalsurfer.constants as constants

__all__ = [
    "RetrievalCase",
    "RetrievalSummary",
    "RetrievalMetrics",
]


def _as_sequence(value: Any, field_name: str) -> list[Any]:
    """Return ``value`` as a list, rejecting strings/bytes and non-sequences.

    Args:
        value: The value that should be an ordered, non-string sequence.
        field_name: Name used in error messages.

    Returns:
        The value as a list.

    Raises:
        TypeError: If ``value`` is a string, bytes, or not a sequence.
    """
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a list, not {type(value).__name__}")
    return list(value)


def _validate_k(k: Any) -> None:
    """Validate an optional rank cutoff ``k``.

    Args:
        k: ``None`` (use the whole list) or a positive integer.

    Raises:
        ValueError: If ``k`` is a boolean, non-integer, or not positive.
    """
    if k is None:
        return
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be None or a positive integer")


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


class RetrievalMetrics:
    """Stateless retrieval-metric calculations over ranked id lists.

    All methods are static: the calculations carry no per-instance state, so the
    class is a cohesive namespace rather than something to instantiate.
    """

    @staticmethod
    def recall_at_k(
        retrieved: Sequence[Any], relevant: Iterable[Any], k: int | None = None
    ) -> float | None:
        """Fraction of relevant ids found in the top ``k`` retrieved.

        Args:
            retrieved: The ranked list of retrieved ids (best first).
            relevant: The set of relevant (gold) ids.
            k: Rank cutoff; ``None`` uses the whole list.

        Returns:
            ``|relevant ∩ top-k| / |relevant|``, or ``None`` when there are no
            relevant ids (recall is then undefined).

        Raises:
            TypeError: If ``retrieved`` is not a list.
            ValueError: If ``k`` is invalid.
        """
        _validate_k(k)
        top = _as_sequence(retrieved, "retrieved")[:k]
        relevant_set = set(relevant)
        if not relevant_set:
            return None
        hits = len(relevant_set.intersection(top))
        return hits / len(relevant_set)

    @staticmethod
    def precision_at_k(
        retrieved: Sequence[Any], relevant: Iterable[Any], k: int | None = None
    ) -> float | None:
        """Fraction of the top ``k`` retrieved ids that are relevant.

        The denominator is the number of ids actually considered
        (``min(k, len(retrieved))``), so a short list is not penalised for
        ``k`` exceeding its length.

        Args:
            retrieved: The ranked list of retrieved ids (best first).
            relevant: The set of relevant (gold) ids.
            k: Rank cutoff; ``None`` uses the whole list.

        Returns:
            ``|relevant ∩ top-k| / |top-k|``, or ``None`` when nothing was
            retrieved (precision is then undefined).

        Raises:
            TypeError: If ``retrieved`` is not a list.
            ValueError: If ``k`` is invalid.
        """
        _validate_k(k)
        top = _as_sequence(retrieved, "retrieved")[:k]
        if not top:
            return None
        relevant_set = set(relevant)
        # Count per slot (not deduplicated) so numerator and denominator agree
        # when the ranked list contains duplicate ids.
        hits = sum(1 for doc in top if doc in relevant_set)
        return hits / len(top)

    @staticmethod
    def reciprocal_rank(
        retrieved: Sequence[Any], relevant: Iterable[Any]
    ) -> float:
        """Reciprocal rank of the first relevant id (``1/rank``), else ``0.0``.

        Args:
            retrieved: The ranked list of retrieved ids (best first).
            relevant: The set of relevant (gold) ids.

        Returns:
            ``1 / position`` of the first relevant id (1-indexed), or ``0.0``
            when none of the retrieved ids are relevant.

        Raises:
            TypeError: If ``retrieved`` is not a list.
        """
        relevant_set = set(relevant)
        for position, doc in enumerate(_as_sequence(retrieved, "retrieved"), start=1):
            if doc in relevant_set:
                return 1.0 / position
        return 0.0

    @staticmethod
    def tool_selection_recall(
        called_tools: Sequence[Any], expected_tools: Iterable[Any]
    ) -> float | None:
        """Recall of the expected tools among those the agent actually called.

        Tool routing is recall-oriented -- a missed expected tool is a recall
        error -- so this is set-based recall (order does not matter).

        Args:
            called_tools: The tool names the agent invoked.
            expected_tools: The tool names it was expected to invoke.

        Returns:
            ``|expected ∩ called| / |expected|``, or ``None`` when no tools were
            expected.

        Raises:
            TypeError: If ``called_tools`` is not a list.
        """
        return RetrievalMetrics.recall_at_k(called_tools, expected_tools, k=None)

    @staticmethod
    def summarize(
        cases: Sequence[RetrievalCase], k: int | None = None
    ) -> RetrievalSummary:
        """Aggregate mean Recall@k / Precision@k / MRR across queries.

        Args:
            cases: The per-query retrieval cases.
            k: A cutoff applied to every case that does not set its own ``k``;
                ``None`` uses each case's own ``k`` (or the whole list).

        Returns:
            The :class:`RetrievalSummary`. ``mean_recall_at_k`` /
            ``mean_precision_at_k`` are ``None`` when no case defines them; the
            MRR is ``0.0`` for an empty input. Values are rounded to
            ``constants.SHARE_PRECISION`` decimals.

        Raises:
            TypeError: If ``cases`` is not a sequence of :class:`RetrievalCase`.
            ValueError: If ``k`` is invalid.
        """
        _validate_k(k)
        if isinstance(cases, (str, bytes)) or not isinstance(cases, Sequence):
            raise TypeError("cases must be a sequence of RetrievalCase")

        recalls: list[float] = []
        precisions: list[float] = []
        rrs: list[float] = []
        query_count = 0
        for case in cases:
            if not isinstance(case, RetrievalCase):
                raise TypeError("each case must be a RetrievalCase")
            query_count += 1
            cutoff = case.k if case.k is not None else k
            recall = RetrievalMetrics.recall_at_k(case.retrieved, case.relevant, cutoff)
            precision = RetrievalMetrics.precision_at_k(
                case.retrieved, case.relevant, cutoff
            )
            if recall is not None:
                recalls.append(recall)
            if precision is not None:
                precisions.append(precision)
            # MRR is only defined for queries that have gold-relevant docs; a
            # query with no gold contributes nothing (mirrors recall's None).
            if case.relevant:
                rrs.append(
                    RetrievalMetrics.reciprocal_rank(case.retrieved, case.relevant)
                )

        digits = constants.SHARE_PRECISION
        return RetrievalSummary(
            query_count=query_count,
            k=k,
            mean_recall_at_k=round(mean(recalls), digits) if recalls else None,
            mean_precision_at_k=(
                round(mean(precisions), digits) if precisions else None
            ),
            mrr=round(mean(rrs), digits) if rrs else None,
        )
