"""Version / regression diff for EvalSurfer reports.

Compare a *before* report against an *after* report and describe what moved:
:class:`RegressionDiffer` reports the overall-score delta, any decision change,
per-category score deltas, a criterion-by-criterion diff (matched by id within the
same category), the coverage delta, and the ids that regressed or improved.

This is a diagnostic layer over two already-produced reports. It reads the
scores that are present in each report rather than recomputing them, tolerates
any optional key being absent, and never mutates its inputs. Stateless service,
standard library only, no model calls.

The implementation is split across three focused modules -- :mod:`.models` (the
:class:`CriterionDiff` value object), :mod:`.helpers` (the coercion helpers), and
:mod:`.differ` (the :class:`RegressionDiffer` service) -- and re-exported here so
that ``from evalsurfer.analysis.diagnostics.regression import RegressionDiffer``
keeps working.
"""

from evalsurfer.analysis.diagnostics.regression.differ import RegressionDiffer
from evalsurfer.analysis.diagnostics.regression.models import CriterionDiff

__all__ = [
    "CriterionDiff",
    "RegressionDiffer",
]
