"""Decision-vs-minimum release gating.

:class:`Gate` turns a report's decision into a pass/fail release signal by
ranking it against a required minimum decision using
:data:`constants.DECISION_RANK`. Deterministic and standard-library-only: it
makes no model calls and never mutates the report.
"""

from __future__ import annotations

from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.report.models import GateResult

__all__ = ["Gate"]


class Gate:
    """Rank a report's decision against a required minimum to gate releases.

    Stateless: the minimum bar is supplied per call, so the class is a cohesive
    namespace of static methods rather than something to instantiate.
    Deterministic and standard-library-only -- it makes no model calls and never
    mutates the report.
    """

    @staticmethod
    def evaluate(report: Mapping[str, Any], minimum: str) -> dict[str, Any]:
        """Decide whether a report's decision clears the ``minimum`` bar.

        The report passes when the rank of its decision is at least the rank of
        ``minimum`` under ``constants.DECISION_RANK`` (``fail`` <
        ``pass_with_fixes`` < ``pass``).

        Args:
            report: The report whose top-level ``decision`` is gated.
            minimum: The lowest decision that still passes; must be one of
                ``constants.DECISIONS``.

        Returns:
            ``{"passed": bool, "decision": str, "minimum": str, "reason": str}``.

        Raises:
            ValueError: If ``minimum`` is not a known decision, or the report's
                decision is missing or unknown.
        """
        if minimum not in constants.DECISIONS:
            raise ValueError(
                f"minimum must be one of {list(constants.DECISIONS)}, got {minimum!r}"
            )
        decision = report.get("decision") if isinstance(report, Mapping) else None
        if decision not in constants.DECISIONS:
            raise ValueError(f"unknown report decision: {decision!r}")

        passed = constants.DECISION_RANK[decision] >= constants.DECISION_RANK[minimum]
        return GateResult(
            passed=passed,
            decision=decision,
            minimum=minimum,
            reason=Gate._reason(passed, decision, minimum),
        ).to_dict()

    @staticmethod
    def _reason(passed: bool, decision: str, minimum: str) -> str:
        """Explain the gate outcome in one human-readable sentence.

        Args:
            passed: Whether the report cleared the minimum bar.
            decision: The report's decision.
            minimum: The minimum decision required.

        Returns:
            A sentence describing why the report passed or failed the gate.
        """
        relation = "meets or exceeds" if passed else "is below"
        return f"Decision {decision!r} {relation} the minimum bar of {minimum!r}."
