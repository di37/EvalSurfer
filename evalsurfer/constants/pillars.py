"""Pillars and quality sub-groups.

The three top-level pillars and the quality sub-groups (framework subcategories).
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Pillars
# --------------------------------------------------------------------------- #
PILLAR_QUALITY: Final = "quality"
PILLAR_SAFETY: Final = "safety"
PILLAR_OPERATIONAL: Final = "operational"
PILLARS: Final = (PILLAR_QUALITY, PILLAR_SAFETY, PILLAR_OPERATIONAL)

# Quality sub-groups (framework subcategories). Safety/operational criteria have
# no sub-group (``None``).
GROUP_CORE_GENERATION: Final = "core_generation_quality"
GROUP_RAG: Final = "rag_specific"
GROUP_AGENT_TOOL_USE: Final = "agent_tool_use"
GROUP_MULTI_TURN: Final = "multi_turn_conversation"

__all__ = [
    "PILLAR_QUALITY",
    "PILLAR_SAFETY",
    "PILLAR_OPERATIONAL",
    "PILLARS",
    "GROUP_CORE_GENERATION",
    "GROUP_RAG",
    "GROUP_AGENT_TOOL_USE",
    "GROUP_MULTI_TURN",
]
