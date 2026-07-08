"""Deterministic report validation and release gating for EvalSurfer.

Two pure, standard-library-only services that operate on an already-produced
report. :class:`ReportValidator` performs *structural* validation entirely in
Python -- required keys are present, decisions and severities are drawn from the
allowed vocabularies, and every score sits in range -- with no JSON Schema
dependency and without reading any file. It accumulates every problem it finds
rather than stopping at the first. :class:`Gate` turns a report's decision into a
pass/fail release signal by ranking it against a required minimum decision.

Both are deterministic and immutable: they make no model calls, never mutate the
report, and rank decisions using :data:`constants.DECISION_RANK`. Report
traversal is delegated to :class:`ScoringModel`, which owns it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.core.scoring import ScoringModel

__all__ = [
    "ValidationResult",
    "GateResult",
    "ReportValidator",
    "Gate",
]

#: Top-level keys every report must carry (see ``report.schema.json``).
REQUIRED_TOP_LEVEL_KEYS: Final = ("overall", "pillars", "decision", "top_issues")
#: Inclusive lower bound for pillar/overall scores; the upper bound is
#: :data:`constants.PERFECT_SCORE`.
MIN_AGGREGATE_SCORE: Final = 0


@dataclass(frozen=True)
class ValidationResult:
    """The outcome of structurally validating one report."""

    valid: bool
    errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Render the result as a JSON-ready dict.

        Returns:
            ``{"valid": bool, "errors": [str, ...]}``.
        """
        return {"valid": self.valid, "errors": list(self.errors)}


@dataclass(frozen=True)
class GateResult:
    """Whether a report's decision clears a required minimum decision."""

    passed: bool
    decision: str
    minimum: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Render the gate result as a JSON-ready dict.

        Returns:
            ``{"passed": bool, "decision": str, "minimum": str,
            "reason": str}``.
        """
        return {
            "passed": self.passed,
            "decision": self.decision,
            "minimum": self.minimum,
            "reason": self.reason,
        }


def _one_of_error(label: str, value: Any, allowed: Sequence[str]) -> str:
    """Build a uniform "must be one of" error message.

    Args:
        label: Human-readable name of the field being validated.
        value: The offending value.
        allowed: The allowed vocabulary.

    Returns:
        A message naming the field, the offending value, and the allowed options.
    """
    return f"{label} {value!r} must be one of {list(allowed)}"


class ReportValidator:
    """Structurally validate an evaluation report in pure Python.

    Stateless: the rules carry no per-instance state, so the class is a cohesive
    namespace of static/class methods rather than something to instantiate. The
    validation is deterministic and standard-library-only -- it never reads a
    schema file, makes no model calls, and never mutates the report.
    """

    @classmethod
    def validate(cls, report: Any) -> dict[str, Any]:
        """Check a report's structure, accumulating every problem found.

        The following are checked, and *all* violations are reported (validation
        never stops at the first error):

        * the required top-level keys (``overall``, ``pillars``, ``decision``,
          ``top_issues``) are present;
        * ``report["decision"]`` and ``report["overall"]["decision"]`` are drawn
          from ``constants.DECISIONS`` when present;
        * every pillar key is one of ``constants.PILLARS``;
        * every criterion ``score`` is ``None`` or an int in
          ``[constants.CRITERION_MIN_SCORE, constants.CRITERION_MAX_SCORE]``;
        * every top issue ``severity`` is one of ``constants.SEVERITIES``;
        * every overall/pillar ``score`` is ``None`` or a number in
          ``[0, constants.PERFECT_SCORE]``.

        Args:
            report: The value to validate; a non-mapping fails with a single
                error rather than raising.

        Returns:
            ``{"valid": bool, "errors": [str, ...]}`` where ``valid`` is ``True``
            exactly when ``errors`` is empty.
        """
        if not isinstance(report, Mapping):
            return ValidationResult(False, ("report must be a mapping",)).to_dict()

        errors: list[str] = []
        errors.extend(cls._check_required_keys(report))
        errors.extend(cls._check_decision(report))
        errors.extend(cls._check_overall(report))
        errors.extend(cls._check_pillars(report))
        errors.extend(cls._check_criteria(report))
        errors.extend(cls._check_top_issues(report))
        return ValidationResult(not errors, tuple(errors)).to_dict()

    @staticmethod
    def _check_required_keys(report: Mapping[str, Any]) -> list[str]:
        """Return an error for each absent required top-level key.

        Args:
            report: The report mapping.

        Returns:
            One error per missing key in ``REQUIRED_TOP_LEVEL_KEYS``.
        """
        return [
            f"missing required key: {key!r}"
            for key in REQUIRED_TOP_LEVEL_KEYS
            if key not in report
        ]

    @staticmethod
    def _check_decision(report: Mapping[str, Any]) -> list[str]:
        """Validate the top-level ``decision`` value when present.

        Args:
            report: The report mapping.

        Returns:
            An error when ``decision`` is present but not in
            ``constants.DECISIONS``; otherwise an empty list. Absence is left to
            the required-keys check.
        """
        if "decision" not in report:
            return []
        decision = report["decision"]
        if decision in constants.DECISIONS:
            return []
        return [_one_of_error("decision", decision, constants.DECISIONS)]

    @classmethod
    def _check_overall(cls, report: Mapping[str, Any]) -> list[str]:
        """Validate the ``overall`` block's decision and score when present.

        Args:
            report: The report mapping.

        Returns:
            Errors for a non-mapping ``overall``, an out-of-vocabulary
            ``overall.decision``, or an out-of-range ``overall.score``.
        """
        if "overall" not in report:
            return []
        overall = report["overall"]
        if not isinstance(overall, Mapping):
            return ["overall must be a mapping"]

        errors: list[str] = []
        if "decision" in overall and overall["decision"] not in constants.DECISIONS:
            errors.append(
                _one_of_error("overall.decision", overall["decision"], constants.DECISIONS)
            )
        errors.extend(cls._aggregate_score_errors("overall", overall.get("score")))
        return errors

    @classmethod
    def _check_pillars(cls, report: Mapping[str, Any]) -> list[str]:
        """Validate pillar keys and each pillar's aggregate score.

        Args:
            report: The report mapping.

        Returns:
            Errors for a non-mapping ``pillars`` block, unknown pillar keys,
            non-mapping pillars, and out-of-range pillar scores.
        """
        if "pillars" not in report:
            return []
        pillars = report["pillars"]
        if not isinstance(pillars, Mapping):
            return ["pillars must be a mapping"]

        errors: list[str] = []
        for key, pillar in pillars.items():
            if key not in constants.PILLARS:
                errors.append(_one_of_error("pillar key", key, constants.PILLARS))
            if not isinstance(pillar, Mapping):
                errors.append(f"pillar {key!r} must be a mapping")
                continue
            errors.extend(cls._aggregate_score_errors(f"pillar {key!r}", pillar.get("score")))
        return errors

    @classmethod
    def _check_criteria(cls, report: Mapping[str, Any]) -> list[str]:
        """Validate every criterion score across all pillars.

        Report traversal is delegated to :meth:`ScoringModel.iter_criteria`, so
        malformed pillar/criteria containers are tolerated rather than raising.

        Args:
            report: The report mapping.

        Returns:
            One error per criterion whose ``score`` is neither ``None`` nor an
            int in the allowed criterion range.
        """
        errors: list[str] = []
        for _pillar_id, criterion in ScoringModel.iter_criteria(report):
            error = cls._criterion_score_error(criterion)
            if error is not None:
                errors.append(error)
        return errors

    @staticmethod
    def _check_top_issues(report: Mapping[str, Any]) -> list[str]:
        """Validate that every top issue carries a known severity.

        Args:
            report: The report mapping.

        Returns:
            Errors for a non-list ``top_issues`` block, non-mapping issues, and
            severities outside ``constants.SEVERITIES``.
        """
        if "top_issues" not in report:
            return []
        issues = report["top_issues"]
        if not isinstance(issues, Sequence) or isinstance(issues, (str, bytes)):
            return ["top_issues must be a list"]

        errors: list[str] = []
        for index, issue in enumerate(issues):
            if not isinstance(issue, Mapping):
                errors.append(f"top_issues[{index}] must be a mapping")
                continue
            severity = issue.get("severity")
            if severity not in constants.SEVERITIES:
                errors.append(
                    _one_of_error(
                        f"top_issues[{index}] severity", severity, constants.SEVERITIES
                    )
                )
        return errors

    @staticmethod
    def _criterion_score_error(criterion: Mapping[str, Any]) -> str | None:
        """Return an error if a criterion's score is out of range, else ``None``.

        Args:
            criterion: A single criterion mapping.

        Returns:
            An error string when ``score`` is neither ``None`` nor an int in
            ``[constants.CRITERION_MIN_SCORE, constants.CRITERION_MAX_SCORE]``;
            otherwise ``None``. Booleans are rejected (a bool is not a score).
        """
        score = criterion.get("score")
        if score is None:
            return None
        valid = (
            not isinstance(score, bool)
            and isinstance(score, int)
            and constants.CRITERION_MIN_SCORE <= score <= constants.CRITERION_MAX_SCORE
        )
        if valid:
            return None
        cid = criterion.get("id")
        name = cid if isinstance(cid, str) and cid else "unknown"
        return (
            f"criterion {name!r} score must be null or an int in "
            f"[{constants.CRITERION_MIN_SCORE}, {constants.CRITERION_MAX_SCORE}], "
            f"got {score!r}"
        )

    @staticmethod
    def _aggregate_score_errors(label: str, value: Any) -> list[str]:
        """Validate a pillar/overall score is ``None`` or a number in range.

        Args:
            label: Human-readable name of the score being checked.
            value: The raw score value.

        Returns:
            A single-item error list when ``value`` is neither ``None`` nor a
            number in ``[MIN_AGGREGATE_SCORE, constants.PERFECT_SCORE]``;
            otherwise an empty list. Booleans are rejected (a bool is not a score).
        """
        if value is None:
            return []
        valid = (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and MIN_AGGREGATE_SCORE <= value <= constants.PERFECT_SCORE
        )
        if valid:
            return []
        return [
            f"{label} score must be null or a number in "
            f"[{MIN_AGGREGATE_SCORE}, {constants.PERFECT_SCORE}], got {value!r}"
        ]


class Gate:
    """Rank a report's decision against a required minimum to gate releases.

    Stateless: the minimum bar is supplied per call, so the class is a cohesive
    namespace of static methods rather than something to instantiate.
    Deterministic and standard-library-only -- it makes no model calls and never
    mutates the report.
    """

    @staticmethod
    def evaluate(report: Mapping[str, Any], minimum: str) -> dict[str, Any]:
        """Decide whether a report's decision clears the ``minimum`` bar.

        The report passes when the rank of its decision is at least the rank of
        ``minimum`` under ``constants.DECISION_RANK`` (``fail`` <
        ``pass_with_fixes`` < ``pass``).

        Args:
            report: The report whose top-level ``decision`` is gated.
            minimum: The lowest decision that still passes; must be one of
                ``constants.DECISIONS``.

        Returns:
            ``{"passed": bool, "decision": str, "minimum": str, "reason": str}``.

        Raises:
            ValueError: If ``minimum`` is not a known decision, or the report's
                decision is missing or unknown.
        """
        if minimum not in constants.DECISIONS:
            raise ValueError(
                f"minimum must be one of {list(constants.DECISIONS)}, got {minimum!r}"
            )
        decision = report.get("decision") if isinstance(report, Mapping) else None
        if decision not in constants.DECISIONS:
            raise ValueError(f"unknown report decision: {decision!r}")

        passed = constants.DECISION_RANK[decision] >= constants.DECISION_RANK[minimum]
        return GateResult(
            passed=passed,
            decision=decision,
            minimum=minimum,
            reason=Gate._reason(passed, decision, minimum),
        ).to_dict()

    @staticmethod
    def _reason(passed: bool, decision: str, minimum: str) -> str:
        """Explain the gate outcome in one human-readable sentence.

        Args:
            passed: Whether the report cleared the minimum bar.
            decision: The report's decision.
            minimum: The minimum decision required.

        Returns:
            A sentence describing why the report passed or failed the gate.
        """
        relation = "meets or exceeds" if passed else "is below"
        return f"Decision {decision!r} {relation} the minimum bar of {minimum!r}."
