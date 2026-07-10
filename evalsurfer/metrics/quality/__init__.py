"""Deterministic quality metrics -- the reference-based / programmatic layer.

Retrieval (:class:`RetrievalMetrics`), match & classification
(:class:`MatchMetrics`), and reference-text (:class:`TextMetrics`) scores that
compare an output to a gold reference with **zero model calls** -- the
programmatic half of an evaluation, complementing the agent's judgment.
"""

from evalsurfer.metrics.quality.matching import ClassificationReport, MatchMetrics
from evalsurfer.metrics.quality.retrieval import (
    RetrievalCase,
    RetrievalMetrics,
    RetrievalSummary,
)
from evalsurfer.metrics.quality.text import RougeScore, TextMetrics

__all__ = [
    "RetrievalMetrics",
    "RetrievalCase",
    "RetrievalSummary",
    "MatchMetrics",
    "ClassificationReport",
    "TextMetrics",
    "RougeScore",
]
