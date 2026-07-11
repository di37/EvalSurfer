"""Unified command-line interface for EvalSurfer.

A single ``evalsurfer`` entry point that dispatches to every deterministic
verb: ``evaluate`` (Interface full CIMAA pipeline), ``validate`` (structural
check), ``gate`` (Core decision bar; ``--policy`` for Assurance), ``diagnose``
(Analysis diagnostics block), ``plan`` (adaptive plan), ``metrics`` (operational
metrics), ``quality`` (reference quality metrics), ``dataset`` (golden-dataset
operations), ``agreement`` (judge agreement), ``calibrate`` (eval of the eval),
``redteam-template`` / ``redteam-check`` (safety probes), and ``trajectory``
(agent-trajectory diff). No model calls anywhere.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

import evalsurfer.constants as constants
from evalsurfer.analysis.calibration.calibrate import CalibrationCase, Calibrator
from evalsurfer.analysis.diagnostics.bundle import DiagnosticsBundle
from evalsurfer.assurance.policy.guardrails import GuardrailPolicy, Guardrails
from evalsurfer.assurance.safety.redteam import RedTeam
from evalsurfer.assurance.trajectory.agent_trace import TrajectoryEvaluator
from evalsurfer.core.planner import Signals
from evalsurfer.core.report import Gate, ReportValidator
from evalsurfer.interface.cli import agreement as agreement_cli
from evalsurfer.interface.cli import dataset as dataset_cli
from evalsurfer.interface.cli import metrics as metrics_cli
from evalsurfer.interface.cli import plan as plan_cli
from evalsurfer.interface.cli import quality as quality_cli
from evalsurfer.interface.pipeline import evaluate as run_evaluate


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
    """Run the Interface pipeline: Metrics enrich → Core assemble → Analysis diagnose."""
    emit(run_evaluate(load_json(args.input)), args.out, args.pretty)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    """Structurally validate a report; exit non-zero when invalid."""
    result = ReportValidator.validate(load_json(args.input))
    emit(result, None, args.pretty)
    return 0 if result["valid"] else 1


def _read_changed_files(path: str | None) -> tuple[str, ...]:
    """Read a newline-separated changed-file list from a path or stdin.

    Args:
        path: A filesystem path, ``"-"`` for stdin, or ``None`` for no files.

    Returns:
        The non-empty, stripped file names, in order.
    """
    if not path:
        return ()
    if path == "-":
        text = sys.stdin.read()
    else:
        with open(path, encoding="utf-8") as file:
            text = file.read()
    return tuple(line.strip() for line in text.splitlines() if line.strip())


def _cmd_gate(args: argparse.Namespace) -> int:
    """Gate a report against a minimum decision, or a full guardrail policy."""
    report = load_json(args.input)
    if args.policy:
        policy = GuardrailPolicy.from_mapping(load_json(args.policy))
        result = Guardrails.check(
            report,
            policy,
            changed_files=_read_changed_files(args.changed_files),
            attempt=args.attempt,
        )
        emit(result, None, args.pretty)
        return 0 if result["allowed"] else 1
    result = Gate.evaluate(report, args.min)
    emit(result, None, args.pretty)
    return 0 if result["passed"] else 1


def _cmd_diagnose(args: argparse.Namespace) -> int:
    """Run diagnostics, optionally adding maturity signals and a prior report."""
    before = load_json(args.before) if args.before else None
    signals = _load_signals(args.signals) if args.signals else None
    emit(
        DiagnosticsBundle.run(load_json(args.input), before=before, signals=signals),
        args.out,
        args.pretty,
    )
    return 0


def _load_signals(path: str) -> Signals:
    """Load a canonical signals object or infer signals from a raw sample.

    A top-level ``signals`` object is treated as an explicit MCP-compatible
    snapshot and validated strictly. A top-level ``sample`` object or any
    unwrapped object is passed through :meth:`Signals.from_sample`, so raw
    samples may contain arbitrary application metadata without ambiguity.

    Args:
        path: Path to the JSON payload, or ``"-"`` for stdin.

    Returns:
        The explicit or inferred evidence signals.

    Raises:
        TypeError: If the payload or a wrapper value is not a JSON object.
        ValueError: If an explicit signals object has an unknown field.
    """
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise TypeError("signals input must be a JSON object")

    if "signals" in payload:
        explicit = payload["signals"]
        if not isinstance(explicit, dict):
            raise TypeError("signals must be a JSON object")
        return _explicit_signals(explicit)

    if "sample" in payload:
        sample = payload["sample"]
        if not isinstance(sample, dict):
            raise TypeError("sample must be a JSON object")
        return Signals.from_sample(sample)

    return Signals.from_sample(payload)


def _explicit_signals(payload: dict[str, Any]) -> Signals:
    """Validate and construct an MCP-shaped explicit signals snapshot."""
    unknown = set(payload).difference(constants.SIGNALS)
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"unknown signal field(s): {names}")
    invalid = [name for name, value in payload.items() if not isinstance(value, bool)]
    if invalid:
        names = ", ".join(sorted(invalid))
        raise TypeError(f"signal field(s) must be boolean: {names}")
    return Signals(**payload)


def _cmd_plan(args: argparse.Namespace) -> int:
    """Infer the adaptive plan for a sample."""
    emit(plan_cli.build_report(load_json(args.input)), args.out, args.pretty)
    return 0


def _cmd_metrics(args: argparse.Namespace) -> int:
    """Compute operational metrics from a traces payload."""
    emit(metrics_cli.build_report(load_json(args.input)), args.out, args.pretty)
    return 0


def _cmd_quality(args: argparse.Namespace) -> int:
    """Compute deterministic quality metrics (retrieval / match / text)."""
    emit(quality_cli.build_report(load_json(args.input)), args.out, args.pretty)
    return 0


def _cmd_dataset(args: argparse.Namespace) -> int:
    """Build / split / diff / contamination-check a golden dataset."""
    emit(dataset_cli.build_report(load_json(args.input)), args.out, args.pretty)
    return 0


def _cmd_agreement(args: argparse.Namespace) -> int:
    """Chance-corrected agreement and judge-vs-human calibration stats."""
    emit(agreement_cli.build_report(load_json(args.input)), args.out, args.pretty)
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
    result = TrajectoryEvaluator.evaluate(
        payload.get("actual", {}), payload.get("expected", {})
    )
    emit(result, args.out, args.pretty)
    return 0


def _build_calibration_case(data: Any) -> CalibrationCase:
    """Construct a :class:`CalibrationCase` from a calibration file's JSON.

    Args:
        data: A mapping with ``name``, ``signals`` (bool flags) or ``sample``,
            ``expected_applicable_categories``, ``expected_score_ranges``,
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
        expected_applicable_categories=frozenset(
            data.get("expected_applicable_categories") or []
        ),
        expected_score_ranges=ranges,
        expected_decision=data.get(
            "expected_decision", constants.DECISION_PASS_WITH_FIXES
        ),
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

    def add(
        name: str, handler: Callable[[argparse.Namespace], int], *, help: str
    ) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, help=help)
        sub.set_defaults(handler=handler)
        return sub

    def with_input_out(sub: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sub.add_argument("input", help="Path to a JSON file, or '-' for stdin.")
        sub.add_argument(
            "--out", "-o", help="Optional output path. Defaults to stdout."
        )
        sub.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
        return sub

    with_input_out(
        add(
            "evaluate",
            _cmd_evaluate,
            help="Full CIMAA pipeline: Metrics enrich → Core assemble → Analysis diagnose.",
        )
    )
    diagnose = with_input_out(
        add(
            "diagnose",
            _cmd_diagnose,
            help="Run diagnostics, optionally adding maturity and regression.",
        )
    )
    diagnose.add_argument(
        "--before",
        help="Prior report to diff against (adds the regression diagnostic).",
    )
    diagnose.add_argument(
        "--signals",
        help=(
            "JSON evidence sample, or a strict Signals object wrapped in "
            "'signals' (a 'sample' wrapper is also accepted); adds maturity."
        ),
    )
    with_input_out(add("plan", _cmd_plan, help="Infer the adaptive plan for a sample."))
    with_input_out(
        add("metrics", _cmd_metrics, help="Operational metrics from a traces payload.")
    )
    with_input_out(
        add(
            "quality",
            _cmd_quality,
            help="Deterministic quality metrics (retrieval/match/text).",
        )
    )
    with_input_out(
        add(
            "dataset",
            _cmd_dataset,
            help="Golden dataset: build/split/diff/contamination-check.",
        )
    )
    with_input_out(
        add(
            "agreement",
            _cmd_agreement,
            help="Chance-corrected agreement + judge-vs-human stats.",
        )
    )
    with_input_out(
        add(
            "calibrate",
            _cmd_calibrate,
            help="Score a judge against a calibration case.",
        )
    )
    with_input_out(
        add(
            "trajectory",
            _cmd_trajectory,
            help="Diff an agent trajectory vs expectations.",
        )
    )
    with_input_out(
        add(
            "redteam-check",
            _cmd_redteam_check,
            help="Triage collected red-team outputs.",
        )
    )

    validate = add(
        "validate",
        _cmd_validate,
        help="Structurally validate a report (exit 1 if invalid).",
    )
    validate.add_argument("input", help="Path to a report JSON, or '-' for stdin.")
    validate.add_argument("--pretty", action="store_true")

    gate = add(
        "gate",
        _cmd_gate,
        help="Gate a report against a minimum decision or a guardrail policy (exit 1 if blocked).",
    )
    gate.add_argument("input", help="Path to a report JSON, or '-' for stdin.")
    gate.add_argument(
        "--min",
        choices=constants.DECISIONS,
        default=constants.DECISION_PASS_WITH_FIXES,
        help="Minimum passing decision (ignored when --policy is given).",
    )
    gate.add_argument(
        "--policy", help="Path to a guardrails.json policy to enforce instead of --min."
    )
    gate.add_argument(
        "--changed-files",
        help="Path (or '-') to a newline-separated changed-file list, matched against the policy's sensitive_paths.",
    )
    gate.add_argument(
        "--attempt",
        type=int,
        help="Current fix-attempt number, checked against the policy's max_fix_attempts.",
    )
    gate.add_argument("--pretty", action="store_true")

    template = add(
        "redteam-template",
        _cmd_redteam_template,
        help="Emit red-team probes for a target shape.",
    )
    template.add_argument(
        "--rag", action="store_true", help="Include retrieval-injection probes."
    )
    template.add_argument(
        "--agent", action="store_true", help="Include tool-exfiltration probes."
    )
    template.add_argument(
        "--pii", action="store_true", help="Include the PII-bait probe."
    )
    template.add_argument(
        "--out", "-o", help="Optional output path. Defaults to stdout."
    )
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
