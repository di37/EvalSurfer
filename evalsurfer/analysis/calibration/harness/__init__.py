"""Harness-invariant judgment reliability -- is the verdict a property of the
target or of the judging harness?

:class:`HarnessInvariance` decomposes a ``target x harness x replication`` grid
of judgments (the same portable skill run across different coding-agent
harnesses) into variance components, derives generalizability / dependability
coefficients -- including gate dependability at the pass/fail cut scores -- and
profiles which rubric criteria are harness-sensitive. Deterministic, standard
library only, no model calls. Design: ``docs/design/harness-invariance.md``.
"""

from evalsurfer.analysis.calibration.harness.decomposition import HarnessInvariance
from evalsurfer.analysis.calibration.harness.models import (
    DStudyPoint,
    Judgment,
    VarianceComponents,
)

__all__ = ["HarnessInvariance", "Judgment", "VarianceComponents", "DStudyPoint"]
