"""Ecosystem adapters: deterministic import from external eval and trace tools.

Each adapter is a small, stateless service that maps another tool's native
output into EvalSurfer's own shapes -- rubric criteria, a report, or request
traces -- with no model, network, or API calls. They let you reuse scores and
telemetry you already collected (RAGAS, promptfoo, OpenTelemetry, LangSmith)
inside the EvalSurfer scoring and diagnostics layers.
"""

from evalsurfer.adapters.langsmith import LangSmithAdapter
from evalsurfer.adapters.otel import OtelAdapter
from evalsurfer.adapters.promptfoo import PromptfooAdapter
from evalsurfer.adapters.ragas import RagasAdapter

__all__ = [
    "RagasAdapter",
    "PromptfooAdapter",
    "OtelAdapter",
    "LangSmithAdapter",
]
