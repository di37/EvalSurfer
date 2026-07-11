"""Industry weighting profiles for EvalSurfer.

The default overall score weights the three categories equally (see
:meth:`evalsurfer.core.scoring.ScoringModel.overall_score`). Different industries care about the
categories differently: a healthcare deployment weighs safety far above raw quality,
a game backend cares most about operational latency. :class:`IndustryProfiler`
resolves a named preset from :data:`constants.INDUSTRY_PROFILES` (or a custom
weight mapping) once at construction and applies it to a set of category scores.

The weights are *renormalised* over whichever categories actually have a score, so a
profile still works when a category was not assessed (its score is ``None``). Pure
behaviour, standard library only, no model calls -- this stays in step with the
rest of the deterministic scoring layer.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

import evalsurfer.constants as constants

__all__ = ["IndustryProfiler"]


def _is_number(value: Any) -> bool:
    """Report whether a value is a real int/float (booleans excluded).

    Args:
        value: The value to test.

    Returns:
        ``True`` for a non-boolean ``int`` or ``float``, ``False`` otherwise.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class IndustryProfiler:
    """Weight the three category scores into one overall score by industry.

    The default profile weights the categories equally; named industry presets from
    :data:`constants.INDUSTRY_PROFILES` (and custom weight mappings) tilt the
    balance -- healthcare toward safety, gaming toward operational, and so on. The
    resolved weights are held as instance state and reused across calls.
    """

    def __init__(
        self, profile: str | Mapping[str, float] = constants.PROFILE_DEFAULT
    ) -> None:
        """Resolve a profile name or custom weight mapping into category weights.

        Args:
            profile: A preset name from :data:`constants.INDUSTRY_PROFILES`, or a
                mapping of canonical category names to non-negative finite weights.
                Defaults to :data:`constants.PROFILE_DEFAULT`. The mapping is
                copied, never retained or mutated.

        Raises:
            TypeError: If ``profile`` is neither a name nor a mapping, or a custom
                weight is not a real number.
            ValueError: If the name is unknown, a category key is not canonical, or
                a custom weight is negative or non-finite.
        """
        self.weights: dict[str, float] = self._resolve_weights(profile)

    @classmethod
    def available_profiles(cls) -> tuple[str, ...]:
        """Return the preset profile names in sorted order.

        Returns:
            The names of every preset in :data:`constants.INDUSTRY_PROFILES`.
        """
        return tuple(sorted(constants.INDUSTRY_PROFILES))

    def weighted_overall(
        self, category_scores: Mapping[str, float | None]
    ) -> float | None:
        """Weight the category scores by this profile into one overall score.

        The weights are renormalised over the categories that actually carry a
        score, so a missing (``None``) category drops out of both the numerator and
        the denominator.

        Args:
            category_scores: Mapping of canonical category names to a 0-10 score or
                ``None`` (not assessed). Unknown keys are ignored; the mapping is
                never mutated.

        Returns:
            The weighted mean rounded to ``constants.SCORE_PRECISION`` decimals,
            or ``None`` when no category has a score.

        Raises:
            TypeError: If ``category_scores`` is not a mapping, or a score is not a
                real number.
            ValueError: If a score is non-finite, or the profile assigns zero
                weight to every scored category.
        """
        scored = self._scored_categories(category_scores)
        if not scored:
            return None

        total_weight = sum(self.weights.get(category, 0.0) for category in scored)
        if total_weight <= 0:
            raise ValueError("profile assigns zero weight to all scored categories")

        weighted_sum = sum(
            self.weights.get(category, 0.0) * score for category, score in scored.items()
        )
        return round(weighted_sum / total_weight, constants.SCORE_PRECISION)

    # ----------------------------------------------------------------- #
    # Internal validation helpers (stateless).
    # ----------------------------------------------------------------- #
    @classmethod
    def _resolve_weights(
        cls, profile: str | Mapping[str, float]
    ) -> dict[str, float]:
        """Resolve a profile name or custom mapping to a fresh weights dict.

        Args:
            profile: A preset name or a custom weight mapping.

        Returns:
            A new dict of category weights.

        Raises:
            TypeError: If ``profile`` is neither a name nor a mapping.
            ValueError: If the name is unknown or a custom weight is invalid.
        """
        if isinstance(profile, str):
            preset = constants.INDUSTRY_PROFILES.get(profile)
            if preset is None:
                raise ValueError(
                    f"unknown profile {profile!r}; "
                    f"choose from {list(cls.available_profiles())}"
                )
            return dict(preset)
        if isinstance(profile, Mapping):
            return cls._validate_weights(profile)
        raise TypeError("profile must be a profile name or a weights mapping")

    @classmethod
    def _validate_weights(cls, weights: Mapping[str, Any]) -> dict[str, float]:
        """Validate a custom weight mapping into a new, clean dict.

        Args:
            weights: Mapping of canonical category names to weights.

        Returns:
            A new dict with every weight validated and coerced to ``float``.

        Raises:
            TypeError: If a weight is not a real number.
            ValueError: If a key is not a canonical category, or a weight is
                negative or non-finite.
        """
        validated: dict[str, float] = {}
        for category, value in weights.items():
            if category not in constants.CATEGORIES:
                raise ValueError(
                    f"unknown category {category!r}; "
                    f"expected one of {list(constants.CATEGORIES)}"
                )
            validated[category] = cls._validate_weight(category, value)
        return validated

    @staticmethod
    def _validate_weight(category: str, value: Any) -> float:
        """Validate a single non-negative finite category weight.

        Args:
            category: The category the weight belongs to (for error messages).
            value: The weight to validate.

        Returns:
            The weight as a ``float``.

        Raises:
            TypeError: If ``value`` is not a real number.
            ValueError: If ``value`` is non-finite or negative.
        """
        if not _is_number(value):
            raise TypeError(f"weight for {category!r} must be a number")
        if not isfinite(value):
            raise ValueError(f"weight for {category!r} must be finite")
        if value < 0:
            raise ValueError(f"weight for {category!r} must be non-negative")
        return float(value)

    @classmethod
    def _scored_categories(
        cls, category_scores: Mapping[str, float | None]
    ) -> dict[str, float]:
        """Collect the canonical categories carrying a non-``None`` numeric score.

        Args:
            category_scores: Mapping of category names to scores or ``None``.

        Returns:
            A new dict of the canonical categories that have a validated score.

        Raises:
            TypeError: If ``category_scores`` is not a mapping, or a score is not a
                real number.
            ValueError: If a score is non-finite.
        """
        if not isinstance(category_scores, Mapping):
            raise TypeError("category_scores must be a mapping")

        scored: dict[str, float] = {}
        for category in constants.CATEGORIES:
            value = category_scores.get(category)
            if value is None:
                continue
            scored[category] = cls._validate_score(category, value)
        return scored

    @staticmethod
    def _validate_score(category: str, value: Any) -> float:
        """Validate a single finite category score.

        Args:
            category: The category the score belongs to (for error messages).
            value: The score to validate.

        Returns:
            The score as a ``float``.

        Raises:
            TypeError: If ``value`` is not a real number.
            ValueError: If ``value`` is non-finite.
        """
        if not _is_number(value):
            raise TypeError(f"score for {category!r} must be a number or None")
        if not isfinite(value):
            raise ValueError(f"score for {category!r} must be finite")
        return float(value)
