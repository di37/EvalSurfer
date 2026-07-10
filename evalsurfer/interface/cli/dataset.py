"""Command-line interface for the golden dataset artifact.

Reads one JSON payload with an ``op`` selecting a dataset operation and prints
the result. All deterministic, no model calls.

Operations::

    {"op": "from_traces", "traces": [...], "name": "x", "version": "v1"}
    {"op": "split", "dataset": {...}, "held_out_fraction": 0.2, "salt": "s"}
    {"op": "diff", "before": {...}, "after": {...}}
    {"op": "contamination", "dataset": {...}, "blocklist": [...], "canaries": [...]}
    {"op": "coverage", "dataset": {...}}
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from evalsurfer.interface.cli.metrics import load_json, write_json
from evalsurfer.metrics.dataset.dataset import Dataset

_OPS = ("from_traces", "split", "diff", "contamination", "coverage")


def _dataset(payload: dict[str, Any], key: str = "dataset") -> Dataset:
    """Build a :class:`Dataset` from the payload's ``key`` object."""
    return Dataset.from_mapping(payload.get(key) or {})


def build_report(payload: Any) -> dict[str, Any]:
    """Run a dataset operation from a CLI payload.

    Args:
        payload: An object with an ``op`` and its operands.

    Returns:
        The operation's result (a dataset, diff, contamination, or coverage dict).

    Raises:
        ValueError: If ``payload`` is not an object or ``op`` is unknown/invalid.
    """
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    op = payload.get("op")

    if op == "from_traces":
        traces = payload.get("traces")
        if not isinstance(traces, list):
            raise ValueError("from_traces needs a 'traces' list")
        dataset = Dataset.from_traces(
            traces,
            name=str(payload.get("name", "dataset")),
            version=str(payload.get("version", "v1")),
        )
        return dataset.to_dict()
    if op == "split":
        fraction = payload.get("held_out_fraction")
        if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
            raise ValueError("split needs a numeric 'held_out_fraction'")
        return _dataset(payload).split(
            float(fraction), salt=str(payload.get("salt", ""))
        ).to_dict()
    if op == "diff":
        return _dataset(payload, "after").diff(_dataset(payload, "before"))
    if op == "contamination":
        return _dataset(payload).contamination_report(
            blocklist=tuple(payload.get("blocklist") or ()),
            canaries=tuple(payload.get("canaries") or ()),
        )
    if op == "coverage":
        return _dataset(payload).coverage_summary()

    raise ValueError(f"dataset 'op' must be one of: {', '.join(_OPS)}")


def main(argv: list[str] | None = None) -> int:
    """Run the dataset CLI.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Process exit code: ``0`` on success, ``1`` on a handled error.
    """
    parser = argparse.ArgumentParser(
        description="Build, split, diff, and contamination-check a golden dataset.",
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
