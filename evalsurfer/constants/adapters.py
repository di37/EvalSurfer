"""Ecosystem adapters.

Adapter names for importing from external eval/trace tools, plus the RAGAS metric
name -> EvalSurfer criterion id mapping.
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Ecosystem adapters (import from external eval/trace tools)
# --------------------------------------------------------------------------- #
ADAPTER_PROMPTFOO: Final = "promptfoo"
ADAPTER_RAGAS: Final = "ragas"
ADAPTER_LANGSMITH: Final = "langsmith"
ADAPTER_OTEL: Final = "otel"
# RAGAS metric name -> EvalSurfer criterion id.
RAGAS_CRITERION_MAP: Final = {
    "faithfulness": "groundedness_faithfulness",
    "answer_relevancy": "relevance",
    "context_precision": "context_relevance",
    "context_recall": "retrieval_recall",
}

__all__ = [
    "ADAPTER_PROMPTFOO",
    "ADAPTER_RAGAS",
    "ADAPTER_LANGSMITH",
    "ADAPTER_OTEL",
    "RAGAS_CRITERION_MAP",
]
