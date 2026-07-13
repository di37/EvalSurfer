"""Parsing, validation, and decision statistics for the harness-invariance study.

The boundary layer: raw payloads are validated fail-fast into
:class:`~evalsurfer.analysis.calibration.harness.models.Judgment` grids here, so
the decomposition math never sees malformed data. Also home to the categorical
decision-flip statistics (deterministic companions to the variance
decomposition). Standard library only; inputs are never mutated.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import isfinite
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.analysis.calibration.agreement import AgreementStats
from evalsurfer.analysis.calibration.harness.models import Judgment
from evalsurfer.core.scoring import ScoringModel

# Top-level payload keys accepted by HarnessInvariance.analyze (typo protection).
_PAYLOAD_KEYS = frozenset(
    {
        "judgments",
        "dependability_target",
        "dstudy_max_harnesses",
        "dstudy_max_replications",
    }
)
_MAX_REPORTED_CELLS = 10  # cap on missing-cell listings in error messages


def parse_options(payload: Mapping[str, Any]) -> tuple[float, int, int]:
    """Validate the analysis options, applying the documented defaults.

    Args:
        payload: The full analyze payload.

    Returns:
        ``(dependability_target, dstudy_max_harnesses, dstudy_max_replications)``.

    Raises:
        ValueError: If an unknown top-level key is present, the target is not in
            ``(0, 1)``, or a D-study cap is not a positive integer at most
            ``constants.DSTUDY_MAX_LIMIT`` (the grid is materialized, so the
            caps bound real allocation).
    """
    unknown = sorted(set(payload) - _PAYLOAD_KEYS)
    if unknown:
        raise ValueError(f"unknown payload key(s): {', '.join(unknown)}")

    target = payload.get("dependability_target", constants.DEFAULT_DEPENDABILITY_TARGET)
    if isinstance(target, bool) or not isinstance(target, (int, float)):
        raise ValueError("dependability_target must be a number in (0, 1)")
    if not isfinite(target) or not 0 < target < 1:
        raise ValueError("dependability_target must be in (0, 1) exclusive")

    def _cap(key: str, default: int) -> int:
        value = payload.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{key} must be a positive integer")
        if value > constants.DSTUDY_MAX_LIMIT:
            raise ValueError(
                f"{key} must be at most {constants.DSTUDY_MAX_LIMIT}: the "
                "D-study grid is materialized point by point"
            )
        return value

    return (
        float(target),
        _cap("dstudy_max_harnesses", constants.DSTUDY_MAX_HARNESSES),
        _cap("dstudy_max_replications", constants.DSTUDY_MAX_REPLICATIONS),
    )


def parse_judgments(payload: Mapping[str, Any]) -> list[Judgment]:
    """Parse and validate the ``judgments`` list into :class:`Judgment` records.

    Args:
        payload: The full analyze payload.

    Returns:
        The parsed judgments, in input order.

    Raises:
        TypeError: If ``judgments`` is not a sequence of mappings.
        ValueError: If it is empty, an identity field is invalid, a key is
            duplicated, or a score is invalid (the offending judgment is named).
    """
    raw = payload.get("judgments")
    if isinstance(raw, (str, bytes)) or not isinstance(raw, Sequence):
        raise TypeError("judgments must be a sequence of judgment mappings")
    if not raw:
        raise ValueError("judgments must not be empty")

    judgments: list[Judgment] = []
    seen: set[tuple[str, str, int]] = set()
    for entry in raw:
        if not isinstance(entry, Mapping):
            raise TypeError("each judgment must be a mapping")
        target = _identity(entry, "target")
        harness = _identity(entry, "harness")
        replication = _replication(entry)
        key = (target, harness, replication)
        if key in seen:
            raise ValueError(f"duplicate judgment key {key!r}")
        seen.add(key)
        judgments.append(_project(entry, target, harness, replication))
    return judgments


def build_grid(
    judgments: Sequence[Judgment],
) -> tuple[list[str], list[str], int, dict[tuple[str, str], list[Judgment]]]:
    """Validate the crossed design and index judgments by ``(target, harness)`` cell.

    Args:
        judgments: The parsed judgments.

    Returns:
        ``(targets, harnesses, n_replications, cells)`` with targets/harnesses
        sorted and each cell's judgments ordered by replication label.

    Raises:
        ValueError: If there are fewer than two targets or harnesses, the grid
            is incomplete (missing cells are listed), or replication counts
            differ across cells.
    """
    targets = sorted({judgment.target for judgment in judgments})
    harnesses = sorted({judgment.harness for judgment in judgments})
    if len(targets) < 2:
        raise ValueError("at least 2 targets are required")
    if len(harnesses) < 2:
        raise ValueError("at least 2 harnesses are required")

    cells: dict[tuple[str, str], list[Judgment]] = {}
    for judgment in judgments:
        cells.setdefault((judgment.target, judgment.harness), []).append(judgment)

    missing = [
        (target, harness)
        for target in targets
        for harness in harnesses
        if (target, harness) not in cells
    ]
    if missing:
        shown = missing[:_MAX_REPORTED_CELLS]
        suffix = "" if len(missing) <= _MAX_REPORTED_CELLS else f" (+{len(missing) - _MAX_REPORTED_CELLS} more)"
        raise ValueError(
            f"incomplete grid: missing (target, harness) cells: {shown}{suffix}"
        )

    counts = {cell: len(entries) for cell, entries in cells.items()}
    n_replications = counts[(targets[0], harnesses[0])]
    uneven = sorted(cell for cell, count in counts.items() if count != n_replications)
    if uneven:
        raise ValueError(
            "replication counts differ across cells: expected "
            f"{n_replications}, got {[(cell, counts[cell]) for cell in uneven[:_MAX_REPORTED_CELLS]]}"
        )

    ordered = {
        cell: sorted(entries, key=lambda judgment: judgment.replication)
        for cell, entries in cells.items()
    }
    return targets, harnesses, n_replications, ordered


def decision_analysis(
    targets: Sequence[str],
    harnesses: Sequence[str],
    cells: Mapping[tuple[str, str], Sequence[Judgment]],
) -> dict[str, Any] | None:
    """Categorical decision-flip statistics over the judgment grid.

    Args:
        targets: The sorted target ids.
        harnesses: The sorted harness ids.
        cells: The grid of judgments.

    Returns:
        ``None`` when no judgment carries any decision; otherwise a dict with
        ``fleiss_kappa`` (over per-harness modal decisions; ``None`` when any
        panel slot has no valid decision), ``mean_flip_rate``,
        ``p_flip_within_harness`` (``None`` when there are no replication
        pairs), ``p_flip_between_harness``, ``per_target`` (each entry carries
        ``flip_rate`` and the severity-weighted ``weighted_flip`` -- the mean
        ``DECISION_RANK`` band distance from the modal decision, so a
        fail<->pass flip counts 2 and an adjacent flip counts 1),
        ``invalid_decisions`` (count of decisions present but outside
        ``constants.DECISIONS``), and ``invalid`` (each such judgment named as
        ``{"target", "harness", "replication", "decision"}``).
    """
    all_judgments = [judgment for cell in cells.values() for judgment in cell]
    if all(judgment.decision is None for judgment in all_judgments):
        return None

    valid = set(constants.DECISIONS)
    invalid = [
        {
            "target": judgment.target,
            "harness": judgment.harness,
            "replication": judgment.replication,
            "decision": judgment.decision,
        }
        for target in targets
        for harness in harnesses
        for judgment in cells[(target, harness)]
        if judgment.decision is not None and judgment.decision not in valid
    ]

    per_target: list[dict[str, Any]] = []
    flip_rates: list[float] = []
    for target in targets:
        decisions = [
            judgment.decision
            for harness in harnesses
            for judgment in cells[(target, harness)]
            if judgment.decision in valid
        ]
        if not decisions:
            continue
        modal = _modal(decisions)
        flip_rate = sum(1 for decision in decisions if decision != modal) / len(decisions)
        weighted_flip = sum(
            abs(constants.DECISION_RANK[decision] - constants.DECISION_RANK[modal])
            for decision in decisions
        ) / len(decisions)
        flip_rates.append(flip_rate)
        per_target.append(
            {
                "target": target,
                "modal": modal,
                "flip_rate": round(flip_rate, constants.SHARE_PRECISION),
                "weighted_flip": round(weighted_flip, constants.SHARE_PRECISION),
            }
        )

    return {
        "fleiss_kappa": _panel_kappa(targets, harnesses, cells, valid),
        "mean_flip_rate": (
            round(sum(flip_rates) / len(flip_rates), constants.SHARE_PRECISION)
            if flip_rates
            else None
        ),
        "p_flip_within_harness": _pair_flip_rate(
            _within_harness_pairs(cells, valid)
        ),
        "p_flip_between_harness": _pair_flip_rate(
            _between_harness_pairs(targets, harnesses, cells, valid)
        ),
        "per_target": per_target,
        "invalid_decisions": len(invalid),
        "invalid": invalid,
    }


# --------------------------------------------------------------------------- #
# Judgment projection (full report or slim record)
# --------------------------------------------------------------------------- #


def _identity(entry: Mapping[str, Any], field: str) -> str:
    """A non-empty string identity field, or raise."""
    value = entry.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"judgment {field} must be a non-empty string, got {value!r}")
    return value


def _replication(entry: Mapping[str, Any]) -> int:
    """A positive integer replication label, or raise (bools rejected)."""
    value = entry.get("replication")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"judgment replication must be a positive integer, got {value!r}")
    return value


def _project(
    entry: Mapping[str, Any], target: str, harness: str, replication: int
) -> Judgment:
    """Project a judgment's report (full or slim) into a :class:`Judgment`.

    A mapping with an ``overall`` block is treated as a full EvalSurfer report
    (score from ``overall.score``, decision preferring ``overall.decision`` then
    the top-level ``decision``, criteria via :meth:`ScoringModel.iter_criteria`);
    anything else is a slim ``{"score", "decision", "criteria"}`` record.
    """
    where = f"judgment ({target!r}, {harness!r}, rep {replication})"
    report = entry.get("report")
    if not isinstance(report, Mapping):
        raise ValueError(f"{where}: report must be a mapping")

    if isinstance(report.get("overall"), Mapping):
        overall = report["overall"]
        score = _score(overall.get("score"), where)
        decision = _decision(overall.get("decision")) or _decision(report.get("decision"))
        criteria = {}
        for _, criterion in ScoringModel.iter_criteria(report):
            criterion_id = criterion.get("id")
            if not isinstance(criterion_id, str) or not criterion_id:
                continue
            if criterion_id in criteria:
                raise ValueError(
                    f"{where}: criterion {criterion_id!r} appears in more than "
                    "one report section; duplicate ids would silently overwrite "
                    "scores in the per-criterion profile"
                )
            criteria[criterion_id] = _criterion_score(
                criterion.get("score"), criterion_id, where
            )
    else:
        score = _score(report.get("score"), where)
        decision = _decision(report.get("decision"))
        criteria = _slim_criteria(report.get("criteria"), where)

    return Judgment(
        target=target,
        harness=harness,
        replication=replication,
        score=score,
        decision=decision,
        criteria=criteria or None,
    )


def _score(value: Any, where: str) -> float:
    """A finite overall score within ``[0, PERFECT_SCORE]``, or raise."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or not 0 <= value <= constants.PERFECT_SCORE
    ):
        raise ValueError(
            f"{where}: overall score must be a number in "
            f"[0, {constants.PERFECT_SCORE:g}], got {value!r}"
        )
    return float(value)


def _decision(value: Any) -> str | None:
    """The decision as a string; ``None`` only when absent (or empty string).

    A non-string decision (e.g. a numeric code) is preserved via ``str`` rather
    than silently dropped, so the decision analysis counts and names it as
    invalid instead of concluding no decisions were supplied.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    return str(value)


def _criterion_score(value: Any, criterion_id: Any, where: str) -> int | None:
    """A criterion score that is ``None`` or an int in the 1-5 scale, or raise."""
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not constants.CRITERION_MIN_SCORE <= value <= constants.CRITERION_MAX_SCORE
    ):
        raise ValueError(
            f"{where}: criterion {criterion_id!r} score must be null or an int in "
            f"[{constants.CRITERION_MIN_SCORE}, {constants.CRITERION_MAX_SCORE}], "
            f"got {value!r}"
        )
    return value


def _slim_criteria(value: Any, where: str) -> dict[str, int | None]:
    """Validate a slim record's ``criteria`` mapping."""
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{where}: criteria must be a mapping of id to score")
    criteria: dict[str, int | None] = {}
    for criterion_id, score in value.items():
        if not isinstance(criterion_id, str) or not criterion_id:
            raise ValueError(f"{where}: criterion ids must be non-empty strings")
        criteria[criterion_id] = _criterion_score(score, criterion_id, where)
    return criteria


# --------------------------------------------------------------------------- #
# Decision statistics internals
# --------------------------------------------------------------------------- #


def _modal(decisions: Sequence[str]) -> str:
    """The most common decision; ties break to the most severe (lowest rank)."""
    counts = Counter(decisions)
    top = max(counts.values())
    tied = [decision for decision, count in counts.items() if count == top]
    return min(tied, key=lambda decision: constants.DECISION_RANK[decision])


def _panel_kappa(
    targets: Sequence[str],
    harnesses: Sequence[str],
    cells: Mapping[tuple[str, str], Sequence[Judgment]],
    valid: set[str],
) -> float | None:
    """Fleiss' kappa over per-harness modal decisions (harnesses as the panel).

    Returns ``None`` when any ``(target, harness)`` slot has no valid decision,
    since the panel is then incomplete and kappa is undefined.
    """
    rows: list[dict[str, int]] = []
    for target in targets:
        row: Counter = Counter()
        for harness in harnesses:
            decisions = [
                judgment.decision
                for judgment in cells[(target, harness)]
                if judgment.decision in valid
            ]
            if not decisions:
                return None
            row[_modal(decisions)] += 1
        rows.append(dict(row))
    return AgreementStats.fleiss_kappa(rows)


def _within_harness_pairs(
    cells: Mapping[tuple[str, str], Sequence[Judgment]], valid: set[str]
) -> list[tuple[str, str]]:
    """Decision pairs from the same cell across different replications."""
    pairs: list[tuple[str, str]] = []
    for cell in cells.values():
        decisions = [
            judgment.decision for judgment in cell if judgment.decision in valid
        ]
        pairs.extend(combinations(decisions, 2))
    return pairs


def _between_harness_pairs(
    targets: Sequence[str],
    harnesses: Sequence[str],
    cells: Mapping[tuple[str, str], Sequence[Judgment]],
    valid: set[str],
) -> list[tuple[str, str]]:
    """Decision pairs for the same target across different harnesses."""
    pairs: list[tuple[str, str]] = []
    for target in targets:
        for harness_a, harness_b in combinations(harnesses, 2):
            first = [
                judgment.decision
                for judgment in cells[(target, harness_a)]
                if judgment.decision in valid
            ]
            second = [
                judgment.decision
                for judgment in cells[(target, harness_b)]
                if judgment.decision in valid
            ]
            pairs.extend((a, b) for a in first for b in second)
    return pairs


def _pair_flip_rate(pairs: Sequence[tuple[str, str]]) -> float | None:
    """Fraction of decision pairs that disagree, or ``None`` with no pairs."""
    if not pairs:
        return None
    differing = sum(1 for a, b in pairs if a != b)
    return round(differing / len(pairs), constants.SHARE_PRECISION)
