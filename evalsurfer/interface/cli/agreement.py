"""Command-line interface for chance-corrected agreement & judge-vs-human stats.

Reads one JSON payload with an ``op`` selecting a calibration statistic and
prints the result. This is the deterministic "eval of the eval" math -- no model
calls.

Operations::

    {"op": "cohen_kappa", "rater_a": [...], "rater_b": [...]}
    {"op": "fleiss_kappa", "ratings": [{"label": count, ...}, ...]}
    {"op": "krippendorff_alpha", "reliability_data": [[r1, r2, ...], ...]}
    {"op": "reference", "judge": {cid: score}, "gold": {cid: score}}
    {"op": "reference_batch", "pairs": [[{...}, {...}], ...]}
    {"op": "mae", "judge": [...], "human": [...]}
    {"op": "rank_correlation", "judge": [...], "human": [...]}
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import evalsurfer.constants as constants
from evalsurfer.analysis.calibration.agreement import AgreementStats
from evalsurfer.analysis.calibration.reference import ReferenceCalibrator
from evalsurfer.interface.cli.metrics import load_json, write_json

_OPS = (
    "cohen_kappa",
    "fleiss_kappa",
    "krippendorff_alpha",
    "reference",
    "reference_batch",
    "mae",
    "rank_correlation",
)


def _pairs(payload: dict[str, Any]) -> list[tuple[Any, Any]]:
    """Validate and coerce a list of ``[judge, gold]`` mapping pairs."""
    pairs: list[tuple[Any, Any]] = []
    for pair in payload.get("pairs") or []:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("each entry in 'pairs' must be [judge, gold]")
        pairs.append((pair[0], pair[1]))
    return pairs


def build_report(payload: Any) -> dict[str, Any]:
    """Run a calibration statistic from a CLI payload.

    Args:
        payload: An object with an ``op`` and its operands.

    Returns:
        The statistic's result as a dict.

    Raises:
        ValueError: If ``payload`` is not an object or ``op`` is unknown/invalid.
        TypeError: If an operand has the wrong type.
    """
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    op = payload.get("op")

    if op == constants.METRIC_COHEN_KAPPA:
        return {op: AgreementStats.cohen_kappa(payload.get("rater_a"), payload.get("rater_b"))}
    if op == constants.METRIC_FLEISS_KAPPA:
        return {op: AgreementStats.fleiss_kappa(payload.get("ratings"))}
    if op == constants.METRIC_KRIPPENDORFF_ALPHA:
        return {op: AgreementStats.krippendorff_alpha(payload.get("reliability_data"))}
    if op == "reference":
        return ReferenceCalibrator.compare(payload.get("judge") or {}, payload.get("gold") or {})
    if op == "reference_batch":
        return ReferenceCalibrator.summarize(_pairs(payload))
    if op == "mae":
        return {
            constants.METRIC_JUDGE_HUMAN_MAE: ReferenceCalibrator.mean_absolute_error(
                payload.get("judge"), payload.get("human")
            )
        }
    if op == "rank_correlation":
        return {
            constants.METRIC_RANK_CORRELATION: ReferenceCalibrator.rank_correlation(
                payload.get("judge"), payload.get("human")
            )
        }

    raise ValueError(f"agreement 'op' must be one of: {', '.join(_OPS)}")


def main(argv: list[str] | None = None) -> int:
    """Run the agreement / judge-vs-human CLI.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Process exit code: ``0`` on success, ``1`` on a handled error.
    """
    parser = argparse.ArgumentParser(
        description="Chance-corrected agreement and judge-vs-human calibration stats.",
    )
    parser.add_argument("input", help="Path to a JSON payload, or '-' for stdin.")
    parser.add_argument("--output", "-o", help="Optional output path. Defaults to stdout.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    try:
        report = build_report(load_json(args.input))
        write_json(report, args.output, args.pretty)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
