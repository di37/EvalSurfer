"""Release guardrail policy.

Machine-readable rule names Assurance ``guardrail_gate`` / ``Guardrails`` enforce
on a report; the field names are the keys of a guardrails.json policy file.
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Release guardrail policy: rules Assurance Guardrails enforces on a report.
# Field names are the keys of a guardrails.json policy file.
# --------------------------------------------------------------------------- #
GUARDRAIL_MIN_DECISION: Final = "min_decision"
GUARDRAIL_MIN_SAFETY: Final = "min_safety"
GUARDRAIL_COVERAGE_FLOOR: Final = "coverage_floor"
GUARDRAIL_BLOCK_ON_CRITICAL_ISSUE: Final = "block_on_critical_issue"
GUARDRAIL_SENSITIVE_PATHS: Final = "sensitive_paths"
GUARDRAIL_MAX_FIX_ATTEMPTS: Final = "max_fix_attempts"
GUARDRAIL_FIELDS: Final = (
    GUARDRAIL_MIN_DECISION,
    GUARDRAIL_MIN_SAFETY,
    GUARDRAIL_COVERAGE_FLOOR,
    GUARDRAIL_BLOCK_ON_CRITICAL_ISSUE,
    GUARDRAIL_SENSITIVE_PATHS,
    GUARDRAIL_MAX_FIX_ATTEMPTS,
)

__all__ = [
    "GUARDRAIL_MIN_DECISION",
    "GUARDRAIL_MIN_SAFETY",
    "GUARDRAIL_COVERAGE_FLOOR",
    "GUARDRAIL_BLOCK_ON_CRITICAL_ISSUE",
    "GUARDRAIL_SENSITIVE_PATHS",
    "GUARDRAIL_MAX_FIX_ATTEMPTS",
    "GUARDRAIL_FIELDS",
]
