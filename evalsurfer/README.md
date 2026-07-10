# `evalsurfer/` — the deterministic measurement layer

This package is the deterministic measurement layer around the EvalSurfer skill.
The **harness LLM is the judge**; this code does everything *measurable* around
it — planning scope, assembling and validating reports, gating releases,
diagnostics, operational scoring, calibration, red-team triage, trajectory
analysis, and ecosystem imports. All of it is exposed as an **MCP server**
([`mcp/`](mcp/)) so the agent calls each function as a tool.

Every module in the **core** is **deterministic, standard-library only, and makes
no model or API calls**; inputs are never mutated (new objects are always
returned). The two `mcp_*` modules are the sole exception — they wrap the core as
MCP tools and import `mcp` + `pydantic` from the optional `[mcp]` extra, which the
core itself never imports.

## Layout

| Module / subpackage | What lives here |
| --- | --- |
| [`constants/`](constants/) | Every shared constant (all `UPPERCASE`, `Final`): pillars, the 29-criterion catalog, score scales, decisions, severities, signals, SLO fields/bands, diagnostics keys, and framework metadata. The single source of truth the rest of the package imports. |
| [`core/`](core/) | Scoring, the adaptive planner, report validation + release gate, and the end-to-end `Evaluator` orchestrator. |
| [`policy/`](policy/) | Machine-readable release **guardrail policy** — decision / safety / coverage floors, block-on-critical, a fix-attempt cap, and a sensitive-path denylist the gate enforces in CI. |
| [`operational/`](operational/) | Raw operational metrics from request traces, and SLO-based auto-scoring of the operational pillar. |
| [`diagnostics/`](diagnostics/) | Explain-and-compare modules (attribution, root cause, regression, maturity, industry profile, review gate, …) plus the `DiagnosticsBundle`. |
| [`safety/`](safety/) | Executable red-team probe battery and deterministic triage. |
| [`trajectory/`](trajectory/) | Agent tool-call trajectory evaluation. |
| [`calibration/`](calibration/) | The "eval of the eval" — scoring the judge against an oracle. |
| [`adapters/`](adapters/) | Import RAGAS / promptfoo / OpenTelemetry / LangSmith artifacts into native shapes. |
| [`cli/`](cli/) | Command-line entry points (`evalsurfer` and the `plan` / `metrics` tools). |
| [`mcp/`](mcp/) | The **MCP server** — every function above exposed as one of **47 deterministic tools** the harness LLM calls (`evalsurfer-mcp`; optional `[mcp]` extra). |
| [`mcp/models.py`](mcp/models.py) | Pydantic input schemas that give each MCP tool a validated signature (optional `[mcp]` extra). |

## Conventions

- **Absolute imports** everywhere (`from evalsurfer.core.scoring import ScoringModel`).
- **Class-based services** with `@staticmethod` / `@classmethod`; frozen dataclasses for value objects.
- **Google-style docstrings** (Args / Returns / Raises).
- **No third-party runtime dependencies in the core.** Optional extras, opt-in only: `dev` (`jsonschema`, tests), `mcp` (`mcp` + `pydantic`, the tool server), `llm` (`anthropic`, the example script).

See the [root README](../README.md) for the product overview, [`docs/mcp.md`](../docs/mcp.md)
for the tool server, and the [worked scenarios](../examples/scenarios/) for runnable
end-to-end demos.
