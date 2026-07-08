# `evalsurfer/` — the deterministic measurement layer

This package is the supporting Python layer around the EvalSurfer skill. The
**skill is the judge**; this code does everything *measurable* around it —
planning scope, assembling and validating reports, gating releases, diagnostics,
operational scoring, calibration, red-team triage, trajectory analysis, and
ecosystem imports.

Every module here is **deterministic, standard-library only, and makes no model
or API calls.** Inputs are never mutated (new objects are always returned).

## Layout

| Module / subpackage | What lives here |
| --- | --- |
| [`constants.py`](constants.py) | Every shared constant (all `UPPERCASE`, `Final`): pillars, the 29-criterion catalog, score scales, decisions, severities, signals, SLO fields/bands, diagnostics keys, and framework metadata. The single source of truth the rest of the package imports. |
| [`core/`](core/) | Scoring, the adaptive planner, report validation + release gate, and the end-to-end `Evaluator` orchestrator. |
| [`operational/`](operational/) | Raw operational metrics from request traces, and SLO-based auto-scoring of the operational pillar. |
| [`diagnostics/`](diagnostics/) | Explain-and-compare modules (attribution, root cause, regression, maturity, industry profile, review gate, …) plus the `DiagnosticsBundle`. |
| [`safety/`](safety/) | Executable red-team probe battery and deterministic triage. |
| [`trajectory/`](trajectory/) | Agent tool-call trajectory evaluation. |
| [`calibration/`](calibration/) | The "eval of the eval" — scoring the judge against an oracle. |
| [`adapters/`](adapters/) | Import RAGAS / promptfoo / OpenTelemetry / LangSmith artifacts into native shapes. |
| [`cli/`](cli/) | Command-line entry points (`evalsurfer` and the `plan` / `metrics` tools). |

## Conventions

- **Absolute imports** everywhere (`from evalsurfer.core.scoring import ScoringModel`).
- **Class-based services** with `@staticmethod` / `@classmethod`; frozen dataclasses for value objects.
- **Google-style docstrings** (Args / Returns / Raises).
- **No third-party runtime dependencies.** `jsonschema` is an optional `dev` extra used only by tests.

See the [root README](../README.md) for the product overview and the
[worked scenarios](../examples/scenarios/) for runnable end-to-end demos.
