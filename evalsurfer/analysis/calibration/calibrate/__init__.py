"""Judge calibration for EvalSurfer -- the deterministic "eval of the eval".

An EvalSurfer report is produced by the agent/skill acting as an LLM judge. This
module never runs that judge; instead it *scores the judge*. A
:class:`CalibrationCase` freezes what a trustworthy judge should conclude about
one target: which categories the planner makes applicable, the score band each
criterion should land in, the pass/fix/fail decision, the severity of the worst
reported issue, and whether a critical safety issue should be escalated.
:class:`Calibrator` then compares one judge-produced report against that oracle
(:meth:`~Calibrator.check_report`) and aggregates agreement, false-pass /
false-fail rates, and score variance across many repeated judge runs
(:meth:`~Calibrator.summarize`).

The judge reports are external input produced by the agent/skill: this layer
reads the scores, decision, and top issues already written into them and never
recomputes the judge's opinion. Everything here is deterministic, standard
library only, and makes no model calls; inputs are never mutated. Applicability
comes from :class:`planner.EvaluationPlanner`, and every threshold, severity,
decision, and metric name is imported from :mod:`constants`.

The implementation is split across two focused modules -- :mod:`.models` (the
:class:`CalibrationCase` oracle and its validation) and :mod:`.calibrator` (the
:class:`Calibrator` service) -- and re-exported here so that
``from evalsurfer.analysis.calibration.calibrate import Calibrator`` keeps
working.
"""

from evalsurfer.analysis.calibration.calibrate.calibrator import Calibrator
from evalsurfer.analysis.calibration.calibrate.models import CalibrationCase

__all__ = [
    "CalibrationCase",
    "Calibrator",
]
