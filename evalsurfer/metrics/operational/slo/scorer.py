"""The operational SLO scorer.

:class:`OperationalScorer` turns measured operational metrics into the 1-5
operational criterion scores the rubric expects by comparing each measured metric
against an SLO target. The SLO targets are the only configurable input, so they
are instance state set in ``__init__``; everything else is pure. The value
objects it produces live in :mod:`evalsurfer.metrics.operational.slo.models`.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.core.planner import Criterion, EvaluationPlanner
from evalsurfer.core.scoring import ScoringModel
from evalsurfer.metrics.operational.metrics import (
    OperationalMetrics,
    OperationalSummary,
    Pricing,
    RequestTrace,
)
from evalsurfer.metrics.operational.slo.models import CriterionScore, OperationalScore


class OperationalScorer:
    """Score operational criteria by comparing measured metrics to an SLO.

    Configurable: the SLO targets are instance state, set once in ``__init__``.
    The scoring itself is pure and standard-library-only -- it never mutates its
    inputs and makes no model calls.
    """

    #: Operational criteria (id/name), drawn once from the planner catalog in
    #: rubric order.
    OPERATIONAL_CRITERIA: tuple[Criterion, ...] = tuple(
        criterion
        for criterion in EvaluationPlanner.CRITERIA
        if criterion.category == constants.CATEGORY_OPERATIONAL
    )

    def __init__(self, slo: Mapping[str, float] | None = None) -> None:
        """Validate and store the SLO targets for this scorer.

        Args:
            slo: Target values keyed by :data:`constants.SLO_FIELDS`
                (e.g. ``{"p95_latency_ms": 1000}``). ``None`` means no targets
                are configured, so every criterion is left unscored.

        Raises:
            TypeError: If ``slo`` is not a mapping or a target is not a number.
            ValueError: If a key is not an SLO field or a target is not finite.
        """
        self.slo = self._normalize_slo(slo)

    @staticmethod
    def _normalize_slo(slo: Mapping[str, float] | None) -> dict[str, float]:
        """Validate the SLO mapping and return an owned copy.

        Args:
            slo: The raw SLO mapping supplied to the constructor, or ``None``.

        Returns:
            A new ``dict`` of finite ``float`` targets keyed by SLO field; empty
            when ``slo`` is ``None``.

        Raises:
            TypeError: If ``slo`` is not a mapping or a target is not a number.
            ValueError: If a key is not an SLO field or a target is not finite.
        """
        if slo is None:
            return {}
        if not isinstance(slo, Mapping):
            raise TypeError("slo must be a mapping or None")

        normalized: dict[str, float] = {}
        for field, target in slo.items():
            if field not in constants.SLO_FIELDS:
                raise ValueError(
                    f"unknown SLO field {field!r}; expected one of {constants.SLO_FIELDS}"
                )
            if isinstance(target, bool) or not isinstance(target, (int, float)):
                raise TypeError(f"SLO target for {field!r} must be a number")
            if not isfinite(target):
                raise ValueError(f"SLO target for {field!r} must be finite")
            normalized[field] = float(target)
        return normalized

    @staticmethod
    def score_ratio(measured: float | None, target: float | None) -> int | None:
        """Score a lower-is-better metric against its SLO target.

        Args:
            measured: The observed metric value, or ``None`` when unavailable.
            target: The SLO target, or ``None`` when no target is configured.

        Returns:
            The 1-5 score for the first band in
            :data:`constants.SLO_SCORE_BANDS` whose ``max_ratio`` is at least the
            ``measured / target`` ratio, ``constants.CRITERION_MIN_SCORE`` when
            the ratio exceeds every band, or ``None`` when ``measured`` or
            ``target`` is ``None`` or ``target`` is not positive.
        """
        if measured is None or target is None or target <= 0:
            return None

        ratio = measured / target
        for max_ratio, score in constants.SLO_SCORE_BANDS:
            if max_ratio >= ratio:
                return score
        return constants.CRITERION_MIN_SCORE

    def score(self, traces_payload: Any) -> dict[str, Any]:
        """Auto-score the operational category from request traces against the SLO.

        Args:
            traces_payload: Either a list of trace mappings, or a mapping of the
                form ``{"traces": [...], "pricing": {...}}`` where ``pricing`` is
                optional. Traces are parsed with
                :meth:`RequestTrace.from_mapping` and summarized with
                :meth:`OperationalMetrics.summarize`.

        Returns:
            ``{"criteria": [{"id", "name", "score", "evidence"}, ...],
            "category_score": float | None}``. ``token_efficiency`` has no SLO and
            is always unscored; any criterion whose SLO field is absent, or whose
            metric could not be measured, scores ``None``.

        Raises:
            TypeError: If ``traces_payload`` is neither a list nor a mapping.
            ValueError: If a mapping payload lacks a ``traces`` list or a trace
                or pricing entry is malformed.
        """
        traces, pricing = self._parse_payload(traces_payload)
        summary = OperationalMetrics.summarize(traces, pricing=pricing)
        measured = self._measured_metrics(summary, traces)

        criteria = tuple(
            self._score_criterion(criterion, measured)
            for criterion in self.OPERATIONAL_CRITERIA
        )
        category_score = ScoringModel.category_score(
            [criterion.score for criterion in criteria]
        )
        return OperationalScore(criteria=criteria, category_score=category_score).to_dict()

    @staticmethod
    def _parse_payload(
        payload: Any,
    ) -> tuple[list[RequestTrace], Pricing | None]:
        """Split a trace payload into parsed traces and optional pricing.

        Args:
            payload: A list of trace mappings, or a mapping with a ``traces``
                list and optional ``pricing`` mapping.

        Returns:
            A ``(traces, pricing)`` tuple; ``pricing`` is ``None`` for list
            payloads or when no pricing is supplied.

        Raises:
            TypeError: If ``payload`` is neither a list nor a mapping.
            ValueError: If a mapping payload lacks a ``traces`` list or a trace
                or pricing entry is malformed.
        """
        if isinstance(payload, Mapping):
            trace_payloads = payload.get("traces")
            if not isinstance(trace_payloads, list):
                raise ValueError("payload mapping must contain a 'traces' list")
            pricing = OperationalScorer._parse_pricing(payload.get("pricing"))
        elif isinstance(payload, list):
            trace_payloads = payload
            pricing = None
        else:
            raise TypeError("traces_payload must be a list or a mapping")

        traces = [RequestTrace.from_mapping(item) for item in trace_payloads]
        return traces, pricing

    @staticmethod
    def _parse_pricing(pricing: Any) -> Pricing | None:
        """Build a :class:`Pricing` from a payload's ``pricing`` mapping.

        Args:
            pricing: The raw ``pricing`` value, or ``None`` when absent.

        Returns:
            The parsed :class:`Pricing`, or ``None`` when ``pricing`` is ``None``.

        Raises:
            TypeError: If ``pricing`` is present but not a mapping.
            ValueError: If a required pricing field is missing or not a number.
        """
        if pricing is None:
            return None
        if not isinstance(pricing, Mapping):
            raise TypeError("pricing must be a mapping")

        try:
            return Pricing(
                input_per_million=float(pricing["input_per_million"]),
                output_per_million=float(pricing["output_per_million"]),
            )
        except KeyError as exc:
            raise ValueError(f"pricing is missing required field: {exc}") from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(f"pricing values must be numbers: {exc}") from exc

    @staticmethod
    def _measured_metrics(
        summary: OperationalSummary,
        traces: Sequence[RequestTrace],
    ) -> dict[str, float | None]:
        """Map each SLO-backed operational criterion to its measured metric.

        Args:
            summary: The aggregated operational summary for the traces.
            traces: The parsed request traces (for the under-load grouping).

        Returns:
            A mapping of criterion id to its measured value; a value is ``None``
            when the metric could not be computed. ``token_efficiency`` is
            deliberately absent because it carries no SLO.
        """
        latency_p95 = summary.latency.p95_ms if summary.latency is not None else None
        ttft_p95 = summary.ttft.p95_ms if summary.ttft is not None else None

        load_groups = OperationalMetrics.latency_under_load(traces)
        if load_groups:
            latency_under_load = max(stats.p95_ms for stats in load_groups.values())
        else:
            latency_under_load = latency_p95

        return {
            "end_to_end_latency": latency_p95,
            "time_to_first_token": ttft_p95,
            "cost_per_request": summary.average_cost_usd,
            "error_failure_rate": summary.failure_rate,
            "latency_under_load": latency_under_load,
            "inter_token_latency": summary.itl.p95_ms if summary.itl is not None else None,
            "output_throughput": summary.average_tokens_per_second,
            "tail_latency": summary.tail_latency_ratio,
            "cost_per_million_tokens": summary.cost_per_million_tokens,
        }

    def _score_criterion(
        self,
        criterion: Criterion,
        measured: Mapping[str, float | None],
    ) -> CriterionScore:
        """Score a single operational criterion against its SLO target.

        Args:
            criterion: The operational criterion to score.
            measured: The measured metric per criterion id.

        Returns:
            The :class:`CriterionScore`; ``score`` is ``None`` when the criterion
            has no SLO field, the field is not in the configured SLO, or the
            metric could not be measured.
        """
        field = constants.OPERATIONAL_CRITERION_SLO.get(criterion.id)
        value = measured.get(criterion.id)
        target = self.slo.get(field) if field is not None else None
        higher_is_better = criterion.id in constants.HIGHER_IS_BETTER_OPERATIONAL_CRITERIA
        if field is None:
            score = None
        elif higher_is_better:
            # Throughput: measured >= target is best, so invert the ratio.
            score = self.score_ratio(target, value)
        else:
            score = self.score_ratio(value, target)
        evidence = self._evidence(
            criterion.name, field, value, target, score, higher_is_better
        )
        return CriterionScore(
            id=criterion.id,
            name=criterion.name,
            score=score,
            evidence=evidence,
        )

    @classmethod
    def _evidence(
        cls,
        name: str,
        field: str | None,
        measured: float | None,
        target: float | None,
        score: int | None,
        higher_is_better: bool = False,
    ) -> str:
        """Describe the measured-versus-target comparison for a criterion.

        Args:
            name: The human-readable criterion name.
            field: The SLO field the criterion maps to, or ``None`` when it has
                no SLO.
            measured: The measured metric value, or ``None``.
            target: The SLO target value, or ``None``.
            score: The resolved 1-5 score, or ``None`` when not scored.
            higher_is_better: Whether a higher measured value is better (a
                throughput target is a minimum, not a ceiling).

        Returns:
            A human-readable evidence string stating measured versus target.
        """
        if field is None:
            return f"{name}: no SLO defined for this criterion; not scored."

        measured_str = cls._format_measurement(measured)
        target_str = cls._format_measurement(target)
        if score is None:
            if measured is None:
                return (
                    f"{name}: no measured value available; "
                    f"SLO target {target_str} for {field!r}; not scored."
                )
            return (
                f"{name}: measured {measured_str}; "
                f"no valid SLO target for {field!r} (target {target_str}); not scored."
            )

        if higher_is_better:
            ratio = round(target / measured, constants.SHARE_PRECISION)
            comparison = f"vs SLO minimum {target_str}"
        else:
            ratio = round(measured / target, constants.SHARE_PRECISION)
            comparison = f"vs SLO target {target_str}"
        return (
            f"{name}: measured {measured_str} {comparison} "
            f"for {field!r} (ratio {ratio:g}); scored {score}/{constants.CRITERION_MAX_SCORE}."
        )

    @staticmethod
    def _format_measurement(value: float | None) -> str:
        """Format a metric value for evidence text.

        Args:
            value: The value to format, or ``None`` when unavailable.

        Returns:
            ``"n/a"`` when ``value`` is ``None``, otherwise the value rounded to
            ``constants.SHARE_PRECISION`` decimals in compact form.
        """
        if value is None:
            return "n/a"
        return f"{round(float(value), constants.SHARE_PRECISION):g}"
