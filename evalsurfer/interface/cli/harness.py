"""CLI adapter for the harness-invariance analysis (``evalsurfer harness-invariance``).

Reachable through the unified ``evalsurfer`` dispatcher only (no dedicated
console script -- a study analysis is an occasional command, not a pipeline
stage). The payload is the same ``{"judgments": [...]}`` shape the
``harness_invariance`` MCP tool accepts; see
:class:`evalsurfer.analysis.calibration.harness.HarnessInvariance`.
"""

from __future__ import annotations

from typing import Any, Mapping

from evalsurfer.analysis.calibration.harness import HarnessInvariance


def build_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Run the harness-invariance analysis on a loaded JSON payload.

    Args:
        payload: ``{"judgments": [...]}`` plus optional ``dependability_target``
            and ``dstudy_max_harnesses`` / ``dstudy_max_replications``.

    Returns:
        The full analysis dict (components, shares, coefficients, D-study,
        decisions, per-criterion profiles, diagnostics).

    Raises:
        TypeError: If the payload or a judgment is not a mapping.
        ValueError: On invalid options, judgments, or grid shape.
    """
    return HarnessInvariance.analyze(payload)
