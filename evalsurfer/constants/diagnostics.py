"""Diagnostics: regression labels, maturity ladder, profiles, personas, pipeline.

Regression diff change labels, the maturity ladder, industry weighting profiles,
persona lenses, the pipeline failure map, and the diagnostics block keys. Builds
on the pillar/group names (``pillars``) for the profiles and stage selectors.
Data only -- no behavior, no imports beyond typing helpers and sibling constants.
"""

from __future__ import annotations

from typing import Final

from evalsurfer.constants.pillars import (
    GROUP_AGENT_TOOL_USE,
    GROUP_CORE_GENERATION,
    GROUP_MULTI_TURN,
    GROUP_RAG,
    PILLAR_OPERATIONAL,
    PILLAR_QUALITY,
    PILLAR_SAFETY,
)

# --------------------------------------------------------------------------- #
# Regression diff change labels
# --------------------------------------------------------------------------- #
CHANGE_IMPROVED: Final = "improved"
CHANGE_REGRESSED: Final = "regressed"
CHANGE_UNCHANGED: Final = "unchanged"
CHANGE_ADDED: Final = "added"
CHANGE_REMOVED: Final = "removed"
CHANGES: Final = (CHANGE_IMPROVED, CHANGE_REGRESSED, CHANGE_UNCHANGED, CHANGE_ADDED, CHANGE_REMOVED)

# --------------------------------------------------------------------------- #
# Maturity ladder (levels 1-6): name + why-reached driver + next-step advice
# --------------------------------------------------------------------------- #
MIN_MATURITY_LEVEL: Final = 1
MAX_MATURITY_LEVEL: Final = 6
MATURITY_LEVEL_NAMES: Final = {
    1: "Prompt App",
    2: "Prompt + RAG",
    3: "Agent",
    4: "Multi-Agent",
    5: "Production AI System",
    6: "Self-Improving",
}
MATURITY_LEVEL_DRIVERS: Final = {
    1: "no retrieval, tool, or agent signals are present",
    2: "retrieved context indicates a retrieval-augmented (RAG) pattern",
    3: "tool calls indicate autonomous, agentic behavior",
    4: "multiple coordinated agents are in use",
    5: "operational traces on an agentic system indicate a production deployment",
    6: "a self-improvement loop is in place",
}
MATURITY_LEVEL_RECOMMENDATIONS: Final = {
    1: "Add retrieval (RAG) so answers are grounded in a knowledge source to reach level 2 (Prompt + RAG).",
    2: "Add tool calls so the system can take actions to reach level 3 (Agent).",
    3: "Add multi-agent coordination to reach level 4 (Multi-Agent).",
    4: "Add operational traces (latency, cost, and failure telemetry) to reach level 5 (Production AI System).",
    5: "Add a self-improvement loop that feeds evaluations back into the system to reach level 6 (Self-Improving).",
    6: "",
}

# --------------------------------------------------------------------------- #
# Industry weighting profiles (pillar weights that sum to 1.0)
# --------------------------------------------------------------------------- #
PROFILE_DEFAULT: Final = "default"
INDUSTRY_PROFILES: Final = {
    PROFILE_DEFAULT: {PILLAR_QUALITY: 1 / 3, PILLAR_SAFETY: 1 / 3, PILLAR_OPERATIONAL: 1 / 3},
    "healthcare": {PILLAR_QUALITY: 0.40, PILLAR_SAFETY: 0.50, PILLAR_OPERATIONAL: 0.10},
    "finance": {PILLAR_QUALITY: 0.40, PILLAR_SAFETY: 0.40, PILLAR_OPERATIONAL: 0.20},
    "gaming": {PILLAR_QUALITY: 0.35, PILLAR_SAFETY: 0.15, PILLAR_OPERATIONAL: 0.50},
    "customer_support": {PILLAR_QUALITY: 0.50, PILLAR_SAFETY: 0.20, PILLAR_OPERATIONAL: 0.30},
    "legal": {PILLAR_QUALITY: 0.45, PILLAR_SAFETY: 0.45, PILLAR_OPERATIONAL: 0.10},
    "education": {PILLAR_QUALITY: 0.60, PILLAR_SAFETY: 0.25, PILLAR_OPERATIONAL: 0.15},
}

# --------------------------------------------------------------------------- #
# Persona lenses (persona evaluation)
# --------------------------------------------------------------------------- #
DEFAULT_PERSONAS: Final = ("engineer", "lawyer", "doctor", "beginner", "ceo")

# --------------------------------------------------------------------------- #
# Pipeline failure map: stages, statuses, and which (pillar, group) selectors
# feed each stage. Prompt/Response are structural (no mapped criteria).
# --------------------------------------------------------------------------- #
STAGE_PROMPT: Final = "Prompt"
STAGE_RETRIEVER: Final = "Retriever"
STAGE_RANKER: Final = "Ranker"
STAGE_GENERATOR: Final = "Generator"
STAGE_TOOL: Final = "Tool"
STAGE_RESPONSE: Final = "Response"
PIPELINE_STAGES: Final = (
    STAGE_PROMPT,
    STAGE_RETRIEVER,
    STAGE_RANKER,
    STAGE_GENERATOR,
    STAGE_TOOL,
    STAGE_RESPONSE,
)
STAGE_STATUS_OK: Final = "ok"
STAGE_STATUS_FAIL: Final = "fail"
STAGE_STATUS_NA: Final = "na"
FAILURE_MAP_THRESHOLD: Final = 3  # criterion score below this marks a stage weak

# (pillar, group) selectors mapped to each stage.
STAGE_SELECTORS: Final = {
    STAGE_RETRIEVER: ((PILLAR_QUALITY, GROUP_RAG),),
    STAGE_RANKER: ((PILLAR_QUALITY, GROUP_RAG),),
    STAGE_GENERATOR: (
        (PILLAR_QUALITY, GROUP_CORE_GENERATION),
        (PILLAR_QUALITY, GROUP_MULTI_TURN),
        (PILLAR_SAFETY, None),
    ),
    STAGE_TOOL: ((PILLAR_QUALITY, GROUP_AGENT_TOOL_USE),),
}

# Diagnostics block keys carried in a report's optional "diagnostics" section.
DIAGNOSTICS_KEYS: Final = (
    "explainability",
    "root_cause",
    "failure_map",
    "review_gate",
    "maturity",
    "regression",
)

__all__ = [
    "CHANGE_IMPROVED",
    "CHANGE_REGRESSED",
    "CHANGE_UNCHANGED",
    "CHANGE_ADDED",
    "CHANGE_REMOVED",
    "CHANGES",
    "MIN_MATURITY_LEVEL",
    "MAX_MATURITY_LEVEL",
    "MATURITY_LEVEL_NAMES",
    "MATURITY_LEVEL_DRIVERS",
    "MATURITY_LEVEL_RECOMMENDATIONS",
    "PROFILE_DEFAULT",
    "INDUSTRY_PROFILES",
    "DEFAULT_PERSONAS",
    "STAGE_PROMPT",
    "STAGE_RETRIEVER",
    "STAGE_RANKER",
    "STAGE_GENERATOR",
    "STAGE_TOOL",
    "STAGE_RESPONSE",
    "PIPELINE_STAGES",
    "STAGE_STATUS_OK",
    "STAGE_STATUS_FAIL",
    "STAGE_STATUS_NA",
    "FAILURE_MAP_THRESHOLD",
    "STAGE_SELECTORS",
    "DIAGNOSTICS_KEYS",
]
