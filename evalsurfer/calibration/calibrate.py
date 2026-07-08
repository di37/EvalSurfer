"""Judge calibration for EvalSurfer -- the deterministic "eval of the eval".

An EvalSurfer report is produced by the agent/skill acting as an LLM judge.
This module never runs that judge; instead it *scores the judge*. A
:class:`CalibrationCase` freezes what a trustworthy judge should conclude about
one target: which pillars the planner makes applicable, the score band each
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
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import pvariance
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner, Signals
from evalsurfer.core.scoring import ScoringModel

__all__ = [
    "CalibrationCase",
    "Calibrator",
]

# Decisions that count as "not a fail" (a pass or a conditional pass), derived
# from the shared decision constants and named here for the false-rate metrics.
_PASSING_DECISIONS = frozenset(
    {constants.DECISION_PASS, constants.DECISION_PASS_WITH_FIXES}
)


def _validate_score_range(criterion_id: Any, bounds: Any) -> None:
    """Validate one ``criterion_id -> (min, max)`` expected-score-range entry.

    Args:
        criterion_id: The mapping key; must be a non-empty string.
        bounds: The mapping value; must be a ``(min, max)`` pair of ints on the
            criterion scale with ``min <= max``.

    Raises:
        TypeError: If ``criterion_id`` is not a non-empty string, or ``bounds``
            is not a 2-tuple of (non-bool) ints.
        ValueError: If a bound falls off the criterion scale or ``min > max``.
    """
    if not isinstance(criterion_id, str) or not criterion_id.strip():
        raise TypeError("expected_score_ranges keys must be non-empty strings")
    if not isinstance(bounds, tuple) or len(bounds) != 2:
        raise TypeError(
            f"expected_score_ranges[{criterion_id!r}] must be a (min, max) tuple"
        )
    low, high = bounds
    for bound in (low, high):
        if isinstance(bound, bool) or not isinstance(bound, int):
            raise TypeError(
                f"expected_score_ranges[{criterion_id!r}] bounds must be ints"
            )
        if not constants.CRITERION_MIN_SCORE <= bound <= constants.CRITERION_MAX_SCORE:
            raise ValueError(
                f"expected_score_ranges[{criterion_id!r}] bounds must be within "
                f"{constants.CRITERION_MIN_SCORE}-{constants.CRITERION_MAX_SCORE}"
            )
    if low > high:
        raise ValueError(
            f"expected_score_ranges[{criterion_id!r}] has min greater than max"
        )


def _validate_case(case: "CalibrationCase") -> None:
    """Fail fast on a malformed case so the calibration oracle stays trustworthy.

    Args:
        case: The case to validate immediately after construction.

    Raises:
        TypeError: If a field has the wrong type.
        ValueError: If a field carries an unknown pillar, decision, or severity,
            a blank name, or an invalid score range.
    """
    if not isinstance(case.name, str) or not case.name.strip():
        raise ValueError("name must be a non-empty string")
    if not isinstance(case.signals, Signals):
        raise TypeError("signals must be a planner.Signals instance")
    if not isinstance(case.expected_applicable_pillars, frozenset):
        raise TypeError("expected_applicable_pillars must be a frozenset")
    unknown = case.expected_applicable_pillars - set(constants.PILLARS)
    if unknown:
        raise ValueError(f"unknown pillars in expected: {sorted(unknown)}")
    if not isinstance(case.expected_score_ranges, Mapping):
        raise TypeError("expected_score_ranges must be a mapping")
    for criterion_id, bounds in case.expected_score_ranges.items():
        _validate_score_range(criterion_id, bounds)
    if case.expected_decision not in constants.DECISIONS:
        raise ValueError(f"expected_decision must be one of {constants.DECISIONS}")
    if (
        case.expected_top_issue_severity is not None
        and case.expected_top_issue_severity not in constants.SEVERITIES
    ):
        raise ValueError(
            "expected_top_issue_severity must be None or one of "
            f"{constants.SEVERITIES}"
        )
    if not isinstance(case.expected_safety_escalation, bool):
        raise TypeError("expected_safety_escalation must be a boolean")


@dataclass(frozen=True)
class CalibrationCase:
    """One hand-authored expectation for what a trustworthy judge should conclude.

    ``signals`` is a :class:`planner.Signals` snapshot of the evidence available
    for the target. ``expected_score_ranges`` maps a criterion id to an inclusive
    ``(min, max)`` band the judge's score should fall inside. The remaining
    ``expected_`` fields pin the decision, the severity of the worst reported
    issue (``None`` when no issue is expected), and whether a critical safety
    issue should be escalated. All fields are validated on construction.
    """

    name: str
    signals: Signals
    expected_applicable_pillars: frozenset[str]
    expected_score_ranges: Mapping[str, tuple[int, int]]
    expected_decision: str
    expected_top_issue_severity: str | None
    expected_safety_escalation: bool

    def __post_init__(self) -> None:
        """Validate the case immediately after construction.

        Raises:
            TypeError: If a field has the wrong type.
            ValueError: If a field carries an unknown pillar, decision, or
                severity, a blank name, or an invalid score range.
        """
        _validate_case(self)


class Calibrator:
    """Score a judge against a :class:`CalibrationCase` -- the "eval of the eval".

    Stateless: the set of safety criterion ids is a class attribute and every
    method derives its result from the case and the judge report(s) alone. The
    judge reports are external input produced by the agent/skill; this class only
    reads what they already contain and never mutates them or calls a model.
    """

    #: Ids of the criteria that live on the safety pillar, taken from the
    #: planner's canonical catalog. Used to tell a critical *safety* issue from
    #: any other critical issue.
    _SAFETY_CRITERION_IDS: frozenset[str] = frozenset(
        criterion.id
        for criterion in EvaluationPlanner.CRITERIA
        if criterion.pillar == constants.PILLAR_SAFETY
    )

    @staticmethod
    def _applicable_pillars(signals: Signals) -> frozenset[str]:
        """Return the pillar ids the planner marks applicable for these signals.

        Args:
            signals: The evidence snapshot for the target.

        Returns:
            The frozenset of applicable pillar ids.
        """
        plan = EvaluationPlanner.plan(signals)
        return frozenset(pillar.id for pillar in plan.pillars if pillar.applicable)

    @staticmethod
    def _score_value(value: Any) -> int | None:
        """Coerce a judged criterion score to an ``int``, or ``None`` otherwise.

        Args:
            value: A raw ``score`` from a report criterion.

        Returns:
            The value as an ``int``, or ``None`` when it is missing, a bool, or
            not an int (booleans never count as a score).
        """
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value

    @classmethod
    def _scores_by_id(cls, report: Mapping[str, Any]) -> dict[str, int]:
        """Map each assessed criterion id to its integer judged score.

        Args:
            report: A judge-produced report mapping.

        Returns:
            An id-keyed dict of integer scores; ``None`` / non-int scores are
            skipped and the first score wins if an id repeats.
        """
        scores: dict[str, int] = {}
        for _pillar_id, criterion in ScoringModel.iter_criteria(report):
            cid = criterion.get("id")
            if not isinstance(cid, str) or cid in scores:
                continue
            score = cls._score_value(criterion.get("score"))
            if score is not None:
                scores[cid] = score
        return scores

    @staticmethod
    def _within_range(score: int | None, bounds: tuple[int, int]) -> bool:
        """Report whether a judged score falls in an inclusive ``(min, max)`` band.

        Args:
            score: The judged criterion score, or ``None`` when not assessed.
            bounds: The inclusive ``(min, max)`` expected band.

        Returns:
            ``True`` when ``score`` is present and ``min <= score <= max``.
        """
        if score is None:
            return False
        low, high = bounds
        return low <= score <= high

    @staticmethod
    def _top_issues(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        """Return the report's top issues as a list of mappings.

        Args:
            report: A judge-produced report mapping.

        Returns:
            The ``top_issues`` entries that are mappings; an absent or malformed
            section yields an empty list.
        """
        issues = report.get("top_issues")
        if not isinstance(issues, Sequence) or isinstance(issues, (str, bytes)):
            return []
        return [issue for issue in issues if isinstance(issue, Mapping)]

    @classmethod
    def _top_issue_severity(cls, report: Mapping[str, Any]) -> str | None:
        """Return the severity of the highest-severity top issue, or ``None``.

        Args:
            report: A judge-produced report mapping.

        Returns:
            The most severe known severity (smallest ``constants.SEVERITY_RANK``)
            among the top issues, or ``None`` when none carry a known severity.
        """
        severities = [
            issue.get("severity")
            for issue in cls._top_issues(report)
            if issue.get("severity") in constants.SEVERITY_RANK
        ]
        if not severities:
            return None
        return min(severities, key=lambda severity: constants.SEVERITY_RANK[severity])

    @classmethod
    def _has_critical_safety_issue(cls, report: Mapping[str, Any]) -> bool:
        """Report whether a critical top issue is attributed to a safety criterion.

        A safety escalation is a top issue at ``constants.SEVERITY_CRITICAL``
        whose ``criterion_id`` names one of the safety-pillar criteria; a
        critical issue on a non-safety criterion is not a safety escalation.

        Args:
            report: A judge-produced report mapping.

        Returns:
            ``True`` when such an issue exists, else ``False``.
        """
        return any(
            issue.get("severity") == constants.SEVERITY_CRITICAL
            and issue.get("criterion_id") in cls._SAFETY_CRITERION_IDS
            for issue in cls._top_issues(report)
        )

    @classmethod
    def check_report(
        cls, case: CalibrationCase, judge_report: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Compare one judge-produced report against a calibration case.

        Checks four categorical matches plus the per-criterion score bands:
        ``plan_match`` (the planner's applicable pillars for ``case.signals``
        equal ``case.expected_applicable_pillars``), ``decision_match`` (the
        report's ``decision`` equals ``case.expected_decision``),
        ``top_issue_match`` (the highest-severity top issue equals
        ``case.expected_top_issue_severity``, or both are ``None``), and
        ``safety_escalation_match`` (whether a critical safety top issue exists
        equals ``case.expected_safety_escalation``). ``per_criterion`` maps each
        expected criterion id to whether the judged score fell inside its band,
        and ``scores_within_range`` is ``True`` only when every one did.
        ``agreement`` is the conjunction of the four categorical matches (it does
        not fold in the score bands). The report is never mutated.

        Args:
            case: The calibration expectation.
            judge_report: One report produced by the judge for the same target.

        Returns:
            ``{"plan_match", "per_criterion", "scores_within_range",
            "decision_match", "top_issue_match", "safety_escalation_match",
            "agreement"}``.

        Raises:
            TypeError: If ``case`` is not a :class:`CalibrationCase` or
                ``judge_report`` is not a mapping.
        """
        if not isinstance(case, CalibrationCase):
            raise TypeError("case must be a CalibrationCase")
        if not isinstance(judge_report, Mapping):
            raise TypeError("judge_report must be a mapping")

        plan_match = (
            cls._applicable_pillars(case.signals)
            == case.expected_applicable_pillars
        )

        judged_scores = cls._scores_by_id(judge_report)
        per_criterion = {
            criterion_id: cls._within_range(judged_scores.get(criterion_id), bounds)
            for criterion_id, bounds in case.expected_score_ranges.items()
        }
        scores_within_range = all(per_criterion.values())

        decision_match = judge_report.get("decision") == case.expected_decision
        top_issue_match = (
            cls._top_issue_severity(judge_report)
            == case.expected_top_issue_severity
        )
        safety_escalation_match = (
            cls._has_critical_safety_issue(judge_report)
            == case.expected_safety_escalation
        )

        agreement = (
            plan_match
            and decision_match
            and top_issue_match
            and safety_escalation_match
        )

        return {
            "plan_match": plan_match,
            "per_criterion": per_criterion,
            "scores_within_range": scores_within_range,
            "decision_match": decision_match,
            "top_issue_match": top_issue_match,
            "safety_escalation_match": safety_escalation_match,
            "agreement": agreement,
        }

    @staticmethod
    def _fraction(count: int, total: int) -> float:
        """Return ``count / total`` rounded, or ``0.0`` when ``total`` is zero.

        Args:
            count: The numerator (a non-negative count).
            total: The denominator (the number of runs).

        Returns:
            The fraction rounded to ``constants.SHARE_PRECISION`` decimals, or
            ``0.0`` when ``total`` is not positive.
        """
        if total <= 0:
            return 0.0
        return round(count / total, constants.SHARE_PRECISION)

    @classmethod
    def _false_pass_rate(
        cls, case: CalibrationCase, decisions: Sequence[Any], runs: int
    ) -> float:
        """Fraction of runs judged non-fail when the case expects a fail.

        Args:
            case: The calibration case.
            decisions: The per-run judged decisions.
            runs: The number of runs.

        Returns:
            The false-pass fraction, or ``0.0`` when the case does not expect a
            fail (there is then no false pass to measure).
        """
        if case.expected_decision != constants.DECISION_FAIL:
            return 0.0
        passed = sum(1 for decision in decisions if decision in _PASSING_DECISIONS)
        return cls._fraction(passed, runs)

    @classmethod
    def _false_fail_rate(
        cls, case: CalibrationCase, decisions: Sequence[Any], runs: int
    ) -> float:
        """Fraction of runs judged fail when the case expects a (conditional) pass.

        Args:
            case: The calibration case.
            decisions: The per-run judged decisions.
            runs: The number of runs.

        Returns:
            The false-fail fraction, or ``0.0`` when the case expects a fail
            (there is then no false fail to measure).
        """
        if case.expected_decision not in _PASSING_DECISIONS:
            return 0.0
        failed = sum(
            1 for decision in decisions if decision == constants.DECISION_FAIL
        )
        return cls._fraction(failed, runs)

    @staticmethod
    def _overall_score(report: Mapping[str, Any]) -> float | None:
        """Return the report's overall score as a float, or ``None`` when absent.

        Args:
            report: A judge-produced report mapping.

        Returns:
            ``overall.score`` as a float, or ``None`` when missing or non-numeric
            (booleans are treated as non-numeric).
        """
        overall = report.get("overall")
        if not isinstance(overall, Mapping):
            return None
        value = overall.get("score")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return float(value)

    @classmethod
    def _score_variance(cls, reports: Sequence[Mapping[str, Any]]) -> float:
        """Population variance of the judged overall scores across runs.

        Args:
            reports: The judge-produced report mappings.

        Returns:
            ``statistics.pvariance`` of the present overall scores rounded to
            ``constants.SHARE_PRECISION`` decimals, or ``0.0`` when fewer than two
            runs carry a numeric overall score.
        """
        scores = [
            score
            for score in (cls._overall_score(report) for report in reports)
            if score is not None
        ]
        if len(scores) < 2:
            return 0.0
        return round(pvariance(scores), constants.SHARE_PRECISION)

    @classmethod
    def summarize(
        cls, case: CalibrationCase, judge_reports: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        """Aggregate calibration metrics over many repeated judge runs.

        Computes the ``constants.CALIBRATION_METRICS`` over ``N`` reports the
        judge produced for the same target: ``agreement`` (fraction whose
        decision matches ``case.expected_decision``), ``false_pass_rate``
        (fraction judged pass / pass_with_fixes when the case expects a fail),
        ``false_fail_rate`` (fraction judged fail when the case expects a pass or
        pass_with_fixes), and ``score_variance`` (population variance of the
        judged overall scores, ``0.0`` for fewer than two). Rates are ``0.0``
        when they do not apply and when ``N`` is zero. Inputs are never mutated.

        Args:
            case: The calibration expectation.
            judge_reports: The reports the judge produced for the target.

        Returns:
            ``{"name", "runs", "agreement", "false_pass_rate", "false_fail_rate",
            "score_variance"}``.

        Raises:
            TypeError: If ``case`` is not a :class:`CalibrationCase`,
                ``judge_reports`` is not a (non-string) sequence, or any entry is
                not a mapping.
        """
        if not isinstance(case, CalibrationCase):
            raise TypeError("case must be a CalibrationCase")
        if not isinstance(judge_reports, Sequence) or isinstance(
            judge_reports, (str, bytes)
        ):
            raise TypeError("judge_reports must be a sequence of report mappings")
        reports = list(judge_reports)
        for report in reports:
            if not isinstance(report, Mapping):
                raise TypeError("each judge report must be a mapping")

        runs = len(reports)
        decisions = [report.get("decision") for report in reports]

        return {
            "name": case.name,
            "runs": runs,
            "agreement": cls._fraction(
                sum(
                    1
                    for decision in decisions
                    if decision == case.expected_decision
                ),
                runs,
            ),
            "false_pass_rate": cls._false_pass_rate(case, decisions, runs),
            "false_fail_rate": cls._false_fail_rate(case, decisions, runs),
            "score_variance": cls._score_variance(reports),
        }
