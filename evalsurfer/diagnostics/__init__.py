"""Deterministic diagnostics over an evaluation report."""

from evalsurfer.diagnostics.evidence import Evidence
from evalsurfer.diagnostics.explainability import Explainer
from evalsurfer.diagnostics.failure_map import FailureMap
from evalsurfer.diagnostics.golden_set import GoldenSet
from evalsurfer.diagnostics.maturity import MaturityClassifier
from evalsurfer.diagnostics.personas import PersonaAggregator
from evalsurfer.diagnostics.profiles import IndustryProfiler
from evalsurfer.diagnostics.regression import RegressionDiffer
from evalsurfer.diagnostics.review_gate import ReviewGate
from evalsurfer.diagnostics.root_cause import RootCauseAnalyzer

# Imported last: bundle.py re-imports the diagnostic classes above from this
# package, so they must already be bound before it is loaded.
from evalsurfer.diagnostics.bundle import DiagnosticsBundle

__all__ = [
    "RegressionDiffer",
    "RootCauseAnalyzer",
    "MaturityClassifier",
    "IndustryProfiler",
    "Explainer",
    "Evidence",
    "ReviewGate",
    "PersonaAggregator",
    "FailureMap",
    "GoldenSet",
    "DiagnosticsBundle",
]
