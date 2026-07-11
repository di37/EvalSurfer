"""Structural report validation in pure Python.

:class:`ReportValidator` checks an already-produced report -- required keys,
allowed decision/severity vocabularies, and in-range scores -- with no JSON
Schema dependency and without reading any file, accumulating every problem it
finds rather than stopping at the first. Report traversal is delegated to
:class:`ScoringModel`, which owns it.
"""

from __future__ import annotations

from typing import Any, Final, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.core.report.models import ValidationResult
from evalsurfer.core.scoring import ScoringModel

__all__ = ["ReportValidator"]

#: Top-level keys every report must carry (see ``report.schema.json``).
REQUIRED_TOP_LEVEL_KEYS: Final = ("overall", "decision", "top_issues")
#: Inclusive lower bound for category/overall scores; the upper bound is
#: :data:`constants.PERFECT_SCORE`.
MIN_AGGREGATE_SCORE: Final = 0


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

        * the required top-level keys (``overall``, ``decision``,
          ``top_issues``) are present;
        * ``report["decision"]`` and ``report["overall"]["decision"]`` are drawn
          from ``constants.DECISIONS`` when present;
        * each report section (``metrics`` / ``assurance``) only carries the
          categories assigned to it by the report nesting;
        * every criterion ``score`` is ``None`` or an int in
          ``[constants.CRITERION_MIN_SCORE, constants.CRITERION_MAX_SCORE]``;
        * every top issue ``severity`` is one of ``constants.SEVERITIES``;
        * every overall/category ``score`` is ``None`` or a number in
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
        errors.extend(cls._check_layers(report))
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
    def _check_layers(cls, report: Mapping[str, Any]) -> list[str]:
        """Validate report nesting and each category's aggregate score.

        Args:
            report: The report mapping.

        Returns:
            Errors for a non-mapping report section (``metrics`` / ``assurance``),
            category keys that do not belong in that section, non-mapping
            categories, and out-of-range category scores.
        """
        errors: list[str] = []
        for layer_id in constants.LAYERS:
            if layer_id not in report:
                continue
            layer = report[layer_id]
            if not isinstance(layer, Mapping):
                errors.append(f"{layer_id} must be a mapping")
                continue
            allowed = constants.CATEGORIES_BY_LAYER[layer_id]
            for key, category in layer.items():
                if key not in allowed:
                    errors.append(_one_of_error(f"{layer_id} category key", key, allowed))
                if not isinstance(category, Mapping):
                    errors.append(f"category {key!r} must be a mapping")
                    continue
                errors.extend(cls._aggregate_score_errors(f"category {key!r}", category.get("score")))
        return errors

    @classmethod
    def _check_criteria(cls, report: Mapping[str, Any]) -> list[str]:
        """Validate every criterion score across all categories.

        Report traversal is delegated to :meth:`ScoringModel.iter_criteria`, so
        malformed category/criteria containers are tolerated rather than raising.

        Args:
            report: The report mapping.

        Returns:
            One error per criterion whose ``score`` is neither ``None`` nor an
            int in the allowed criterion range.
        """
        errors: list[str] = []
        for _category_id, criterion in ScoringModel.iter_criteria(report):
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
        """Validate a category/overall score is ``None`` or a number in range.

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
