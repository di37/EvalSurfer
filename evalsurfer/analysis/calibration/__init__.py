"""Judge calibration -- the deterministic "eval of the eval" layer.

:class:`Calibrator` scores an agent-produced judge report against a
:class:`CalibrationCase` oracle. :class:`AgreementStats` adds chance-corrected
inter-rater agreement (Cohen's / Fleiss's kappa, Krippendorff's alpha),
:class:`ReferenceCalibrator` validates judge scores against human/gold scores
(mean absolute error, rank correlation), and :class:`HarnessInvariance`
decomposes cross-harness judgment variance (is the verdict a property of the
target or of the judging harness?). All deterministic, no model calls.
"""

from evalsurfer.analysis.calibration.agreement import AgreementStats
from evalsurfer.analysis.calibration.calibrate import CalibrationCase, Calibrator
from evalsurfer.analysis.calibration.harness import HarnessInvariance
from evalsurfer.analysis.calibration.reference import ReferenceCalibrator

__all__ = [
    "Calibrator",
    "CalibrationCase",
    "AgreementStats",
    "ReferenceCalibrator",
    "HarnessInvariance",
]
