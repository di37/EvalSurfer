# `evalsurfer/` — the deterministic AIMAC layers

This package is EvalSurfer's deterministic implementation of the [AIMAC framework](../README.md#the-aimac-framework) — organized as the five layers Assurance · Interface · Metrics · Analysis · Core, around the skill.
The **harness LLM is the judge**; this code does everything *measurable* around
it — planning scope, assembling and validating reports, gating releases,
diagnostics, operational scoring, calibration, red-team triage, trajectory
analysis, and ecosystem imports. All of it is exposed as an **MCP server**
([`mcp/`](interface/mcp/)) so the agent calls each function as a tool.

Every module is **deterministic, standard-library only, and makes no model or API
calls**; inputs are never mutated (new objects are always returned). The
[`interface/mcp/`](interface/mcp/) package is the sole exception — it wraps the
rest as MCP tools and imports `mcp` + `pydantic` from the optional `[mcp]` extra,
which the core itself never imports.

## Layout — the five AIMAC layers

The package is organized as the five layers of the
[AIMAC framework](../README.md#the-aimac-framework), plus the shared `constants/`.

| Layer | Subpackages | What lives here |
| --- | --- | --- |
| **Core** | [`core/`](core/) · [`constants/`](constants/) | Scoring, the adaptive planner, report validation + release gate, and the end-to-end `Evaluator`; plus every shared constant (the 29-criterion catalog, scales, decisions, signals) that the rest of the package imports. |
| **Interface** | [`cli/`](interface/cli/) · [`mcp/`](interface/mcp/) · [`adapters/`](interface/adapters/) | The command-line entry points, the 47-tool **MCP server** (`evalsurfer-mcp`; optional `[mcp]` extra) with its pydantic [`models.py`](interface/mcp/models.py), and RAGAS / promptfoo / OpenTelemetry / LangSmith importers. |
| **Metrics** | [`operational/`](metrics/operational/) · [`quality/`](metrics/quality/) · [`dataset/`](metrics/dataset/) | Operational metrics + SLO auto-scoring, reference quality metrics (retrieval / match / text), and the versioned golden dataset. |
| **Analysis** | [`diagnostics/`](analysis/diagnostics/) · [`calibration/`](analysis/calibration/) | Explain-and-compare diagnostics (attribution, root cause, regression, maturity, failure map, …) plus the `DiagnosticsBundle`, and the "eval of the eval" calibration. |
| **Assurance** | [`safety/`](assurance/safety/) · [`trajectory/`](assurance/trajectory/) · [`policy/`](assurance/policy/) | Executable red-team + deterministic triage, agent tool-call trajectory evaluation, and the machine-readable release guardrail policy the gate enforces. |

## Conventions

- **Absolute imports** everywhere (`from evalsurfer.core.scoring import ScoringModel`).
- **Class-based services** with `@staticmethod` / `@classmethod`; frozen dataclasses for value objects.
- **Google-style docstrings** (Args / Returns / Raises).
- **No third-party runtime dependencies in the core.** Optional extras, opt-in only: `dev` (`jsonschema`, tests), `mcp` (`mcp` + `pydantic`, the tool server), `llm` (`anthropic`, the example script).

See the [root README](../README.md) for the product overview, [`docs/mcp.md`](../docs/mcp.md)
for the tool server, and the [worked scenarios](../examples/scenarios/) for runnable
end-to-end demos.
