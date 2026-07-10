"""Diagnostics bundle for EvalSurfer reports.

Run the deterministic diagnostic layers over a single produced report and gather
their results into one ``diagnostics`` block. :class:`DiagnosticsBundle` is pure
orchestration: it delegates to the existing diagnostic services
(:class:`Explainer`, :class:`RootCauseAnalyzer`, :class:`FailureMap`,
:class:`ReviewGate`, :class:`MaturityClassifier`, and :class:`RegressionDiffer`)
and assembles their outputs under the canonical keys in
:data:`constants.DIAGNOSTICS_KEYS`.

Four diagnostics run off the report alone and are always present. The two
comparative diagnostics are optional and included only when their extra input is
supplied: ``maturity`` when a :class:`Signals` snapshot is given, and
``regression`` when a prior (before) report is given.

Deterministic, standard library only, no model calls. The report, the prior
report, and the signals are never mutated; the returned block is always a freshly
built dict.
"""

from __future__ import annotations

from typing import Any, Mapping

import evalsurfer.constants as constants
from evalsurfer.core.planner import Signals
from evalsurfer.analysis.diagnostics import (
    Explainer,
    FailureMap,
    MaturityClassifier,
    RegressionDiffer,
    ReviewGate,
    RootCauseAnalyzer,
)

__all__ = ["DiagnosticsBundle"]

# The diagnostics-block keys, unpacked from the canonical constant so the block
# is built from the very names it must use, in DIAGNOSTICS_KEYS order. Unpacking
# (rather than restating the strings) keeps this module in lockstep with
# constants.DIAGNOSTICS_KEYS and fails loudly at import if that tuple changes
# length.
(
    _KEY_EXPLAINABILITY,
    _KEY_ROOT_CAUSE,
    _KEY_FAILURE_MAP,
    _KEY_REVIEW_GATE,
    _KEY_MATURITY,
    _KEY_REGRESSION,
) = constants.DIAGNOSTICS_KEYS


class DiagnosticsBundle:
    """Assemble a report's diagnostics block from the individual diagnostics.

    Stateless: the bundle only orchestrates the sibling diagnostic services with
    their default configuration, so ``run`` is a ``staticmethod`` and the class
    is a cohesive namespace rather than something to instantiate.
    """

    @staticmethod
    def run(
        report: Mapping[str, Any],
        *,
        before: Mapping[str, Any] | None = None,
        signals: Signals | None = None,
    ) -> dict[str, Any]:
        """Run every applicable diagnostic and gather the results into one block.

        The report-only diagnostics (``explainability``, ``root_cause``,
        ``failure_map``, ``review_gate``) always run. ``maturity`` is added only
        when ``signals`` is supplied, and ``regression`` only when a prior
        ``before`` report is supplied. The result contains only keys from
        :data:`constants.DIAGNOSTICS_KEYS`, in that order. No input is mutated.

        Args:
            report: The produced report to diagnose.
            before: An earlier report to diff ``report`` against; when ``None``
                the ``regression`` entry is omitted.
            signals: The evidence snapshot for the target; when ``None`` the
                ``maturity`` entry is omitted.

        Returns:
            A freshly built diagnostics block: a dict whose keys are a subset of
            :data:`constants.DIAGNOSTICS_KEYS`, each mapping to the corresponding
            diagnostic's output.

        Raises:
            TypeError: If ``report`` or a supplied ``before`` is not a mapping,
                or a supplied ``signals`` is not a :class:`Signals` instance.
        """
        if not isinstance(report, Mapping):
            raise TypeError("report must be a mapping")
        if before is not None and not isinstance(before, Mapping):
            raise TypeError("before must be a mapping")
        if signals is not None and not isinstance(signals, Signals):
            raise TypeError("signals must be a Signals instance")

        block: dict[str, Any] = {
            _KEY_EXPLAINABILITY: Explainer.explain(report),
            _KEY_ROOT_CAUSE: RootCauseAnalyzer.attribute(report),
            _KEY_FAILURE_MAP: FailureMap().render(report),
            _KEY_REVIEW_GATE: ReviewGate().evaluate(report),
        }
        if signals is not None:
            block[_KEY_MATURITY] = MaturityClassifier.classify(signals)
        if before is not None:
            block[_KEY_REGRESSION] = RegressionDiffer.diff(before, report)
        return block
