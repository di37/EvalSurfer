"""The maturity-ladder value object.

:class:`MaturityLevel` is one named stage on the six-level maturity ladder. The
classifier that places a target on the ladder lives in
:mod:`evalsurfer.analysis.diagnostics.maturity.classifier`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaturityLevel:
    """A named stage on the maturity ladder.

    Attributes:
        level: The rung number, between ``MIN_MATURITY_LEVEL`` and
            ``MAX_MATURITY_LEVEL`` inclusive.
        name: The framework name for the stage.
        driver: Why the evidence justifies this stage, phrased for the
            ``rationale`` field.
        recommendation: What to add to reach the next stage; empty at the top of
            the ladder.
    """

    level: int
    name: str
    driver: str
    recommendation: str
