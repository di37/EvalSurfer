"""Judge calibration -- the deterministic "eval of the eval" layer.

:class:`Calibrator` scores an agent-produced judge report against a
:class:`CalibrationCase` oracle. :class:`AgreementStats` adds chance-corrected
inter-rater agreement (Cohen's / Fleiss's kappa, Krippendorff's alpha), and
:class:`ReferenceCalibrator` validates judge scores against human/gold scores
(mean absolute error, rank correlation). All deterministic, no model calls.
"""

from evalsurfer.calibration.agreement import AgreementStats
from evalsurfer.calibration.calibrate import CalibrationCase, Calibrator
from evalsurfer.calibration.reference import ReferenceCalibrator

__all__ = [
    "Calibrator",
    "CalibrationCase",
    "AgreementStats",
    "ReferenceCalibrator",
]
