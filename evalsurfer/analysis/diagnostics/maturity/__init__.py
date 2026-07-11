"""AI application maturity model for EvalSurfer.

Classify an evaluation target onto a six-level maturity ladder, from a bare
prompt app up to a self-improving system, using the same :class:`Signals` the
planner already infers. The level is the highest stage the evidence supports:

* 1 Prompt App           -- a prompt/LLM with no retrieval, tools, or agency
* 2 Prompt + RAG         -- retrieved context grounds the answer
* 3 Agent                -- the system calls tools to take actions
* 4 Multi-Agent          -- multiple coordinated agents
* 5 Production AI System -- an agentic system with operational telemetry
* 6 Self-Improving       -- a feedback loop improves the system over time

The ladder's names, drivers, and next-step advice all come from
:mod:`constants`; this module owns only the gating logic. :class:`MaturityClassifier`
is a deterministic diagnostic layer: it runs with no model calls and no
third-party dependencies, and it never mutates its inputs.

The implementation is split across two focused modules -- :mod:`.models` (the
:class:`MaturityLevel` value object) and :mod:`.classifier` (the
:class:`MaturityClassifier` service and its gating logic) -- and re-exported here
so that ``from evalsurfer.analysis.diagnostics.maturity import
MaturityClassifier`` keeps working.
"""

from evalsurfer.analysis.diagnostics.maturity.classifier import MaturityClassifier
from evalsurfer.analysis.diagnostics.maturity.models import MaturityLevel

__all__ = ["MaturityLevel", "MaturityClassifier"]
