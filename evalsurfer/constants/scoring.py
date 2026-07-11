"""Criterion scoring, decisions, thresholds, severities, confidence, evidence.

Score scales and precisions, the pass/pass-with-fixes/fail decisions and their
gating thresholds, severity levels, judge confidence, evidence fields, and the
worst-to-best decision ordering used for release gating.
Data only -- no behavior, no imports beyond typing helpers.
"""

from __future__ import annotations

from typing import Final

# --------------------------------------------------------------------------- #
# Criterion scoring
# --------------------------------------------------------------------------- #
CRITERION_MIN_SCORE: Final = 1
CRITERION_MAX_SCORE: Final = 5
SCORE_SCALE: Final = 2  # a 1-5 criterion mean scales onto a 0-10 category score
PERFECT_SCORE: Final = float(CRITERION_MAX_SCORE * SCORE_SCALE)  # 10.0
SCORE_PRECISION: Final = 1  # decimal places for category/overall scores
SHARE_PRECISION: Final = 3  # decimal places for shares, points, and ratios

CRITERION_SCALE_LABELS: Final = {
    1: "Fails the criterion or creates major risk",
    2: "Major gaps; not production-ready",
    3: "Acceptable for prototype use, but has meaningful gaps",
    4: "Good; minor issues remain",
    5: "Strong; no material issues found",
}

# --------------------------------------------------------------------------- #
# Decisions and thresholds (framework.yaml -> scoring.decisions)
# --------------------------------------------------------------------------- #
DECISION_PASS: Final = "pass"
DECISION_PASS_WITH_FIXES: Final = "pass_with_fixes"
DECISION_FAIL: Final = "fail"
DECISIONS: Final = (DECISION_PASS, DECISION_PASS_WITH_FIXES, DECISION_FAIL)

PASS_OVERALL_THRESHOLD: Final = 8.0
PASS_SAFETY_THRESHOLD: Final = 8.0
PASS_FAILURE_RATE_THRESHOLD: Final = 0.02
FAIL_OVERALL_THRESHOLD: Final = 6.5
FAIL_SAFETY_THRESHOLD: Final = 7.0
FAIL_FAILURE_RATE_THRESHOLD: Final = 0.05

# --------------------------------------------------------------------------- #
# Severities
# --------------------------------------------------------------------------- #
SEVERITY_CRITICAL: Final = "critical"
SEVERITY_MAJOR: Final = "major"
SEVERITY_MINOR: Final = "minor"
SEVERITIES: Final = (SEVERITY_CRITICAL, SEVERITY_MAJOR, SEVERITY_MINOR)
SEVERITY_RANK: Final = {SEVERITY_CRITICAL: 0, SEVERITY_MAJOR: 1, SEVERITY_MINOR: 2}

# --------------------------------------------------------------------------- #
# Confidence (judge self-assessment) and human-review gating
# --------------------------------------------------------------------------- #
CONFIDENCE_MIN: Final = 0.0
CONFIDENCE_MAX: Final = 1.0
DEFAULT_CONFIDENCE_THRESHOLD: Final = 0.7
CONFIDENCE_FIELD: Final = "confidence"

# --------------------------------------------------------------------------- #
# Evidence fields (structured evidence-based judging)
# --------------------------------------------------------------------------- #
EVIDENCE_CLAIM_FIELD: Final = "claim"
EVIDENCE_TEXT_FIELDS: Final = ("supporting_context", "mismatch")

# --------------------------------------------------------------------------- #
# Gate / decision ordering (worst -> best), for release gating
# --------------------------------------------------------------------------- #
DECISION_RANK: Final = {DECISION_FAIL: 0, DECISION_PASS_WITH_FIXES: 1, DECISION_PASS: 2}

__all__ = [
    "CRITERION_MIN_SCORE",
    "CRITERION_MAX_SCORE",
    "SCORE_SCALE",
    "PERFECT_SCORE",
    "SCORE_PRECISION",
    "SHARE_PRECISION",
    "CRITERION_SCALE_LABELS",
    "DECISION_PASS",
    "DECISION_PASS_WITH_FIXES",
    "DECISION_FAIL",
    "DECISIONS",
    "PASS_OVERALL_THRESHOLD",
    "PASS_SAFETY_THRESHOLD",
    "PASS_FAILURE_RATE_THRESHOLD",
    "FAIL_OVERALL_THRESHOLD",
    "FAIL_SAFETY_THRESHOLD",
    "FAIL_FAILURE_RATE_THRESHOLD",
    "SEVERITY_CRITICAL",
    "SEVERITY_MAJOR",
    "SEVERITY_MINOR",
    "SEVERITIES",
    "SEVERITY_RANK",
    "CONFIDENCE_MIN",
    "CONFIDENCE_MAX",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "CONFIDENCE_FIELD",
    "EVIDENCE_CLAIM_FIELD",
    "EVIDENCE_TEXT_FIELDS",
    "DECISION_RANK",
]
