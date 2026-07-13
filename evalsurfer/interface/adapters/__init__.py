"""Ecosystem adapters: deterministic import from external eval and trace tools.

Each adapter is a small, stateless service that maps another tool's native
output into EvalSurfer's own shapes -- rubric criteria, a report, or request
traces -- with no model, network, or API calls. They let you reuse scores and
telemetry you already collected (RAGAS, promptfoo, OpenTelemetry, LangSmith,
Langfuse)
inside the EvalSurfer scoring and diagnostics layers.
"""

from evalsurfer.interface.adapters.langfuse import LangfuseAdapter
from evalsurfer.interface.adapters.langsmith import LangSmithAdapter
from evalsurfer.interface.adapters.otel import OtelAdapter
from evalsurfer.interface.adapters.promptfoo import PromptfooAdapter
from evalsurfer.interface.adapters.ragas import RagasAdapter

__all__ = [
    "RagasAdapter",
    "PromptfooAdapter",
    "OtelAdapter",
    "LangSmithAdapter",
    "LangfuseAdapter",
]
