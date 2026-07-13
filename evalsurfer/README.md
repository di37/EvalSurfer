# `evalsurfer/` — the deterministic CIMAA layers

This package is EvalSurfer's deterministic implementation of the [CIMAA framework](../README.md#the-cimaa-framework) — organized as the five layers Core · Interface · Metrics · Analysis · Assurance, around the skill.
The **harness LLM is the judge**; this code does everything *measurable* around
it — planning scope, assembling and validating reports, gating releases,
diagnostics, operational scoring, calibration, red-team triage, trajectory
analysis, and ecosystem imports. All of it is exposed as an **MCP server**
([`mcp/`](interface/mcp/)) so the agent calls each function as a tool.

Every module is **deterministic, standard-library only, and makes no model or API
calls**; inputs are never mutated (new objects are always returned). The
[`interface/mcp/`](interface/mcp/) package is the sole exception — it wraps the
rest as MCP tools and imports `mcp` + `pydantic` from the optional `[mcp]` extra,
which the rest of the `evalsurfer` package never imports.

## Layout — the five CIMAA layers

The package is organized as the five layers of the
[CIMAA framework](../README.md#the-cimaa-framework), plus the shared `constants/`
catalog (package-wide — not Core-owned).

| Layer | Subpackages | What lives here |
| --- | --- | --- |
| **Core** | [`core/`](core/) | CIMAA **Core**: `planner/`, `scoring`, `report/` (`ReportValidator`, `Gate`), `evaluate` (assemble only). |
| **Interface** | [`pipeline.py`](interface/pipeline.py) · [`cli/`](interface/cli/) · [`mcp/`](interface/mcp/) · [`adapters/`](interface/adapters/) | CIMAA **Interface**: full-run pipeline (Metrics enrich → Core → Analysis), CLI, 48-tool MCP server, adapters. |
| **Metrics** | [`operational/`](metrics/operational/) · [`quality/`](metrics/quality/) · [`dataset/`](metrics/dataset/) | CIMAA **Metrics**: operational + SLO, reference quality metrics, eval golden dataset (≠ Analysis `GoldenSet`). |
| **Analysis** | [`diagnostics/`](analysis/diagnostics/) · [`calibration/`](analysis/calibration/) | CIMAA **Analysis**: diagnostics (incl. `ReviewGate`), judge calibration. |
| **Assurance** | [`safety/`](assurance/safety/) · [`trajectory/`](assurance/trajectory/) · [`policy/`](assurance/policy/) | CIMAA **Assurance**: red-team + PII, trajectory, `guardrail_gate` policy on Core's `Gate`. |
| *(shared)* | [`constants/`](constants/) | Rubric catalog (Quality / Operational / Safety), scales, decisions — used by all layers. |

## Conventions

- **Absolute imports** everywhere (`from evalsurfer.core.scoring import ScoringModel`).
- **Class-based services** with `@staticmethod` / `@classmethod`; frozen dataclasses for value objects.
- **Google-style docstrings** (Args / Returns / Raises).
- **No third-party runtime dependencies in the `evalsurfer` package** (outside optional extras). Opt-in: `dev` (`jsonschema`, tests), `mcp` (`mcp` + `pydantic`, the tool server), `llm` (`anthropic`, the example script).

See the [root README](../README.md) for the product overview, [`docs/mcp.md`](../docs/mcp.md)
for the tool server, and the [worked scenarios](../examples/scenarios/) for runnable
end-to-end demos.
