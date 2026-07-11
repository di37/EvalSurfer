"""Deterministic match & classification metrics (exact match, accuracy, F1).

For extraction / short-answer QA these compare a predicted string to a gold
string: :meth:`MatchMetrics.exact_match` (SQuAD-normalised equality) and
:meth:`MatchMetrics.token_f1` (token-overlap F1). For classification they score
predicted labels against gold labels: :meth:`MatchMetrics.accuracy` and
:meth:`MatchMetrics.classification_report` (per-label precision / recall / F1
with micro or macro averaging, plus a binary mode).

Everything here is pure and standard-library only -- no model calls. Value
objects are immutable; inputs are never mutated. Magic values come from
:mod:`evalsurfer.constants`.

The implementation is split across three focused modules -- :mod:`.helpers` (the
shared F1/pairing/label utilities), :mod:`.models` (the
:class:`ClassificationReport` value object), and :mod:`.service` (the
:class:`MatchMetrics` calculations) -- and re-exported here so that ``from
evalsurfer.metrics.quality.matching import MatchMetrics`` keeps working.
"""

from evalsurfer.metrics.quality.matching.models import ClassificationReport
from evalsurfer.metrics.quality.matching.service import MatchMetrics

__all__ = [
    "ClassificationReport",
    "MatchMetrics",
]
