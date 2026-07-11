"""Judge-confidence human-review gate for EvalSurfer.

An LLM judge is not equally sure about every criterion. :class:`ReviewGate`
reads the per-criterion confidence a judge attached to a report and decides
whether the result should be escalated to a human. A criterion is flagged when
its confidence falls below a configurable threshold; any ``critical`` top issue
also forces a review. Criteria that carry no confidence are left alone.

The threshold is the only configurable input, so it is instance state set in
``__init__``; everything else is pure. Like the other diagnostic layers, the
gate is deterministic and immutable: it never mutates the report, makes no model
calls, and depends only on the standard library and the sibling
:mod:`scoring` module.

The implementation is split across two focused modules -- :mod:`.models` (the
:class:`FlaggedCriterion` and :class:`ReviewRecommendation` value objects) and
:mod:`.gate` (the :class:`ReviewGate` service) -- and re-exported here so that
``from evalsurfer.analysis.diagnostics.review_gate import ReviewGate`` keeps
working.
"""

from evalsurfer.analysis.diagnostics.review_gate.gate import ReviewGate
from evalsurfer.analysis.diagnostics.review_gate.models import (
    FlaggedCriterion,
    ReviewRecommendation,
)

__all__ = [
    "FlaggedCriterion",
    "ReviewRecommendation",
    "ReviewGate",
]
