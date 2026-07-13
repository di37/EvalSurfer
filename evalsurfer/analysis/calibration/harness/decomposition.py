"""Harness-invariant judgment reliability: the variance decomposition service.

:class:`HarnessInvariance` decomposes a ``target x harness x replication`` grid
of judgments into variance components (two-facet crossed random-effects design,
expected-mean-squares estimators), derives generalizability / dependability
coefficients -- including gate dependability at the pass/fail cut scores -- runs
the D-study ("how many harnesses x replications does a dependable gate need"),
attributes decision flips, and profiles per-criterion harness sensitivity.
Design rationale and prior-art positioning: ``docs/design/harness-invariance.md``.

All methods are static: the calculations carry no per-instance state, make no
model calls, and never mutate their inputs. Standard library only.
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Mapping, Sequence

import evalsurfer.constants as constants
from evalsurfer.analysis.calibration.harness.helpers import (
    build_grid,
    decision_analysis,
    parse_judgments,
    parse_options,
)
from evalsurfer.analysis.calibration.harness.models import (
    DStudyPoint,
    Judgment,
    VarianceComponents,
)
from evalsurfer.analysis.calibration.reference import ReferenceCalibrator

__all__ = ["HarnessInvariance"]

_RANDOM_VS_FIXED_NOTE = (
    "random-facet coefficients generalize to harnesses like these; the "
    "fixed-facet dependability applies only to this exact harness set"
)


class HarnessInvariance:
    """Stateless harness-invariance analysis over a judgment grid.

    All methods are static: the class is a cohesive namespace rather than
    something to instantiate.
    """

    @staticmethod
    def analyze(payload: Mapping[str, Any]) -> dict[str, Any]:
        """Run the full harness-invariance analysis on a judgment payload.

        Args:
            payload: ``{"judgments": [...]}`` plus optional
                ``dependability_target`` (default
                ``constants.DEFAULT_DEPENDABILITY_TARGET``) and
                ``dstudy_max_harnesses`` / ``dstudy_max_replications``. Each
                judgment carries ``target`` / ``harness`` / ``replication`` and
                a ``report`` that is either a full EvalSurfer report or a slim
                ``{"score", "decision", "criteria"}`` record.

        Returns:
            A dict with ``design``, ``grand_mean``, ``variance_components``,
            ``shares``, ``coefficients``, ``dstudy``, ``recommended``,
            ``decisions``, ``criteria``, ``harness_diagnostics``, and ``notes``
            (plain-language caveats: confounded design, the estimated-mean
            optimism of ``dependability_at_cuts``, an unattainable
            recommendation, partial rank-correlation coverage). Undefined
            quantities are ``None`` (never a fabricated 0.0 or 1.0): with zero
            *total* variance the shares are ``None``; with zero *target*
            variance the coefficients, D-study, and recommendation are ``None``
            (shares may still attribute the judge-side variance); and with one
            replication per cell the interaction and replication components are
            confounded into a ``residual``.

        Raises:
            TypeError: If the payload or a judgment is not a mapping.
            ValueError: On an unknown payload key, invalid option, invalid
                judgment field, duplicate key, or an incomplete / unbalanced
                grid (the offending cells are named).
        """
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping")
        target_level, max_harnesses, max_replications = parse_options(payload)
        judgments = parse_judgments(payload)
        targets, harnesses, n_replications, cells = build_grid(judgments)

        score_cells = {
            cell: [judgment.score for judgment in entries]
            for cell, entries in cells.items()
        }
        components = HarnessInvariance.decompose(score_cells)
        points = HarnessInvariance.dstudy(
            components,
            max_harnesses=max_harnesses,
            max_replications=max_replications,
        )
        recommended = HarnessInvariance._recommended(points, target_level)
        diagnostics = HarnessInvariance._diagnostics(
            components, targets, harnesses, cells
        )

        return {
            "design": {
                "targets": len(targets),
                "harnesses": len(harnesses),
                "replications": n_replications,
                "balanced": True,
                "confounded": components.confounded,
            },
            "grand_mean": round(components.grand_mean, constants.SCORE_PRECISION),
            "variance_components": components.to_dict(),
            "shares": HarnessInvariance._shares(components),
            "coefficients": HarnessInvariance._coefficients(components),
            "dstudy": [point.to_dict() for point in points],
            "recommended": recommended,
            "decisions": decision_analysis(targets, harnesses, cells),
            "criteria": HarnessInvariance._criteria_profiles(targets, harnesses, cells),
            "harness_diagnostics": diagnostics,
            "notes": HarnessInvariance._notes(
                components, recommended, target_level, diagnostics
            ),
        }

    @staticmethod
    def decompose(
        cells: Mapping[tuple[str, str], Sequence[float]],
    ) -> VarianceComponents:
        """Estimate the variance components of a complete, balanced grid.

        Two-facet crossed random-effects ANOVA via expected mean squares. With
        ``n_r >= 2`` replications per cell the four components are separable;
        with ``n_r = 1`` the interaction and replication noise are confounded
        into a single residual (two-way ANOVA without replication). Negative
        estimates are clamped to zero and named in ``clamped``.

        Args:
            cells: ``(target, harness) -> scores per replication``; every
                target/harness combination present, all cells the same size.

        Returns:
            The estimated :class:`VarianceComponents`.

        Raises:
            ValueError: If the grid is empty, incomplete, or unbalanced.
        """
        targets = sorted({target for target, _ in cells})
        harnesses = sorted({harness for _, harness in cells})
        n_targets, n_harnesses = len(targets), len(harnesses)
        if n_targets < 2 or n_harnesses < 2:
            raise ValueError("decompose requires at least 2 targets and 2 harnesses")
        missing = [
            (target, harness)
            for target in targets
            for harness in harnesses
            if (target, harness) not in cells
        ]
        if missing:
            raise ValueError(f"incomplete grid: missing cells {missing}")
        sizes = {len(scores) for scores in cells.values()}
        if len(sizes) != 1 or not min(sizes):
            raise ValueError("all cells must contain the same non-zero number of scores")
        n_replications = sizes.pop()

        cell_means = {cell: mean(scores) for cell, scores in cells.items()}
        target_means = {
            target: mean(cell_means[(target, harness)] for harness in harnesses)
            for target in targets
        }
        harness_means = {
            harness: mean(cell_means[(target, harness)] for target in targets)
            for harness in harnesses
        }
        grand = mean(cell_means.values())

        ss_target = (
            n_harnesses
            * n_replications
            * sum((target_means[target] - grand) ** 2 for target in targets)
        )
        ss_harness = (
            n_targets
            * n_replications
            * sum((harness_means[harness] - grand) ** 2 for harness in harnesses)
        )
        interaction_residuals = sum(
            (
                cell_means[(target, harness)]
                - target_means[target]
                - harness_means[harness]
                + grand
            )
            ** 2
            for target in targets
            for harness in harnesses
        )

        ms_target = ss_target / (n_targets - 1)
        ms_harness = ss_harness / (n_harnesses - 1)
        ms_cross = (
            n_replications
            * interaction_residuals
            / ((n_targets - 1) * (n_harnesses - 1))
        )

        clamped: list[str] = []

        def _clamp(value: float, facet: str) -> float:
            if value < 0:
                clamped.append(facet)
                return 0.0
            return value

        if n_replications >= 2:
            ss_error = sum(
                (score - cell_means[cell]) ** 2
                for cell, scores in cells.items()
                for score in scores
            )
            sigma_error = ss_error / (n_targets * n_harnesses * (n_replications - 1))
            sigma_target = _clamp(
                (ms_target - ms_cross) / (n_harnesses * n_replications),
                constants.FACET_TARGET,
            )
            sigma_harness = _clamp(
                (ms_harness - ms_cross) / (n_targets * n_replications),
                constants.FACET_HARNESS,
            )
            sigma_interaction = _clamp(
                (ms_cross - sigma_error) / n_replications, constants.FACET_INTERACTION
            )
            return VarianceComponents(
                target=sigma_target,
                harness=sigma_harness,
                interaction=sigma_interaction,
                replication=sigma_error,
                residual=None,
                clamped=tuple(clamped),
                confounded=False,
                grand_mean=grand,
                n_targets=n_targets,
                n_harnesses=n_harnesses,
                n_replications=n_replications,
            )

        # n_r = 1: interaction and replication noise are confounded (residual).
        sigma_residual = ms_cross  # ms_cross reduces to the residual mean square
        sigma_target = _clamp(
            (ms_target - sigma_residual) / n_harnesses, constants.FACET_TARGET
        )
        sigma_harness = _clamp(
            (ms_harness - sigma_residual) / n_targets, constants.FACET_HARNESS
        )
        return VarianceComponents(
            target=sigma_target,
            harness=sigma_harness,
            interaction=None,
            replication=None,
            residual=sigma_residual,
            clamped=tuple(clamped),
            confounded=True,
            grand_mean=grand,
            n_targets=n_targets,
            n_harnesses=n_harnesses,
            n_replications=1,
        )

    @staticmethod
    def dstudy(
        components: VarianceComponents,
        *,
        max_harnesses: int = constants.DSTUDY_MAX_HARNESSES,
        max_replications: int = constants.DSTUDY_MAX_REPLICATIONS,
    ) -> list[DStudyPoint]:
        """Project coefficients over hypothetical ``harnesses x replications`` designs.

        Args:
            components: The estimated variance components.
            max_harnesses: The largest harness count to project.
            max_replications: The largest replication count to project; ignored
                in confounded mode (no separable replication term).

        Returns:
            The grid of :class:`DStudyPoint`s (harness-major order), or an empty
            list when there is no target variance (coefficients are undefined).
        """
        if components.target <= 0:
            return []
        replication_axis: tuple[int | None, ...] = (
            (None,) if components.confounded else tuple(range(1, max_replications + 1))
        )
        points = []
        for n_harnesses in range(1, max_harnesses + 1):
            for n_replications in replication_axis:
                relative = components.relative_error(n_harnesses, n_replications)
                absolute = components.absolute_error(n_harnesses, n_replications)
                points.append(
                    DStudyPoint(
                        harnesses=n_harnesses,
                        replications=n_replications,
                        generalizability=components.target / (components.target + relative),
                        dependability=components.target / (components.target + absolute),
                    )
                )
        return points

    # ------------------------------------------------------------------ #
    # Result assembly
    # ------------------------------------------------------------------ #

    @staticmethod
    def _shares(components: VarianceComponents) -> dict[str, float] | None:
        """Variance shares per facet, or ``None`` when total variance is zero."""
        total = components.total()
        if total <= 0:
            return None
        digits = constants.SHARE_PRECISION
        if components.confounded:
            return {
                constants.FACET_TARGET: round(components.target / total, digits),
                constants.FACET_HARNESS: round(components.harness / total, digits),
                constants.FACET_RESIDUAL: round((components.residual or 0.0) / total, digits),
            }
        return {
            constants.FACET_TARGET: round(components.target / total, digits),
            constants.FACET_HARNESS: round(components.harness / total, digits),
            constants.FACET_INTERACTION: round((components.interaction or 0.0) / total, digits),
            constants.FACET_REPLICATION: round((components.replication or 0.0) / total, digits),
        }

    @staticmethod
    def _coefficients(components: VarianceComponents) -> dict[str, Any] | None:
        """Observed-design coefficients, or ``None`` without target variance."""
        if components.target <= 0:
            return None
        digits = constants.SHARE_PRECISION
        n_harnesses, n_replications = components.n_harnesses, components.n_replications
        relative = components.relative_error(n_harnesses, n_replications)
        absolute = components.absolute_error(n_harnesses, n_replications)

        def _phi_at(cut: float) -> float:
            # Brennan-Kane criterion-referenced dependability at an absolute cut.
            offset = (components.grand_mean - cut) ** 2
            return (components.target + offset) / (components.target + offset + absolute)

        icc_2_1 = None
        if components.confounded:
            icc_2_1 = round(
                components.target
                / (components.target + components.harness + (components.residual or 0.0)),
                digits,
            )
        return {
            "generalizability": round(
                components.target / (components.target + relative), digits
            ),
            "dependability": round(
                components.target / (components.target + absolute), digits
            ),
            "dependability_at_cuts": {
                str(constants.FAIL_OVERALL_THRESHOLD): round(
                    _phi_at(constants.FAIL_OVERALL_THRESHOLD), digits
                ),
                str(constants.PASS_OVERALL_THRESHOLD): round(
                    _phi_at(constants.PASS_OVERALL_THRESHOLD), digits
                ),
            },
            "icc_2_1": icc_2_1,
        }

    @staticmethod
    def _recommended(
        points: Sequence[DStudyPoint], target_level: float
    ) -> dict[str, Any] | None:
        """The cheapest D-study point reaching the dependability target.

        Cost is total runs (``harnesses * replications``); ties break to fewer
        harnesses. ``None`` when no projected design reaches the target.
        """
        qualifying = [
            point for point in points if point.dependability >= target_level
        ]
        if not qualifying:
            return None
        best = min(
            qualifying,
            key=lambda point: (
                point.harnesses * (point.replications or 1),
                point.harnesses,
            ),
        )
        return {
            "harnesses": best.harnesses,
            "replications": best.replications,
            "dependability": round(best.dependability, constants.SHARE_PRECISION),
            "target": target_level,
        }

    @staticmethod
    def _criteria_profiles(
        targets: Sequence[str],
        harnesses: Sequence[str],
        cells: Mapping[tuple[str, str], Sequence[Judgment]],
    ) -> list[dict[str, Any]]:
        """Per-criterion invariance profiles over each criterion's complete subgrid.

        A criterion is profiled over the targets where it was assessed in every
        judgment; targets partially assessed for it are counted in
        ``dropped_targets``. Fewer than two surviving targets -> ``skipped``
        with the reason. ``harness_sensitive`` is ``True`` when the raw
        harness-linked share (harness + interaction) strictly exceeds
        ``constants.HARNESS_SENSITIVITY_SHARE``; it is ``None`` when the
        attribution is undefined (confounded design or zero variance).
        """
        criterion_ids = sorted(
            {
                criterion_id
                for cell in cells.values()
                for judgment in cell
                for criterion_id, score in (judgment.criteria or {}).items()
                if score is not None
            }
        )
        profiles: list[dict[str, Any]] = []
        for criterion_id in criterion_ids:
            surviving = [
                target
                for target in targets
                if all(
                    isinstance((judgment.criteria or {}).get(criterion_id), int)
                    for harness in harnesses
                    for judgment in cells[(target, harness)]
                )
            ]
            dropped = len(targets) - len(surviving)
            if len(surviving) < 2:
                profiles.append(
                    {
                        "id": criterion_id,
                        "skipped": (
                            f"only {len(surviving)} target(s) with complete "
                            "assessments (need >= 2)"
                        ),
                        "dropped_targets": dropped,
                    }
                )
                continue

            score_cells = {
                (target, harness): [
                    float((judgment.criteria or {})[criterion_id])  # type: ignore[arg-type]
                    for judgment in cells[(target, harness)]
                ]
                for target in surviving
                for harness in harnesses
            }
            components = HarnessInvariance.decompose(score_cells)
            total = components.total()
            sensitive: bool | None = None
            if not components.confounded and total > 0:
                harness_linked = components.harness + (components.interaction or 0.0)
                sensitive = harness_linked / total > constants.HARNESS_SENSITIVITY_SHARE
            dependability = None
            if components.target > 0:
                absolute = components.absolute_error(
                    components.n_harnesses, components.n_replications
                )
                dependability = round(
                    components.target / (components.target + absolute),
                    constants.SHARE_PRECISION,
                )
            profiles.append(
                {
                    "id": criterion_id,
                    "shares": HarnessInvariance._shares(components),
                    "dependability": dependability,
                    "harness_sensitive": sensitive,
                    "dropped_targets": dropped,
                }
            )
        return profiles

    @staticmethod
    def _diagnostics(
        components: VarianceComponents,
        targets: Sequence[str],
        harnesses: Sequence[str],
        cells: Mapping[tuple[str, str], Sequence[Judgment]],
    ) -> dict[str, Any]:
        """Facet diagnostics: severity, rank stability, and the fixed-facet view."""
        per_harness_mean = {
            harness: round(
                mean(
                    judgment.score
                    for target in targets
                    for judgment in cells[(target, harness)]
                ),
                constants.SCORE_PRECISION,
            )
            for harness in harnesses
        }

        vectors = {
            harness: [
                mean(judgment.score for judgment in cells[(target, harness)])
                for target in targets
            ]
            for harness in harnesses
        }
        total_pairs = len(harnesses) * (len(harnesses) - 1) // 2
        correlations = [
            rho
            for index, first in enumerate(harnesses)
            for second in harnesses[index + 1 :]
            if (rho := ReferenceCalibrator.rank_correlation(vectors[first], vectors[second]))
            is not None
        ]
        mean_rank_correlation = (
            round(mean(correlations), constants.SHARE_PRECISION) if correlations else None
        )

        fixed = None
        if not components.confounded:
            # Fixed-facet view: the harness main effect averages out and the
            # interaction folds into the universe score (sigma2_t* = t + th/n_h).
            fixed_target = components.target + (
                (components.interaction or 0.0) / components.n_harnesses
            )
            error = (components.replication or 0.0) / (
                components.n_harnesses * components.n_replications
            )
            if fixed_target > 0:
                fixed = round(fixed_target / (fixed_target + error), constants.SHARE_PRECISION)

        return {
            "per_harness_mean": per_harness_mean,
            "mean_rank_correlation": mean_rank_correlation,
            "rank_correlation_pairs": {
                "defined": len(correlations),
                "total": total_pairs,
            },
            "fixed_facet_dependability": fixed,
            "note": _RANDOM_VS_FIXED_NOTE,
        }

    @staticmethod
    def _notes(
        components: VarianceComponents,
        recommended: Mapping[str, Any] | None,
        target_level: float,
        diagnostics: Mapping[str, Any],
    ) -> list[str]:
        """Plain-language caveats about the result, for humans and agent consumers.

        One general mechanism carries every explanation the design contract
        promises: the confounded-design warning, the estimated-mean optimism of
        ``dependability_at_cuts``, the reason a recommendation is absent, and
        partial rank-correlation coverage.
        """
        notes: list[str] = []
        if components.confounded:
            notes.append(
                "one replication per cell: interaction and replication noise "
                "are confounded into 'residual'; run >= 2 replications per "
                "(target, harness) to separate harness disagreement from run noise"
            )
        if components.target <= 0:
            notes.append(
                "no target variance: coefficients, D-study, and recommendation "
                "are undefined; any shares reflect only judge-side variance"
            )
        else:
            notes.append(
                "dependability_at_cuts uses the estimated grand mean and is "
                "slightly optimistic in small samples (no unbiased correction "
                "applied)"
            )
            if recommended is None:
                notes.append(
                    "no projected design within the D-study grid reaches the "
                    f"dependability target {target_level:g}; raise "
                    "dstudy_max_harnesses / dstudy_max_replications, collect "
                    "more replications, or lower the target"
                )
        pairs = diagnostics["rank_correlation_pairs"]
        if pairs["defined"] < pairs["total"]:
            notes.append(
                "rank correlation is undefined for "
                f"{pairs['total'] - pairs['defined']} of {pairs['total']} "
                "harness pair(s) (fewer than 3 targets, or constant per-target "
                "means); mean_rank_correlation covers only the defined pairs"
            )
        return notes
