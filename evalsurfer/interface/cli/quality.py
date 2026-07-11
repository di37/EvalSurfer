"""Command-line interface for the deterministic quality metrics.

Reads one JSON payload and computes whichever of the three metric families are
present -- ``retrieval`` (Recall@k / Precision@k / MRR), ``match`` (exact match /
accuracy / token-F1 / classification P-R-F1), and ``text`` (BLEU / ROUGE /
METEOR). All reference-based, all deterministic, no model calls.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from evalsurfer.interface.cli.metrics import load_json, write_json
from evalsurfer.metrics.quality.report import build_report


def main(argv: list[str] | None = None) -> int:
    """Run the quality-metrics CLI."""
    parser = argparse.ArgumentParser(
        description="Deterministic reference-based quality metrics for AI outputs.",
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
