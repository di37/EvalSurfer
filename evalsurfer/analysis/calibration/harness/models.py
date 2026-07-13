"""Harness-invariance value objects -- immutable containers for the decomposition.

The frozen dataclasses that carry a parsed judgment grid and the estimated
variance components of the ``target x harness x replication`` design
(see ``docs/design/harness-invariance.md``). The stateless calculations that
produce and consume them live in
:mod:`evalsurfer.analysis.calibration.harness.decomposition`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import evalsurfer.constants as constants

__all__ = ["Judgment", "VarianceComponents", "DStudyPoint"]


@dataclass(frozen=True)
class Judgment:
    """One parsed judgment: harness ``harness`` judged ``target`` on run ``replication``.

    ``decision`` is kept raw (validity is the decision analysis' concern);
    ``criteria`` maps criterion id to an assessed 1-5 score or ``None``.
    """

    target: str
    harness: str
    replication: int
    score: float
    decision: str | None = None
    criteria: Mapping[str, int | None] | None = None


@dataclass(frozen=True)
class VarianceComponents:
    """Estimated variance components of a ``target x harness (x replication)`` grid.

    In the normal design (``n_replications >= 2``) the four components are
    ``target`` / ``harness`` / ``interaction`` / ``replication`` and ``residual``
    is ``None``. With a single replication per cell the interaction and
    replication noise are mathematically confounded: ``confounded`` is ``True``,
    ``interaction`` and ``replication`` are ``None``, and their sum is reported
    as ``residual``.
    """

    target: float
    harness: float
    interaction: float | None
    replication: float | None
    residual: float | None
    clamped: tuple[str, ...]
    confounded: bool
    grand_mean: float
    n_targets: int
    n_harnesses: int
    n_replications: int

    def total(self) -> float:
        """Total estimated variance across all components."""
        error = self.residual if self.confounded else (
            (self.interaction or 0.0) + (self.replication or 0.0)
        )
        return self.target + self.harness + (error or 0.0)

    def relative_error(self, n_harnesses: int, n_replications: int | None) -> float:
        """Relative (norm-referenced) error variance for an averaged design.

        Args:
            n_harnesses: The hypothetical number of harnesses averaged over.
            n_replications: The hypothetical replications per harness; ignored
                in confounded mode (there is no separable replication term).

        Returns:
            ``sigma2_delta`` for a mean over the given design.
        """
        if self.confounded:
            return (self.residual or 0.0) / n_harnesses
        runs = n_harnesses * (n_replications or 1)
        return (self.interaction or 0.0) / n_harnesses + (self.replication or 0.0) / runs

    def absolute_error(self, n_harnesses: int, n_replications: int | None) -> float:
        """Absolute (criterion-referenced) error variance for an averaged design."""
        return self.harness / n_harnesses + self.relative_error(
            n_harnesses, n_replications
        )

    def to_dict(self) -> dict[str, Any]:
        """Render the components rounded to ``constants.SHARE_PRECISION``."""
        digits = constants.SHARE_PRECISION

        def _round(value: float | None) -> float | None:
            return None if value is None else round(value, digits)

        return {
            constants.FACET_TARGET: _round(self.target),
            constants.FACET_HARNESS: _round(self.harness),
            constants.FACET_INTERACTION: _round(self.interaction),
            constants.FACET_REPLICATION: _round(self.replication),
            constants.FACET_RESIDUAL: _round(self.residual),
            "clamped": list(self.clamped),
        }


@dataclass(frozen=True)
class DStudyPoint:
    """One D-study grid point: coefficients for ``harnesses x replications``."""

    harnesses: int
    replications: int | None
    generalizability: float
    dependability: float

    def to_dict(self) -> dict[str, Any]:
        """Render the point with coefficients rounded to ``SHARE_PRECISION``."""
        digits = constants.SHARE_PRECISION
        return {
            "harnesses": self.harnesses,
            "replications": self.replications,
            "generalizability": round(self.generalizability, digits),
            "dependability": round(self.dependability, digits),
        }
