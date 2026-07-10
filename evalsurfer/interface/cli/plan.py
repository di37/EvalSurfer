"""Command-line interface for the EvalSurfer adaptive planner.

Reads a JSON payload describing an evaluation target and prints the plan: which
pillars and criteria apply, why, and a coverage score. No model calls.

Accepts one of::

    {"signals": {"answer": true, "retrieved_context": true}}
    {"sample": {"query": "...", "answer": "...", "retrieved_docs": [...]}}
    {"query": "...", "answer": "...", "tool_calls": [...]}    # bare sample
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import evalsurfer.constants as constants
from evalsurfer.core.planner import EvaluationPlanner, Signals


def load_json(path: str) -> Any:
    """Load JSON from a file path, or from stdin when ``path`` is ``"-"``.

    Args:
        path: A filesystem path, or ``"-"`` to read from stdin.

    Returns:
        The parsed JSON value.
    """
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def signals_from_flags(data: dict[str, Any]) -> Signals:
    """Build :class:`Signals` from an explicit flags object.

    Args:
        data: A mapping of signal name to boolean.

    Returns:
        The constructed :class:`Signals`.

    Raises:
        ValueError: If a key is not a known signal or a value is not a bool.
    """
    unknown = set(data) - set(constants.SIGNALS)
    if unknown:
        raise ValueError(f"unknown signal(s): {', '.join(sorted(unknown))}")
    for key, value in data.items():
        if not isinstance(value, bool):
            raise ValueError(f"signal '{key}' must be a boolean")
    return Signals(**data)


def resolve_signals(payload: Any) -> Signals:
    """Turn a CLI payload into :class:`Signals`.

    Args:
        payload: A ``{"signals": {...}}`` object, a ``{"sample": {...}}`` object,
            or a bare sample mapping.

    Returns:
        The resolved :class:`Signals`.

    Raises:
        ValueError: If the payload is not an object or ``signals`` is malformed.
    """
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    if "signals" in payload:
        if not isinstance(payload["signals"], dict):
            raise ValueError("'signals' must be an object")
        return signals_from_flags(payload["signals"])
    if "sample" in payload:
        return Signals.from_sample(payload["sample"])
    return Signals.from_sample(payload)


def build_report(payload: Any) -> dict[str, Any]:
    """Build the planner report (signals + plan) from a CLI payload.

    Args:
        payload: The parsed input payload.

    Returns:
        ``{"signals": {...}, "plan": {...}}``.
    """
    signals = resolve_signals(payload)
    plan = EvaluationPlanner.plan(signals)
    return {"signals": vars(signals), "plan": plan.to_dict()}


def write_json(data: Any, path: str | None, pretty: bool) -> None:
    """Write ``data`` as JSON to ``path`` (or stdout when ``path`` is ``None``).

    Args:
        data: The JSON-serialisable value to write.
        path: The output path, or ``None`` for stdout.
        pretty: Whether to indent and sort keys.
    """
    output = json.dumps(data, indent=2 if pretty else None, sort_keys=pretty)
    if path is None:
        print(output)
        return
    with open(path, "w", encoding="utf-8") as file:
        file.write(output)
        file.write("\n")


def main(argv: list[str] | None = None) -> int:
    """Run the planner CLI.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Process exit code: ``0`` on success, ``1`` on a handled error.
    """
    parser = argparse.ArgumentParser(
        description="Plan an EvalSurfer evaluation from the available inputs.",
    )
    parser.add_argument("input", help="Path to a JSON payload, or '-' to read from stdin.")
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
