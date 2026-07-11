"""Red-team issue types.

The executable safety probe issue types and their tuple.
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Red-team issue types (executable safety probes)
# --------------------------------------------------------------------------- #
ISSUE_PROMPT_INJECTION: Final = "prompt_injection_followed"
ISSUE_PII_LEAKED: Final = "pii_leaked"
ISSUE_HARMFUL_CONTENT: Final = "harmful_content"
ISSUE_TOOL_EXFILTRATION: Final = "tool_exfiltration"
ISSUE_DISCRIMINATORY: Final = "discriminatory_ranking"
REDTEAM_ISSUE_TYPES: Final = (
    ISSUE_PROMPT_INJECTION,
    ISSUE_PII_LEAKED,
    ISSUE_HARMFUL_CONTENT,
    ISSUE_TOOL_EXFILTRATION,
    ISSUE_DISCRIMINATORY,
)

__all__ = [
    "ISSUE_PROMPT_INJECTION",
    "ISSUE_PII_LEAKED",
    "ISSUE_HARMFUL_CONTENT",
    "ISSUE_TOOL_EXFILTRATION",
    "ISSUE_DISCRIMINATORY",
    "REDTEAM_ISSUE_TYPES",
]
