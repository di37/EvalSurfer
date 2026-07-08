"""Unified command-line interface for EvalSurfer.

A single ``evalsurfer`` entry point that dispatches to every deterministic
verb: ``evaluate`` (assemble a report), ``validate`` (structural check), ``gate``
(release decision), ``diagnose`` (diagnostics block), ``plan`` (adaptive plan),
``metrics`` (operational metrics), ``calibrate`` (eval of the eval),
``redteam-template`` / ``redteam-check`` (safety probes), and ``trajectory``
(agent-trajectory diff). No model calls anywhere.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

import evalsurfer.constants as constants
from evalsurfer.calibration.calibrate import CalibrationCase, Calibrator
from evalsurfer.cli import metrics as metrics_cli
from evalsurfer.cli import plan as plan_cli
from evalsurfer.core.evaluate import Evaluator
from evalsurfer.core.planner import Signals
from evalsurfer.core.report import Gate, ReportValidator
from evalsurfer.diagnostics.bundle import DiagnosticsBundle
from evalsurfer.safety.redteam import RedTeam
from evalsurfer.trajectory.agent_trace import TrajectoryEvaluator


def load_json(path: str) -> Any:
    """Load JSON from a file path, or from stdin when ``path`` is ``"-"``.

    Args:
        path: A filesystem path, or ``"-"`` for stdin.

    Returns:
        The parsed JSON value.
    """
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def emit(data: Any, out: str | None, pretty: bool) -> None:
    """Write JSON to ``out`` (or stdout when ``out`` is ``None``).

    Args:
        data: The JSON-serialisable value.
        out: The output path, or ``None`` for stdout.
        pretty: Whether to indent and sort keys.
    """
    text = json.dumps(data, indent=2 if pretty else None, sort_keys=pretty)
    if out is None:
        print(text)
        return
    with open(out, "w", encoding="utf-8") as file:
        file.write(text + "\n")


def _cmd_evaluate(args: argparse.Namespace) -> int:
    """Assemble a full report from an evaluation request."""
    emit(Evaluator.evaluate(load_json(args.input)), args.out, args.pretty)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """Structurally validate a report; exit non-zero when invalid."""
    result = ReportValidator.validate(load_json(args.input))
    emit(result, None, args.pretty)
    return 0 if result["valid"] else 1


def _cmd_gate(args: argparse.Namespace) -> int:
    """Gate a report against a minimum decision; exit non-zero when it fails."""
    result = Gate.evaluate(load_json(args.input), args.min)
    emit(result, None, args.pretty)
    return 0 if result["passed"] else 1


def _cmd_diagnose(args: argparse.Namespace) -> int:
    """Run the diagnostics bundle over a report (optionally vs a prior report)."""
    before = load_json(args.before) if args.before else None
    emit(DiagnosticsBundle.run(load_json(args.input), before=before), args.out, args.pretty)
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    """Infer the adaptive plan for a sample."""
    emit(plan_cli.build_report(load_json(args.input)), args.out, args.pretty)
    return 0


def _cmd_metrics(args: argparse.Namespace) -> int:
    """Compute operational metrics from a traces payload."""
    emit(metrics_cli.build_report(load_json(args.input)), args.out, args.pretty)
    return 0


def _cmd_calibrate(args: argparse.Namespace) -> int:
    """Score a judge against a calibration case ("eval of the eval")."""
    case_data = load_json(args.input)
    case = _build_calibration_case(case_data)
    reports = case_data.get("judge_reports") or []
    emit(Calibrator.summarize(case, reports), args.out, args.pretty)
    return 0


def _cmd_redteam_template(args: argparse.Namespace) -> int:
    """Emit the red-team probe battery for a target's shape."""
    emit(
        RedTeam.template(rag=args.rag, agent=args.agent, pii=args.pii),
        args.out,
        args.pretty,
    )
    return 0


def _cmd_redteam_check(args: argparse.Namespace) -> int:
    """Triage collected red-team outputs (deterministic PII + judgment flags)."""
    emit(RedTeam.check(load_json(args.input)), args.out, args.pretty)
    return 0


def _cmd_trajectory(args: argparse.Namespace) -> int:
    """Diff an agent's actual tool trajectory against an expected spec."""
    payload = load_json(args.input)
    result = TrajectoryEvaluator.evaluate(payload.get("actual", {}), payload.get("expected", {}))
    emit(result, args.out, args.pretty)
    return 0


def _build_calibration_case(data: Any) -> CalibrationCase:
    """Construct a :class:`CalibrationCase` from a calibration file's JSON.

    Args:
        data: A mapping with ``name``, ``signals`` (bool flags) or ``sample``,
            ``expected_applicable_pillars``, ``expected_score_ranges``,
            ``expected_decision``, ``expected_top_issue_severity``, and
            ``expected_safety_escalation``.

    Returns:
        The constructed :class:`CalibrationCase`.

    Raises:
        ValueError: If ``data`` is not an object.
    """
    if not isinstance(data, dict):
        raise ValueError("calibration input must be an object")
    if "signals" in data and isinstance(data["signals"], dict):
        known = {k: v for k, v in data["signals"].items() if k in constants.SIGNALS}
        signals = Signals(**known)
    else:
        signals = Signals.from_sample(data.get("sample", {}))
    ranges = {
        cid: tuple(bounds)
        for cid, bounds in (data.get("expected_score_ranges") or {}).items()
    }
    return CalibrationCase(
        name=str(data.get("name", "calibration-case")),
        signals=signals,
        expected_applicable_pillars=frozenset(data.get("expected_applicable_pillars") or []),
        expected_score_ranges=ranges,
        expected_decision=data.get("expected_decision", constants.DECISION_PASS_WITH_FIXES),
        expected_top_issue_severity=data.get("expected_top_issue_severity"),
        expected_safety_escalation=bool(data.get("expected_safety_escalation", False)),
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with one subparser per verb.

    Returns:
        The configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="evalsurfer",
        description="Deterministic evaluation, diagnostics, and gating for AI applications.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add(name: str, handler: Callable[[argparse.Namespace], int], *, help: str) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, help=help)
        sub.set_defaults(handler=handler)
        return sub

    def with_input_out(sub: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sub.add_argument("input", help="Path to a JSON file, or '-' for stdin.")
        sub.add_argument("--out", "-o", help="Optional output path. Defaults to stdout.")
        sub.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
        return sub

    with_input_out(add("evaluate", _cmd_evaluate, help="Assemble a full report from a request."))
    with_input_out(add("diagnose", _cmd_diagnose, help="Run the diagnostics bundle over a report.")).add_argument(
        "--before", help="Prior report to diff against (adds the regression diagnostic)."
    )
    with_input_out(add("plan", _cmd_plan, help="Infer the adaptive plan for a sample."))
    with_input_out(add("metrics", _cmd_metrics, help="Operational metrics from a traces payload."))
    with_input_out(add("calibrate", _cmd_calibrate, help="Score a judge against a calibration case."))
    with_input_out(add("trajectory", _cmd_trajectory, help="Diff an agent trajectory vs expectations."))
    with_input_out(add("redteam-check", _cmd_redteam_check, help="Triage collected red-team outputs."))

    validate = add("validate", _cmd_validate, help="Structurally validate a report (exit 1 if invalid).")
    validate.add_argument("input", help="Path to a report JSON, or '-' for stdin.")
    validate.add_argument("--pretty", action="store_true")

    gate = add("gate", _cmd_gate, help="Gate a report against a minimum decision (exit 1 if below).")
    gate.add_argument("input", help="Path to a report JSON, or '-' for stdin.")
    gate.add_argument("--min", choices=constants.DECISIONS, default=constants.DECISION_PASS_WITH_FIXES)
    gate.add_argument("--pretty", action="store_true")

    template = add("redteam-template", _cmd_redteam_template, help="Emit red-team probes for a target shape.")
    template.add_argument("--rag", action="store_true", help="Include retrieval-injection probes.")
    template.add_argument("--agent", action="store_true", help="Include tool-exfiltration probes.")
    template.add_argument("--pii", action="store_true", help="Include the PII-bait probe.")
    template.add_argument("--out", "-o", help="Optional output path. Defaults to stdout.")
    template.add_argument("--pretty", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the unified EvalSurfer CLI.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        A process exit code: the handler's code, or ``1`` on a handled error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
