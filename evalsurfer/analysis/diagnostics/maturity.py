"""AI application maturity model for EvalSurfer.

Classify an evaluation target onto a six-level maturity ladder, from a bare
prompt app up to a self-improving system, using the same :class:`Signals` the
planner already infers. The level is the highest stage the evidence supports:

* 1 Prompt App           -- a prompt/LLM with no retrieval, tools, or agency
* 2 Prompt + RAG         -- retrieved context grounds the answer
* 3 Agent                -- the system calls tools to take actions
* 4 Multi-Agent          -- multiple coordinated agents
* 5 Production AI System -- an agentic system with operational telemetry
* 6 Self-Improving       -- a feedback loop improves the system over time

The ladder's names, drivers, and next-step advice all come from
:mod:`constants`; this module owns only the gating logic. :class:`MaturityClassifier`
is a deterministic diagnostic layer: it runs with no model calls and no
third-party dependencies, and it never mutates its inputs.
"""

from __future__ import annotations

from dataclasses import dataclass

import evalsurfer.constants as constants
from evalsurfer.core.planner import Signals

__all__ = ["MaturityLevel", "MaturityClassifier"]

# Keyword-flag names (not planner signals): supplied by the caller and echoed in
# the rationale text and validation messages. They are not part of
# :data:`constants.SIGNALS`, so they are named locally.
_FLAG_MULTI_AGENT = "multi_agent"
_FLAG_SELF_IMPROVING = "self_improving"

# One rung up the ladder: the step between two adjacent contiguous levels.
_ONE_RUNG = 1


@dataclass(frozen=True)
class MaturityLevel:
    """A named stage on the maturity ladder.

    Attributes:
        level: The rung number, between ``MIN_MATURITY_LEVEL`` and
            ``MAX_MATURITY_LEVEL`` inclusive.
        name: The framework name for the stage.
        driver: Why the evidence justifies this stage, phrased for the
            ``rationale`` field.
        recommendation: What to add to reach the next stage; empty at the top of
            the ladder.
    """

    level: int
    name: str
    driver: str
    recommendation: str


class MaturityClassifier:
    """Classify an evaluation target onto the six-level maturity ladder.

    Stateless: the ladder is a class attribute built once from :mod:`constants`,
    and every method derives a result without per-instance state, so the class is
    a cohesive namespace rather than something to instantiate.
    """

    #: The canonical ladder, built from the central maturity constants in rung
    #: order (``MIN_MATURITY_LEVEL`` .. ``MAX_MATURITY_LEVEL``).
    LEVELS: tuple[MaturityLevel, ...] = tuple(
        MaturityLevel(
            level=level,
            name=constants.MATURITY_LEVEL_NAMES[level],
            driver=constants.MATURITY_LEVEL_DRIVERS[level],
            recommendation=constants.MATURITY_LEVEL_RECOMMENDATIONS[level],
        )
        for level in sorted(constants.MATURITY_LEVEL_NAMES)
    )

    #: Lookup from a rung number to its :class:`MaturityLevel`.
    _BY_LEVEL: dict[int, MaturityLevel] = {stage.level: stage for stage in LEVELS}

    # The intermediate rungs the signal gates target. Named relative to the
    # bounds so no rung number is hard-coded; the ladder is contiguous, so each
    # rung is one step above the previous.
    _LEVEL_PROMPT_RAG = constants.MIN_MATURITY_LEVEL + _ONE_RUNG
    _LEVEL_AGENT = _LEVEL_PROMPT_RAG + _ONE_RUNG
    _LEVEL_MULTI_AGENT = _LEVEL_AGENT + _ONE_RUNG
    _LEVEL_PRODUCTION = _LEVEL_MULTI_AGENT + _ONE_RUNG

    @staticmethod
    def _flag(signals: Signals, name: str) -> bool:
        """Read a boolean signal, treating a missing or ``None`` value as False.

        Args:
            signals: The evidence snapshot for the target.
            name: The :class:`Signals` attribute to read.

        Returns:
            ``True`` when the named signal is present and truthy.
        """
        return bool(getattr(signals, name, False))

    @staticmethod
    def _validate_flag(value: bool, name: str) -> bool:
        """Ensure a keyword flag is a real bool (rejecting ints, strings, None).

        Args:
            value: The supplied keyword flag.
            name: The flag's name, for the error message.

        Returns:
            The validated flag, unchanged.

        Raises:
            TypeError: If ``value`` is not a ``bool``.
        """
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be a bool, not {type(value).__name__}")
        return value

    @classmethod
    def _compute_level(
        cls,
        signals: Signals,
        multi_agent: bool,
        self_improving: bool,
    ) -> int:
        """Resolve the highest maturity level the evidence supports.

        Args:
            signals: The evidence snapshot for the target.
            multi_agent: Whether multiple coordinated agents are in use.
            self_improving: Whether a self-improvement loop is in place.

        Returns:
            The rung number (``MIN_MATURITY_LEVEL`` .. ``MAX_MATURITY_LEVEL``).
        """
        level = constants.MIN_MATURITY_LEVEL
        if cls._flag(signals, constants.SIGNAL_RETRIEVED_CONTEXT):
            level = max(level, cls._LEVEL_PROMPT_RAG)
        if cls._flag(signals, constants.SIGNAL_TOOL_CALLS):
            level = max(level, cls._LEVEL_AGENT)
        if multi_agent:
            level = max(level, cls._LEVEL_MULTI_AGENT)
        if (
            cls._flag(signals, constants.SIGNAL_OPERATIONAL_TRACES)
            and level >= cls._LEVEL_AGENT
        ):
            level = max(level, cls._LEVEL_PRODUCTION)
        if self_improving:
            level = constants.MAX_MATURITY_LEVEL
        return level

    @classmethod
    def _active_signals(
        cls,
        signals: Signals,
        multi_agent: bool,
        self_improving: bool,
    ) -> tuple[str, ...]:
        """Return the maturity signals that are present, in ladder order.

        Args:
            signals: The evidence snapshot for the target.
            multi_agent: Whether multiple coordinated agents are in use.
            self_improving: Whether a self-improvement loop is in place.

        Returns:
            The active signal/flag names, in ascending ladder order.
        """
        flags = (
            (
                constants.SIGNAL_RETRIEVED_CONTEXT,
                cls._flag(signals, constants.SIGNAL_RETRIEVED_CONTEXT),
            ),
            (
                constants.SIGNAL_TOOL_CALLS,
                cls._flag(signals, constants.SIGNAL_TOOL_CALLS),
            ),
            (_FLAG_MULTI_AGENT, multi_agent),
            (
                constants.SIGNAL_OPERATIONAL_TRACES,
                cls._flag(signals, constants.SIGNAL_OPERATIONAL_TRACES),
            ),
            (_FLAG_SELF_IMPROVING, self_improving),
        )
        return tuple(name for name, active in flags if active)

    @classmethod
    def _rationale(
        cls,
        signals: Signals,
        multi_agent: bool,
        self_improving: bool,
        stage: MaturityLevel,
    ) -> str:
        """Explain which signals drove the classification.

        Args:
            signals: The evidence snapshot for the target.
            multi_agent: Whether multiple coordinated agents are in use.
            self_improving: Whether a self-improvement loop is in place.
            stage: The resolved level for the target.

        Returns:
            A one-line rationale naming the level, its driver, and the active
            signals (``none`` when no maturity signal is set).
        """
        active = cls._active_signals(signals, multi_agent, self_improving)
        signals_text = ", ".join(active) if active else "none"
        return (
            f"Level {stage.level} ({stage.name}): {stage.driver}. "
            f"Active signals: {signals_text}."
        )

    @staticmethod
    def classify(
        signals: Signals,
        *,
        multi_agent: bool = False,
        self_improving: bool = False,
    ) -> dict:
        """Classify an evaluation target on the six-level maturity ladder.

        Args:
            signals: The evidence snapshot for the target.
            multi_agent: Whether multiple coordinated agents are in use. Signals
                alone cannot prove coordination, so it is supplied explicitly.
            self_improving: Whether a self-improvement loop feeds evaluations
                back into the system.

        Returns:
            A new dict with the numeric ``level``, its ``name``, a ``rationale``
            naming the signals that drove it, and a ``next_recommendation`` for
            reaching the next level (empty at the top of the ladder). Inputs are
            never mutated.

        Raises:
            TypeError: If ``signals`` is not a :class:`Signals` instance, or if
                ``multi_agent`` or ``self_improving`` is not a ``bool``.
        """
        if not isinstance(signals, Signals):
            raise TypeError("signals must be a Signals instance")
        multi_agent = MaturityClassifier._validate_flag(multi_agent, _FLAG_MULTI_AGENT)
        self_improving = MaturityClassifier._validate_flag(
            self_improving, _FLAG_SELF_IMPROVING
        )

        level = MaturityClassifier._compute_level(signals, multi_agent, self_improving)
        stage = MaturityClassifier._BY_LEVEL[level]
        return {
            "level": stage.level,
            "name": stage.name,
            "rationale": MaturityClassifier._rationale(
                signals, multi_agent, self_improving, stage
            ),
            "next_recommendation": stage.recommendation,
        }
