"""The retrieval-metric calculations over ranked id lists.

:class:`RetrievalMetrics` groups the stateless retrieval calculations (Recall@k,
Precision@k, MRR, tool-selection recall) into a single cohesive namespace. All
methods are static: the calculations carry no per-instance state, operate over
the value objects in :mod:`evalsurfer.metrics.quality.retrieval.models`, and make
no model calls. Magic values come from :mod:`evalsurfer.constants`.
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Iterable, Sequence

import evalsurfer.constants as constants
from evalsurfer.metrics.quality.retrieval.helpers import _as_sequence, _validate_k
from evalsurfer.metrics.quality.retrieval.models import RetrievalCase, RetrievalSummary


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
            MRR is ``None`` for an empty input or when no case has gold-relevant
            docs. Values are rounded to ``constants.SHARE_PRECISION`` decimals.

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
