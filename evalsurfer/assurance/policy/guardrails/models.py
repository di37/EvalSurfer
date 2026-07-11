"""The guardrail policy value object.

:class:`GuardrailPolicy` is the frozen dataclass that encodes a team's release
rules, loaded and validated from a ``guardrails.json`` mapping via
:meth:`GuardrailPolicy.from_mapping`. The private ``_optional_number`` helper
serves that validation. The enforcement logic lives in
:mod:`evalsurfer.assurance.policy.guardrails.guardrails`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import evalsurfer.constants as constants

__all__ = ["GuardrailPolicy"]


def _optional_number(
    value: Any, name: str, low: float, high: float
) -> float | None:
    """Validate an optional numeric policy field within an inclusive range.

    Args:
        value: The raw value, or ``None`` when the field is absent.
        name: The field name, for error messages.
        low: The inclusive lower bound.
        high: The inclusive upper bound.

    Returns:
        The value as a ``float``, or ``None`` when absent.

    Raises:
        TypeError: If ``value`` is present but not a (non-bool) number.
        ValueError: If ``value`` falls outside ``[low, high]``.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number or null")
    if not low <= value <= high:
        raise ValueError(f"{name} must be within {low}-{high}")
    return float(value)


@dataclass(frozen=True)
class GuardrailPolicy:
    """A release policy Assurance ``Guardrails`` / ``guardrail_gate`` enforces on a report.

    Every field is optional; an omitted rule is simply not enforced. Loaded from
    a ``guardrails.json`` mapping via :meth:`from_mapping`, which validates on
    construction so a malformed policy fails fast.
    """

    min_decision: str = constants.DECISION_PASS_WITH_FIXES
    min_safety: float | None = None
    coverage_floor: float | None = None
    block_on_critical_issue: bool = False
    sensitive_paths: tuple[str, ...] = ()
    max_fix_attempts: int | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "GuardrailPolicy":
        """Build and validate a policy from a ``guardrails.json`` mapping.

        Args:
            data: The parsed policy object; recognised keys are
                :data:`constants.GUARDRAIL_FIELDS`.

        Returns:
            The validated :class:`GuardrailPolicy`.

        Raises:
            TypeError: If ``data`` or a field has the wrong type.
            ValueError: If an unknown key is present or a field is out of range.
        """
        if not isinstance(data, Mapping):
            raise TypeError("guardrail policy must be an object")
        unknown = set(data) - set(constants.GUARDRAIL_FIELDS)
        if unknown:
            raise ValueError(
                f"unknown guardrail field(s): {', '.join(sorted(unknown))}"
            )

        min_decision = data.get(
            constants.GUARDRAIL_MIN_DECISION, constants.DECISION_PASS_WITH_FIXES
        )
        if min_decision not in constants.DECISIONS:
            raise ValueError(
                f"{constants.GUARDRAIL_MIN_DECISION} must be one of {constants.DECISIONS}"
            )

        block = data.get(constants.GUARDRAIL_BLOCK_ON_CRITICAL_ISSUE, False)
        if not isinstance(block, bool):
            raise TypeError(
                f"{constants.GUARDRAIL_BLOCK_ON_CRITICAL_ISSUE} must be a boolean"
            )

        raw_paths = data.get(constants.GUARDRAIL_SENSITIVE_PATHS, ())
        if not isinstance(raw_paths, (list, tuple)) or not all(
            isinstance(pattern, str) for pattern in raw_paths
        ):
            raise TypeError(
                f"{constants.GUARDRAIL_SENSITIVE_PATHS} must be a list of strings"
            )

        attempts = data.get(constants.GUARDRAIL_MAX_FIX_ATTEMPTS)
        if attempts is not None and (
            isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1
        ):
            raise ValueError(
                f"{constants.GUARDRAIL_MAX_FIX_ATTEMPTS} must be a positive integer or null"
            )

        return cls(
            min_decision=min_decision,
            min_safety=_optional_number(
                data.get(constants.GUARDRAIL_MIN_SAFETY),
                constants.GUARDRAIL_MIN_SAFETY,
                0.0,
                constants.PERFECT_SCORE,
            ),
            coverage_floor=_optional_number(
                data.get(constants.GUARDRAIL_COVERAGE_FLOOR),
                constants.GUARDRAIL_COVERAGE_FLOOR,
                0.0,
                1.0,
            ),
            block_on_critical_issue=block,
            sensitive_paths=tuple(raw_paths),
            max_fix_attempts=attempts,
        )
