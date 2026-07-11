"""Enforcement of a guardrail policy against a produced report.

:class:`Guardrails` composes Core's decision gate
(:class:`~evalsurfer.core.report.Gate`) and Analysis's review gate
(:class:`~evalsurfer.analysis.diagnostics.review_gate.ReviewGate`) and adds the
team-specific rules carried by a
:class:`~evalsurfer.assurance.policy.guardrails.models.GuardrailPolicy`.
Everything here is deterministic, standard-library only, and never mutates the
report.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.core.report import Gate
from evalsurfer.core.scoring import ScoringModel
from evalsurfer.analysis.diagnostics.review_gate import ReviewGate
from evalsurfer.assurance.policy.guardrails.models import GuardrailPolicy

__all__ = ["Guardrails"]


class Guardrails:
    """Enforce a :class:`GuardrailPolicy` against a produced report.

    Stateless: every check derives from the report, the policy, and the optional
    changed-file list. It composes Core's ``Gate`` and Analysis's review gate; a
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
            ValueError: If the report's ``decision`` is missing or unknown, or
                ``policy.min_decision`` is not a known decision -- propagated
                from the Core :class:`~evalsurfer.core.report.gate.Gate`.
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
            safety = Guardrails._category_score(report, constants.CATEGORY_SAFETY)
            if safety is None:
                blocks.append(
                    f"safety category not assessed but policy requires >= {policy.min_safety:g}"
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
    def _category_score(report: Mapping[str, Any], category_id: str) -> float | None:
        """Return a category's numeric score, or ``None`` when absent/non-numeric."""
        entry = ScoringModel.category_block(report, category_id)
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
