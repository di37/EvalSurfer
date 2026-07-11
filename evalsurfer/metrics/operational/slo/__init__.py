"""Operational auto-scoring from service-level objectives (SLOs).

Where :mod:`evalsurfer.metrics.operational.metrics` turns request traces into raw
numbers (p95 latency, TTFT, cost, failure rate), :class:`OperationalScorer`
turns those numbers into the 1-5 operational criterion scores the rubric expects
by comparing each measured metric against an SLO target. Lower-is-better
metrics score higher the further they sit below their target, following the
bands in :data:`constants.SLO_SCORE_BANDS`.

The SLO targets are the only configurable input, so they are instance state set
in ``__init__``; everything else is pure. Like the rest of the package the
scorer is deterministic, immutable, and standard-library-only -- it never
mutates its inputs and makes no model calls.

The implementation is split across two focused modules -- :mod:`.models` (the
:class:`CriterionScore` / :class:`OperationalScore` value objects) and
:mod:`.scorer` (the :class:`OperationalScorer` itself) -- and re-exported here so
that ``from evalsurfer.metrics.operational.slo import OperationalScorer`` keeps
working.
"""

from evalsurfer.metrics.operational.slo.models import CriterionScore, OperationalScore
from evalsurfer.metrics.operational.slo.scorer import OperationalScorer

__all__ = [
    "CriterionScore",
    "OperationalScore",
    "OperationalScorer",
]
