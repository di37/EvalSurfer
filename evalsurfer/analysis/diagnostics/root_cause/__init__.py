"""Root-cause attribution for EvalSurfer reports.

Given a produced report, :class:`RootCauseAnalyzer` attributes its *lost
quality* -- the points each assessed criterion fell short of a perfect
``constants.CRITERION_MAX_SCORE`` -- back to the categories and rubric groups
responsible. This turns a flat set of criterion scores into a ranked diagnosis
of where quality was lost, so a reviewer can see the biggest contributors at a
glance.

Lost points for one assessed criterion are ``CRITERION_MAX_SCORE - score`` (0
for a perfect score, up to ``CRITERION_MAX_SCORE - CRITERION_MIN_SCORE`` for the
lowest). Not-assessed criteria (``score`` is ``None``) are ignored. Each
criterion is mapped to its canonical category and rubric group via
:data:`planner.EvaluationPlanner.CRITERIA`; safety and operational criteria have
no subgroup, so the category name doubles as the group label. Unknown or missing
ids fall back to the report's own category key so no lost points are dropped.

Standard library only, no model calls -- a diagnostic layer on top of the
scored report that never mutates its input.

The implementation is split across two focused modules -- :mod:`.models` (the
:class:`Contribution` value object) and :mod:`.analyzer` (the
:class:`RootCauseAnalyzer` service) -- and re-exported here so that
``from evalsurfer.analysis.diagnostics.root_cause import RootCauseAnalyzer``
keeps working.
"""

from evalsurfer.analysis.diagnostics.root_cause.analyzer import RootCauseAnalyzer
from evalsurfer.analysis.diagnostics.root_cause.models import Contribution

__all__ = [
    "Contribution",
    "RootCauseAnalyzer",
]
