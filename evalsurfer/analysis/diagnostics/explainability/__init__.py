"""SHAP-style deduction attribution for EvalSurfer reports.

An explainability layer over the scoring model. Because that model is linear
(a category score is the mean of its assessed criterion scores times
``constants.SCORE_SCALE``, and the overall score is the mean of the assessed
category scores), every point lost from a perfect ``constants.PERFECT_SCORE`` can
be attributed in closed form to the exact criterion that lost it -- no sampling
or feature-permutation needed.

Attribution:
* perfect = ``PERFECT_SCORE`` (every assessed criterion scored the maximum,
  ``CRITERION_MAX_SCORE``)
* points_lost(c) = (CRITERION_MAX_SCORE - score_c) * SCORE_SCALE / (n_p * P)
    - n_p = number of assessed criteria in criterion c's category p
    - P   = number of assessed categories
* the deductions sum to exactly (PERFECT_SCORE - the exact overall);
  ``reconstructed`` subtracts them from ``PERFECT_SCORE``. This matches the
  reported ``overall`` up to the scoring model's category-level rounding (both
  values are individually correct).

Deterministic, standard library only, no model calls. Inputs are never mutated;
every result is a freshly built object.

The implementation is split across two focused modules -- :mod:`.models` (the
:class:`Deduction` value object) and :mod:`.explainer` (the :class:`Explainer`
service) -- and re-exported here so that
``from evalsurfer.analysis.diagnostics.explainability import Explainer`` keeps
working.
"""

from evalsurfer.analysis.diagnostics.explainability.explainer import Explainer
from evalsurfer.analysis.diagnostics.explainability.models import Deduction

__all__ = [
    "Deduction",
    "Explainer",
]
