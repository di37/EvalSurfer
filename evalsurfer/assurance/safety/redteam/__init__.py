"""Executable red-team probes for EvalSurfer safety evaluation.

The safety category is normally judged by the skill (the agent). This module adds a
small, reusable battery of adversarial probes -- instruction-override and
retrieval-injection prompt attacks, tool-based data exfiltration, a
jailbreak/weapons request, PII bait, and discriminatory ranking -- so a target
application can be poked with realistic malicious inputs and its responses
triaged.

:class:`RedTeam` exposes two stateless helpers:

* :meth:`RedTeam.template` selects the probes that fit a target's shape (plain
  prompt app, RAG, or agent) and returns them as plain probe dicts to send.
* :meth:`RedTeam.check` triages the collected outputs. **Only the PII issue type
  has a reliable deterministic detector** (regex for emails, phone numbers, and
  SSNs); ``triggered`` reflects whether any pattern matched. Every other issue
  type -- prompt injection, harmful content, tool exfiltration, discriminatory
  ranking -- cannot be judged by pattern matching without fabricating a signal,
  so those are surfaced with ``needs_judgment=True`` for the skill to assess. No
  fake detection is ever performed.

Everything here is deterministic and standard-library-only: no model or network
calls, and inputs are never mutated. Issue-type names come from :mod:`constants`;
the ``CASE_*`` and ``CATEGORY_*`` labels are truly local to this feature.

The implementation is split across focused modules -- :mod:`.models` (the
:class:`RedTeamCase` value object plus the ``CASE_*`` / ``CATEGORY_*`` labels),
:mod:`.helpers` (the PII detection and triage helpers), and :mod:`.redteam` (the
:class:`RedTeam` battery) -- and re-exported here so that
``from evalsurfer.assurance.safety.redteam import RedTeam`` keeps working.
"""

from evalsurfer.assurance.safety.redteam.models import (
    CASE_DISCRIMINATORY,
    CASE_HARMFUL_WEAPONS,
    CASE_OVERRIDE_INJECTION,
    CASE_PII_BAIT,
    CASE_RETRIEVAL_INJECTION,
    CASE_TOOL_EXFILTRATION,
    CATEGORY_DISCRIMINATORY,
    CATEGORY_INSTRUCTION_OVERRIDE,
    CATEGORY_JAILBREAK_WEAPONS,
    CATEGORY_PII_DISCLOSURE,
    CATEGORY_RETRIEVAL_INJECTION,
    CATEGORY_TOOL_EXFILTRATION,
    REDTEAM_CATEGORIES,
    RedTeamCase,
)
from evalsurfer.assurance.safety.redteam.redteam import RedTeam

__all__ = ["RedTeamCase", "RedTeam"]
