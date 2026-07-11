"""Result value objects for report validation and gating.

Frozen dataclasses only: :class:`ValidationResult` (the outcome of structurally
validating a report) and :class:`GateResult` (whether a report cleared a minimum
decision). The services that produce them live in
:mod:`evalsurfer.core.report.validator` and :mod:`evalsurfer.core.report.gate`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["ValidationResult", "GateResult"]


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of structurally validating one report."""

    valid: bool
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Render the result as a JSON-ready dict.

        Returns:
            ``{"valid": bool, "errors": [str, ...]}``.
        """
        return {"valid": self.valid, "errors": list(self.errors)}


@dataclass(frozen=True)
class GateResult:
    """Whether a report's decision clears a required minimum decision."""

    passed: bool
    decision: str
    minimum: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Render the gate result as a JSON-ready dict.

        Returns:
            ``{"passed": bool, "decision": str, "minimum": str,
            "reason": str}``.
        """
        return {
            "passed": self.passed,
            "decision": self.decision,
            "minimum": self.minimum,
            "reason": self.reason,
        }
