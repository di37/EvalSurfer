"""Deterministic retrieval-quality metrics (Recall@k, Precision@k, MRR).

These score a *ranked list of retrieved document ids* against the *set of
relevant (gold) ids* for a query -- the programmatic half of RAG evaluation that
needs no judge. The same machinery scores tool selection: a tool router is
recall-oriented, so a missed expected tool is a recall error
(:meth:`RetrievalMetrics.tool_selection_recall`).

Everything here is pure and standard-library only -- no model calls. Value
objects are immutable; inputs are never mutated. Magic values come from
:mod:`evalsurfer.constants`.

The implementation is split across three focused modules -- :mod:`.helpers` (the
shared sequence/cutoff validators), :mod:`.models` (the :class:`RetrievalCase` /
:class:`RetrievalSummary` value objects), and :mod:`.service` (the
:class:`RetrievalMetrics` calculations) -- and re-exported here so that ``from
evalsurfer.metrics.quality.retrieval import RetrievalMetrics`` keeps working.
"""

from evalsurfer.metrics.quality.retrieval.models import RetrievalCase, RetrievalSummary
from evalsurfer.metrics.quality.retrieval.service import RetrievalMetrics

__all__ = [
    "RetrievalCase",
    "RetrievalSummary",
    "RetrievalMetrics",
]
