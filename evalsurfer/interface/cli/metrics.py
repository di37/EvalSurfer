"""Command-line interface for operational AI evaluation metrics."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
import json
import sys
from typing import Any

from evalsurfer.metrics.operational.metrics import (
    OperationalMetrics,
    Pricing,
    RequestTrace,
)


def dataclass_to_dict(value: Any) -> Any:
    """Recursively convert dataclasses to JSON-serializable dictionaries."""

    if is_dataclass(value):
        return {
            key: dataclass_to_dict(nested_value)
            for key, nested_value in asdict(value).items()
        }
    if isinstance(value, dict):
        return {
            str(key): dataclass_to_dict(nested_value)
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [dataclass_to_dict(item) for item in value]
    return value


def load_json(path: str) -> Any:
    """Load JSON from a file path or stdin when path is '-'."""

    if path == "-":
        return json.load(sys.stdin)

    with open(path, encoding="utf-8") as file:
        return json.load(file)


def parse_pricing(data: dict[str, Any]) -> Pricing | None:
    """Parse optional pricing from the input payload."""

    pricing = data.get("pricing")
    if pricing is None:
        return None

    return Pricing(
        input_per_million=float(pricing["input_per_million"]),
        output_per_million=float(pricing["output_per_million"]),
    )


def build_report(payload: Any) -> dict[str, Any]:
    """Build an operational metrics report from a trace payload."""

    if isinstance(payload, list):
        trace_payloads = payload
        pricing = None
    elif isinstance(payload, dict):
        trace_payloads = payload.get("traces")
        if not isinstance(trace_payloads, list):
            raise ValueError("input JSON must contain a 'traces' list")
        pricing = parse_pricing(payload)
    else:
        raise ValueError("input JSON must be an object or list")

    traces = [
        RequestTrace.from_mapping(trace_payload) for trace_payload in trace_payloads
    ]
    summary = OperationalMetrics.summarize(traces, pricing=pricing)

    return {
        "summary": dataclass_to_dict(summary),
        "latency_under_load": dataclass_to_dict(
            OperationalMetrics.latency_under_load(traces)
        ),
    }


def write_json(data: Any, path: str | None, pretty: bool) -> None:
    """Write JSON output to stdout or a file."""

    output = json.dumps(data, indent=2 if pretty else None, sort_keys=pretty)
    if path is None:
        print(output)
        return

    with open(path, "w", encoding="utf-8") as file:
        file.write(output)
        file.write("\n")


def main(argv: list[str] | None = None) -> int:
    """Run the operational metrics CLI."""

    parser = argparse.ArgumentParser(
        description="Calculate operational metrics for AI application traces.",
    )
    parser.add_argument(
        "input",
        help="Path to a JSON trace file, or '-' to read JSON from stdin.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Optional output path. Defaults to stdout.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
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
