"""Command-line interface for the deterministic quality metrics.

Reads one JSON payload and computes whichever of the three metric families are
present -- ``retrieval`` (Recall@k / Precision@k / MRR), ``match`` (exact match /
accuracy / token-F1 / classification P-R-F1), and ``text`` (BLEU / ROUGE /
METEOR). All reference-based, all deterministic, no model calls.

Payload shape (every section optional; at least one required)::

    {
      "retrieval": {"cases": [{"retrieved": [...], "relevant": [...], "k": 5}], "k": 5},
      "match": {"predictions": [...], "references": [...],
                "task": "extraction" | "classification",
                "average": "macro", "positive_label": null},
      "text": {"task": "translation" | "summarization" | "generation",
               "items": [{"candidate": "...", "references": ["..."]}],
               "metrics": ["bleu", "rouge_n", "rouge_l", "meteor"], "n": 1}
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import evalsurfer.constants as constants
from evalsurfer.interface.cli.metrics import dataclass_to_dict, load_json, write_json
from evalsurfer.metrics.quality.matching import MatchMetrics
from evalsurfer.metrics.quality.retrieval import RetrievalCase, RetrievalMetrics
from evalsurfer.metrics.quality.text import TextMetrics

_ALL_TEXT_METRICS = (
    constants.METRIC_BLEU,
    constants.METRIC_ROUGE_N,
    constants.METRIC_ROUGE_L,
    constants.METRIC_METEOR,
)


def _retrieval_section(data: Any) -> dict[str, Any]:
    """Summarize retrieval metrics from a ``{"cases": [...], "k": n}`` block."""
    if not isinstance(data, dict):
        raise ValueError("retrieval must be an object")
    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("retrieval.cases must be a list")
    cases = [RetrievalCase.from_mapping(case) for case in raw_cases]
    summary = RetrievalMetrics.summarize(cases, k=data.get("k"))
    return dataclass_to_dict(summary)


def _match_section(data: Any) -> dict[str, Any]:
    """Compute match / classification metrics from a ``match`` block."""
    if not isinstance(data, dict):
        raise ValueError("match must be an object")
    predictions = data.get("predictions")
    references = data.get("references")
    task = data.get("task", "extraction")

    if task == "classification":
        report = MatchMetrics.classification_report(
            predictions,
            references,
            average=data.get("average", constants.AVERAGE_MACRO),
            positive_label=data.get("positive_label"),
        )
        result = dataclass_to_dict(report)
        result["task"] = "classification"
        return result
    if task == "extraction":
        return {
            "task": "extraction",
            "exact_match_accuracy": MatchMetrics.exact_match_accuracy(
                predictions, references
            ),
            "token_f1": MatchMetrics.token_f1_mean(predictions, references),
            "count": len(predictions),
        }
    raise ValueError("match.task must be 'extraction' or 'classification'")


def _reference_list(item: dict[str, Any]) -> list[str]:
    """Normalize an item's ``references``/``reference`` into a non-empty list."""
    references = item.get("references")
    if isinstance(references, list):
        refs = references
    elif isinstance(references, str):
        refs = [references]
    elif item.get("reference") is not None:
        refs = [item["reference"]]
    else:
        refs = []
    if not refs:
        raise ValueError("each text item needs a 'reference' or 'references'")
    return refs


def _resolve_text_metrics(data: dict[str, Any]) -> list[str]:
    """Pick the metric ids to compute from an explicit list or the task type."""
    metrics = data.get("metrics")
    if metrics is not None:
        if not isinstance(metrics, list) or not metrics:
            raise ValueError("text.metrics must be a non-empty list")
        return metrics
    task = data.get("task")
    if task is None:
        return list(_ALL_TEXT_METRICS)
    if task not in constants.TEXT_TASK_METRICS:
        raise ValueError(f"text.task must be one of {constants.TEXT_TASKS}")
    return list(constants.TEXT_TASK_METRICS[task])


def _text_section(data: Any) -> dict[str, Any]:
    """Compute reference-text metrics from a ``text`` block."""
    if not isinstance(data, dict):
        raise ValueError("text must be an object")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("text.items must be a non-empty list")
    metrics = _resolve_text_metrics(data)
    n = data.get("n", constants.ROUGE_DEFAULT_N)

    per_item: list[dict[str, Any]] = []
    bleu_candidates: list[str] = []
    bleu_references: list[list[str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each text item must be an object")
        candidate = item.get("candidate")
        refs = _reference_list(item)
        entry: dict[str, Any] = {}
        for metric in metrics:
            if metric == constants.METRIC_BLEU:
                entry[metric] = TextMetrics.bleu(candidate, refs)
            elif metric == constants.METRIC_ROUGE_N:
                # Multi-reference convention: score each reference, keep the best.
                best = max(
                    (TextMetrics.rouge_n(candidate, ref, n=n) for ref in refs),
                    key=lambda score: score.f1,
                )
                entry[metric] = dataclass_to_dict(best)
            elif metric == constants.METRIC_ROUGE_L:
                best = max(
                    (TextMetrics.rouge_l(candidate, ref) for ref in refs),
                    key=lambda score: score.f1,
                )
                entry[metric] = dataclass_to_dict(best)
            elif metric == constants.METRIC_METEOR:
                entry[metric] = max(
                    TextMetrics.meteor(candidate, ref) for ref in refs
                )
            else:
                raise ValueError(f"unknown text metric: {metric}")
        per_item.append(entry)
        bleu_candidates.append(candidate)
        bleu_references.append(refs)

    result: dict[str, Any] = {
        "task": data.get("task"),
        "metrics": metrics,
        "items": per_item,
    }
    if constants.METRIC_BLEU in metrics:
        result["corpus_bleu"] = TextMetrics.corpus_bleu(bleu_candidates, bleu_references)
    return result


def build_report(payload: Any) -> dict[str, Any]:
    """Build a quality-metrics report from a CLI payload.

    Args:
        payload: The parsed input; an object with any of ``retrieval``,
            ``match``, or ``text``.

    Returns:
        A report with a section per family that was present.

    Raises:
        ValueError: If ``payload`` is not an object or has no known section.
        TypeError: If a metric input has the wrong type.
    """
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    report: dict[str, Any] = {}
    if "retrieval" in payload:
        report["retrieval"] = _retrieval_section(payload["retrieval"])
    if "match" in payload:
        report["match"] = _match_section(payload["match"])
    if "text" in payload:
        report["text"] = _text_section(payload["text"])
    if not report:
        raise ValueError(
            "input must contain at least one of: retrieval, match, text"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    """Run the quality-metrics CLI.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Process exit code: ``0`` on success, ``1`` on a handled error.
    """
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
