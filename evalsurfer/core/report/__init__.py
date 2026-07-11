"""Deterministic report validation and release gating for EvalSurfer.

Two pure, standard-library-only services that operate on an already-produced
report. :class:`ReportValidator` performs *structural* validation entirely in
Python -- required keys are present, decisions and severities are drawn from the
allowed vocabularies, and every score sits in range -- with no JSON Schema
dependency and without reading any file. It accumulates every problem it finds
rather than stopping at the first. :class:`Gate` turns a report's decision into a
pass/fail release signal by ranking it against a required minimum decision.

Both are deterministic and immutable: they make no model calls, never mutate the
report, and rank decisions using :data:`constants.DECISION_RANK`. Report
traversal is delegated to :class:`ScoringModel`, which owns it.

The implementation is split across focused modules -- :mod:`.models` (the result
value objects), :mod:`.validator` (:class:`ReportValidator`), and :mod:`.gate`
(:class:`Gate`) -- re-exported here so that
``from evalsurfer.core.report import ReportValidator, Gate`` keeps working.
"""

from evalsurfer.core.report.gate import Gate
from evalsurfer.core.report.models import GateResult, ValidationResult
from evalsurfer.core.report.validator import ReportValidator

__all__ = [
    "ValidationResult",
    "GateResult",
    "ReportValidator",
    "Gate",
]
