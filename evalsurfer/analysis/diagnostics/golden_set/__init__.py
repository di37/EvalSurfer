"""Golden-set validation for the deterministic layer (planner + scoring).

A golden set is a small, hand-audited oracle: for each case the *expected*
applicable categories and the *expected* pass/fix/fail decision were computed by
hand from the documented rules, then frozen here as constants. :class:`GoldenSet`
re-derives both from the code under test (:meth:`EvaluationPlanner.plan` and
:meth:`ScoringModel.category_score` / :meth:`~ScoringModel.overall_score` /
:meth:`~ScoringModel.decide`) and reports any mismatch. If the planner's gating
or the scoring thresholds ever drift, a case flips to ``ok: False`` and names the
discrepancy.

This is a pure regression harness: standard library only, no model calls, no
third-party dependencies, and it never mutates its inputs.

The implementation is split across two focused modules -- :mod:`.models` (the
:class:`GoldenCase` value object and its validation) and :mod:`.set` (the
:class:`GoldenSet` service and the ``GOLDEN_CASES`` oracle) -- and re-exported
here so that ``from evalsurfer.analysis.diagnostics.golden_set import GoldenSet``
keeps working.
"""

from evalsurfer.analysis.diagnostics.golden_set.models import GoldenCase
from evalsurfer.analysis.diagnostics.golden_set.set import GOLDEN_CASES, GoldenSet

__all__ = [
    "GoldenCase",
    "GOLDEN_CASES",
    "GoldenSet",
]
