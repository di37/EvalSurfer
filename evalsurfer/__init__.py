"""EvalSurfer -- a skill-first, deterministic AI-application evaluation toolkit.

CIMAA layout:

* :mod:`evalsurfer.constants` -- shared rubric catalog (all layers).
* :mod:`evalsurfer.core` -- planner, scoring, report assemble, Gate.
* :mod:`evalsurfer.interface` -- pipeline (full run), CLI, MCP, adapters.
* :mod:`evalsurfer.metrics` -- operational/SLO, reference quality, eval golden dataset.
* :mod:`evalsurfer.analysis` -- diagnostics (incl. ReviewGate), calibration.
* :mod:`evalsurfer.assurance` -- red-team, trajectory, guardrail policy.
"""

from __future__ import annotations

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner, Signals
from evalsurfer.core.scoring import ScoringModel

__all__ = ["constants", "ScoringModel", "EvaluationPlanner", "Signals"]
__version__ = constants.FRAMEWORK_VERSION
