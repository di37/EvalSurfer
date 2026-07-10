"""Executable red-team safety probes for EvalSurfer.

The single reliable deterministic check here is PII detection; every other
adversarial issue type is surfaced for skill-driven judgment.
"""

from evalsurfer.assurance.safety.redteam import RedTeam, RedTeamCase

__all__ = ["RedTeam", "RedTeamCase"]
