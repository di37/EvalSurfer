"""Rubric categories, report nesting keys, and quality sub-groups.

The three rubric categories (quality, operational, safety) nest under report
section keys ``metrics`` and ``assurance`` (``report.metrics.quality``,
``report.metrics.operational``, ``report.assurance.safety``). That nesting is
**report shape**, not CIMAA ownership: quality rubric scores are agent-judged
and Core-assembled; Metrics owns reference quality metrics and operational /
SLO auto-scoring; Assurance owns safety validation. ``LAYER_BY_CATEGORY`` /
``CATEGORIES_BY_LAYER`` map category ↔ report section key. Also holds the
quality sub-groups (framework subcategories).

Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Rubric categories
# --------------------------------------------------------------------------- #
CATEGORY_QUALITY: Final = "quality"
CATEGORY_OPERATIONAL: Final = "operational"
CATEGORY_SAFETY: Final = "safety"
CATEGORIES: Final = (CATEGORY_QUALITY, CATEGORY_OPERATIONAL, CATEGORY_SAFETY)

# --------------------------------------------------------------------------- #
# Report section keys (not CIMAA product-layer ownership)
# --------------------------------------------------------------------------- #
LAYER_METRICS: Final = "metrics"
LAYER_ASSURANCE: Final = "assurance"
LAYERS: Final = (LAYER_METRICS, LAYER_ASSURANCE)

# Which report section nests each category (see module docstring).
LAYER_BY_CATEGORY: Final = {
    CATEGORY_QUALITY: LAYER_METRICS,
    CATEGORY_OPERATIONAL: LAYER_METRICS,
    CATEGORY_SAFETY: LAYER_ASSURANCE,
}
# Categories under each report section key, in report order.
CATEGORIES_BY_LAYER: Final = {
    LAYER_METRICS: (CATEGORY_QUALITY, CATEGORY_OPERATIONAL),
    LAYER_ASSURANCE: (CATEGORY_SAFETY,),
}

# Quality sub-groups (framework subcategories). Operational/safety criteria have
# no sub-group (``None``). ``GROUP_GENERATION`` is the generation-quality slice
# of Application Quality (not the CIMAA Core layer).
GROUP_GENERATION: Final = "generation_quality"
GROUP_RAG: Final = "rag_specific"
GROUP_AGENT_TOOL_USE: Final = "agent_tool_use"
GROUP_MULTI_TURN: Final = "multi_turn_conversation"

__all__ = [
    "CATEGORY_QUALITY",
    "CATEGORY_OPERATIONAL",
    "CATEGORY_SAFETY",
    "CATEGORIES",
    "LAYER_METRICS",
    "LAYER_ASSURANCE",
    "LAYERS",
    "LAYER_BY_CATEGORY",
    "CATEGORIES_BY_LAYER",
    "GROUP_GENERATION",
    "GROUP_RAG",
    "GROUP_AGENT_TOOL_USE",
    "GROUP_MULTI_TURN",
]
