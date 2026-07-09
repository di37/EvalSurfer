"""Machine-readable release guardrails for EvalSurfer.

Where :class:`~evalsurfer.core.report.Gate` decides whether a report clears a
single minimum decision, a *guardrail policy* lets a team encode several release
rules in one ``guardrails.json`` file and have the gate enforce them
deterministically: a minimum decision, a safety-pillar floor, a coverage floor,
a block on any critical issue, a fix-attempt cap, and a sensitive-path denylist
that forces human review when a release touches protected files.

:class:`Guardrails` *reuses* the existing :class:`Gate` and
:class:`~evalsurfer.diagnostics.review_gate.ReviewGate` rather than
reimplementing them; the policy only adds team-specific rules on top. Everything
here is deterministic, standard-library only (``json`` + ``fnmatch``), and makes
no model calls; inputs are never mutated. Path matching is case-insensitive and
uses :func:`fnmatch.fnmatchcase` semantics (``*`` matches across ``/``), so it is
identical on every platform.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.core.report import Gate
from evalsurfer.diagnostics.review_gate import ReviewGate

__all__ = ["GuardrailPolicy", "Guardrails"]


def _optional_number(
    value: Any, name: str, low: float, high: float
) -> float | None:
    """Validate an optional numeric policy field within an inclusive range.

    Args:
        value: The raw value, or ``None`` when the field is absent.
        name: The field name, for error messages.
        low: The inclusive lower bound.
        high: The inclusive upper bound.

    Returns:
        The value as a ``float``, or ``None`` when absent.

    Raises:
        TypeError: If ``value`` is present but not a (non-bool) number.
        ValueError: If ``value`` falls outside ``[low, high]``.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number or null")
    if not low <= value <= high:
        raise ValueError(f"{name} must be within {low}-{high}")
    return float(value)


@dataclass(frozen=True)
class GuardrailPolicy:
    """A release policy the gate enforces against a produced report.

    Every field is optional; an omitted rule is simply not enforced. Loaded from
    a ``guardrails.json`` mapping via :meth:`from_mapping`, which validates on
    construction so a malformed policy fails fast.
    """

    min_decision: str = constants.DECISION_PASS_WITH_FIXES
    min_safety: float | None = None
    coverage_floor: float | None = None
    block_on_critical_issue: bool = False
    sensitive_paths: tuple[str, ...] = ()
    max_fix_attempts: int | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "GuardrailPolicy":
        """Build and validate a policy from a ``guardrails.json`` mapping.

        Args:
            data: The parsed policy object; recognised keys are
                :data:`constants.GUARDRAIL_FIELDS`.

        Returns:
            The validated :class:`GuardrailPolicy`.

        Raises:
            TypeError: If ``data`` or a field has the wrong type.
            ValueError: If an unknown key is present or a field is out of range.
        """
        if not isinstance(data, Mapping):
            raise TypeError("guardrail policy must be an object")
        unknown = set(data) - set(constants.GUARDRAIL_FIELDS)
        if unknown:
            raise ValueError(
                f"unknown guardrail field(s): {', '.join(sorted(unknown))}"
            )

        min_decision = data.get(
            constants.GUARDRAIL_MIN_DECISION, constants.DECISION_PASS_WITH_FIXES
        )
        if min_decision not in constants.DECISIONS:
            raise ValueError(
                f"{constants.GUARDRAIL_MIN_DECISION} must be one of {constants.DECISIONS}"
            )

        block = data.get(constants.GUARDRAIL_BLOCK_ON_CRITICAL_ISSUE, False)
        if not isinstance(block, bool):
            raise TypeError(
                f"{constants.GUARDRAIL_BLOCK_ON_CRITICAL_ISSUE} must be a boolean"
            )

        raw_paths = data.get(constants.GUARDRAIL_SENSITIVE_PATHS, ())
        if not isinstance(raw_paths, (list, tuple)) or not all(
            isinstance(pattern, str) for pattern in raw_paths
        ):
            raise TypeError(
                f"{constants.GUARDRAIL_SENSITIVE_PATHS} must be a list of strings"
            )

        attempts = data.get(constants.GUARDRAIL_MAX_FIX_ATTEMPTS)
        if attempts is not None and (
            isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1
        ):
            raise ValueError(
                f"{constants.GUARDRAIL_MAX_FIX_ATTEMPTS} must be a positive integer or null"
            )

        return cls(
            min_decision=min_decision,
            min_safety=_optional_number(
                data.get(constants.GUARDRAIL_MIN_SAFETY),
                constants.GUARDRAIL_MIN_SAFETY,
                0.0,
                constants.PERFECT_SCORE,
            ),
            coverage_floor=_optional_number(
                data.get(constants.GUARDRAIL_COVERAGE_FLOOR),
                constants.GUARDRAIL_COVERAGE_FLOOR,
                0.0,
                1.0,
            ),
            block_on_critical_issue=block,
            sensitive_paths=tuple(raw_paths),
            max_fix_attempts=attempts,
        )


class Guardrails:
    """Enforce a :class:`GuardrailPolicy` against a produced report.

    Stateless: every check derives from the report, the policy, and the optional
    changed-file list. It composes the existing release gate and review gate; a
    release is ``allowed`` only when no rule blocks it *and* no human review is
    required. The report is never mutated.
    """

    @staticmethod
    def check(
        report: Mapping[str, Any],
        policy: GuardrailPolicy,
        *,
        changed_files: Sequence[str] = (),
        attempt: int | None = None,
    ) -> dict[str, Any]:
        """Enforce ``policy`` against ``report`` and an optional changed-file set.

        Args:
            report: A produced EvalSurfer report.
            policy: The guardrail policy to enforce.
            changed_files: The release's changed files (e.g. from
                ``git diff --name-only``), matched against
                ``policy.sensitive_paths``.
            attempt: The current fix-attempt number, checked against
                ``policy.max_fix_attempts``.

        Returns:
            ``{"allowed", "decision", "min_decision", "blocks",
            "human_review_required", "sensitive_paths_touched",
            "review_reasons"}``. ``allowed`` is ``True`` only when ``blocks`` is
            empty and no human review is required.

        Raises:
            TypeError: If ``report`` is not a mapping or ``policy`` is not a
                :class:`GuardrailPolicy`.
        """
        if not isinstance(report, Mapping):
            raise TypeError("report must be a mapping")
        if not isinstance(policy, GuardrailPolicy):
            raise TypeError("policy must be a GuardrailPolicy")

        blocks: list[str] = []

        gate = Gate.evaluate(report, policy.min_decision)
        if not gate["passed"]:
            blocks.append(gate["reason"])

        if policy.min_safety is not None:
            safety = Guardrails._pillar_score(report, constants.PILLAR_SAFETY)
            if safety is None:
                blocks.append(
                    f"safety pillar not assessed but policy requires >= {policy.min_safety:g}"
                )
            elif safety < policy.min_safety:
                blocks.append(f"safety {safety:g} below floor {policy.min_safety:g}")

        if policy.coverage_floor is not None:
            coverage = Guardrails._coverage(report)
            if coverage is None:
                blocks.append(
                    f"coverage not reported but policy requires >= {policy.coverage_floor:g}"
                )
            elif coverage < policy.coverage_floor:
                blocks.append(
                    f"coverage {coverage:g} below floor {policy.coverage_floor:g}"
                )

        if policy.block_on_critical_issue and Guardrails._has_critical_issue(report):
            blocks.append("a critical issue is present")

        if (
            policy.max_fix_attempts is not None
            and attempt is not None
            and attempt > policy.max_fix_attempts
        ):
            blocks.append(
                f"attempt {attempt} exceeds cap {policy.max_fix_attempts}"
            )

        touched = Guardrails._sensitive_touched(changed_files, policy.sensitive_paths)
        review = ReviewGate().evaluate(report)
        reasons = list(review["reasons"])
        if touched:
            reasons.append(
                "changed files touch sensitive paths: " + ", ".join(touched)
            )
        human_review_required = bool(touched) or bool(review["needs_human_review"])

        return {
            "allowed": not blocks and not human_review_required,
            "decision": gate["decision"],
            "min_decision": policy.min_decision,
            "blocks": blocks,
            "human_review_required": human_review_required,
            "sensitive_paths_touched": touched,
            "review_reasons": reasons,
        }

    @staticmethod
    def _pillar_score(report: Mapping[str, Any], pillar_id: str) -> float | None:
        """Return a pillar's numeric score, or ``None`` when absent/non-numeric."""
        pillars = report.get("pillars")
        entry = pillars.get(pillar_id) if isinstance(pillars, Mapping) else None
        score = entry.get("score") if isinstance(entry, Mapping) else None
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            return None
        return float(score)

    @staticmethod
    def _coverage(report: Mapping[str, Any]) -> float | None:
        """Return the report's coverage score, or ``None`` when absent/non-numeric."""
        coverage = report.get("coverage")
        score = coverage.get("score") if isinstance(coverage, Mapping) else None
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            return None
        return float(score)

    @staticmethod
    def _has_critical_issue(report: Mapping[str, Any]) -> bool:
        """Report whether any top issue carries ``critical`` severity."""
        issues = report.get("top_issues")
        if not isinstance(issues, Sequence) or isinstance(issues, (str, bytes)):
            return False
        return any(
            isinstance(issue, Mapping)
            and issue.get("severity") == constants.SEVERITY_CRITICAL
            for issue in issues
        )

    @staticmethod
    def _sensitive_touched(
        changed_files: Sequence[str], patterns: Sequence[str]
    ) -> list[str]:
        """Return the changed files matching any sensitive-path pattern.

        Matching is case-insensitive and platform-independent
        (:func:`fnmatch.fnmatchcase` on lower-cased inputs).
        """
        if not patterns:
            return []
        touched: list[str] = []
        for path in changed_files:
            if not isinstance(path, str):
                continue
            lowered = path.lower()
            if any(fnmatchcase(lowered, pattern.lower()) for pattern in patterns):
                if path not in touched:
                    touched.append(path)
        return touched
