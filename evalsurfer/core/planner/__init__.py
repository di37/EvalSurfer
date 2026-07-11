"""Adaptive evaluation planner for EvalSurfer.

Rather than asking the user which criteria to run, :class:`EvaluationPlanner`
infers them from the evidence that is present: given a :class:`Signals` snapshot
(is there an answer? retrieved context? tool calls? a multi-turn history?
operational traces?), it returns exactly the categories and criteria that can be
judged, each with a reason, plus a coverage score.

This is the deterministic "methodology" layer -- which signal gates which
category. It runs with no model calls and no third-party dependencies, and the
rubric catalog it plans over comes from :data:`constants.CRITERIA_CATALOG`.

The implementation is split across three focused modules -- :mod:`.signals`
(the evidence snapshot), :mod:`.models` (the plan value objects), and
:mod:`.engine` (the planner itself) -- and re-exported here so that
``from evalsurfer.core.planner import EvaluationPlanner`` keeps working.
"""

from evalsurfer.core.planner.engine import EvaluationPlanner
from evalsurfer.core.planner.models import (
    Criterion,
    EvaluationPlan,
    PlannedCategory,
    PlannedCriterion,
)
from evalsurfer.core.planner.signals import Signals

__all__ = [
    "Signals",
    "Criterion",
    "PlannedCriterion",
    "PlannedCategory",
    "EvaluationPlan",
    "EvaluationPlanner",
]
