"""Deterministic diagnostics over an evaluation report."""

from evalsurfer.analysis.diagnostics.evidence import Evidence
from evalsurfer.analysis.diagnostics.explainability import Explainer
from evalsurfer.analysis.diagnostics.failure_map import FailureMap
from evalsurfer.analysis.diagnostics.golden_set import GoldenSet
from evalsurfer.analysis.diagnostics.maturity import MaturityClassifier
from evalsurfer.analysis.diagnostics.personas import PersonaAggregator
from evalsurfer.analysis.diagnostics.profiles import IndustryProfiler
from evalsurfer.analysis.diagnostics.regression import RegressionDiffer
from evalsurfer.analysis.diagnostics.review_gate import ReviewGate
from evalsurfer.analysis.diagnostics.root_cause import RootCauseAnalyzer

# Imported last: bundle.py re-imports the diagnostic classes above from this
# package, so they must already be bound before it is loaded.
from evalsurfer.analysis.diagnostics.bundle import DiagnosticsBundle

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
