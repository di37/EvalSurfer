"""Red-team value object and its module-local labels.

:class:`RedTeamCase` is the frozen dataclass for a single adversarial probe; the
``CASE_*`` / ``CATEGORY_*`` labels and :data:`REDTEAM_CATEGORIES` are this
feature's local vocabulary (probe ids and the coarse categories that drive
:meth:`~evalsurfer.assurance.safety.redteam.redteam.RedTeam.template` selection).
"""

from __future__ import annotations

from dataclasses import dataclass

import evalsurfer.constants as constants

__all__ = ["RedTeamCase"]


# --------------------------------------------------------------------------- #
# Module-local labels (local to this feature; not shared framework vocabulary).
# --------------------------------------------------------------------------- #
# Stable id for each probe, so callers and tests can reference a case by name.
CASE_OVERRIDE_INJECTION = "override_injection"
CASE_RETRIEVAL_INJECTION = "rag_injection"
CASE_TOOL_EXFILTRATION = "tool_log_exfiltration"
CASE_HARMFUL_WEAPONS = "weapon_jailbreak"
CASE_PII_BAIT = "pii_readback"
CASE_DISCRIMINATORY = "candidate_ranking_bias"

# Coarse category each probe belongs to; drives template() selection.
CATEGORY_INSTRUCTION_OVERRIDE = "instruction_override"
CATEGORY_RETRIEVAL_INJECTION = "retrieval_injection"
CATEGORY_TOOL_EXFILTRATION = "tool_exfiltration"
CATEGORY_JAILBREAK_WEAPONS = "jailbreak_weapons"
CATEGORY_PII_DISCLOSURE = "pii_disclosure"
CATEGORY_DISCRIMINATORY = "discriminatory_ranking"
REDTEAM_CATEGORIES = (
    CATEGORY_INSTRUCTION_OVERRIDE,
    CATEGORY_RETRIEVAL_INJECTION,
    CATEGORY_TOOL_EXFILTRATION,
    CATEGORY_JAILBREAK_WEAPONS,
    CATEGORY_PII_DISCLOSURE,
    CATEGORY_DISCRIMINATORY,
)

# Categories present in every template regardless of target shape.
_BASE_CATEGORIES = frozenset(
    {CATEGORY_INSTRUCTION_OVERRIDE, CATEGORY_JAILBREAK_WEAPONS, CATEGORY_DISCRIMINATORY}
)


@dataclass(frozen=True)
class RedTeamCase:
    """A single adversarial probe and the behaviour a safe target should show.

    Attributes:
        id: Stable unique identifier for the probe (see the ``CASE_*``
            constants).
        prompt: The adversarial input to send to the target application.
        expected_behavior: What a safe response looks like (a refusal, ignoring
            an injected instruction, and so on).
        issue_type: The red-team issue class, one of
            ``constants.REDTEAM_ISSUE_TYPES``.
        category: The coarse probe family used to select probes in
            :meth:`RedTeam.template`, one of ``REDTEAM_CATEGORIES``.
    """

    id: str
    prompt: str
    expected_behavior: str
    issue_type: str
    category: str

    def __post_init__(self) -> None:
        """Validate the probe on construction so the battery stays trustworthy.

        Raises:
            TypeError: If any field is not a string.
            ValueError: If a text field is blank, ``issue_type`` is not one of
                ``constants.REDTEAM_ISSUE_TYPES``, or ``category`` is not one of
                ``REDTEAM_CATEGORIES``.
        """
        for field_name in ("id", "prompt", "expected_behavior", "issue_type", "category"):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise TypeError(f"{field_name} must be a string")
            if not value.strip():
                raise ValueError(f"{field_name} must not be blank")
        if self.issue_type not in constants.REDTEAM_ISSUE_TYPES:
            raise ValueError(
                f"issue_type must be one of {constants.REDTEAM_ISSUE_TYPES}"
            )
        if self.category not in REDTEAM_CATEGORIES:
            raise ValueError(f"category must be one of {REDTEAM_CATEGORIES}")
