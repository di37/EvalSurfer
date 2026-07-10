"""EvalSurfer -- a skill-first, deterministic AI-application evaluation toolkit.

Layout:

* :mod:`evalsurfer.constants` -- every fixed value, in one place.
* :mod:`evalsurfer.core` -- the scoring model and adaptive planner.
* :mod:`evalsurfer.metrics.operational` -- operational metrics from request traces.
* :mod:`evalsurfer.analysis.diagnostics` -- deterministic diagnostics over a report.
* :mod:`evalsurfer.interface.cli` -- command-line entry points.
"""

from __future__ import annotations

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner, Signals
from evalsurfer.core.scoring import ScoringModel

__all__ = ["constants", "ScoringModel", "EvaluationPlanner", "Signals"]
__version__ = constants.FRAMEWORK_VERSION
