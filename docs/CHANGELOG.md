# Changelog

All notable changes to EvalSurfer are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] — Unreleased

Datasets, deterministic reference metrics, and chance-corrected judge calibration —
all additive and backward-compatible, all zero-LLM-core. The MCP server grows from
36 to **47 tools**.

### Added

- **Golden dataset artifact** (`evalsurfer/metrics/dataset/`): a versioned `Dataset` of
  content-hashed `DatasetCase`s with coverage tags (`normal` / `difficult` / `edge` /
  `random`), a deterministic (salted-hash, no RNG) held-out split, trace harvesting
  (`from_traces`), version-to-version `diff`, and contamination controls (content-hash
  duplicates, blocklist, and canary hits). Ships `spec/dataset.schema.json`.
  - Surfaces: `evalsurfer dataset` CLI verb, the `evalsurfer-dataset` script, and MCP
    tools `dataset_from_traces` / `dataset_diff` / `dataset_contamination` /
    `dataset_coverage`.
- **Deterministic quality metrics** (`evalsurfer/metrics/quality/`) — reference-based and
  zero-LLM: retrieval (Recall@k / Precision@k / MRR, plus tool-selection recall),
  match & classification (exact match, token-F1, accuracy, per-label precision / recall /
  F1 with macro / micro / binary averaging), and reference-text (BLEU, ROUGE-N, ROUGE-L,
  METEOR).
  - Surfaces: `evalsurfer quality` CLI verb, the `evalsurfer-quality` script, and MCP
    tools `retrieval_metrics` / `match_metrics` / `text_metrics`.
- **Chance-corrected agreement & judge-vs-human calibration**
  (`evalsurfer/analysis/calibration/agreement.py`, `evalsurfer/analysis/calibration/reference.py`): Cohen's
  κ, Fleiss's κ, Krippendorff's α (nominal), mean absolute error, and Spearman rank
  correlation — the rigorous replacement for raw agreement, which is ~50% by chance on a
  binary call.
  - Surfaces: `evalsurfer agreement` CLI verb and MCP tools `cohen_kappa` / `fleiss_kappa`
    / `krippendorff_alpha` / `reference_calibrate`.
- MCP server: **36 → 47 tools**. Test suite: 640 → 815 tests.

### Changed

- **Repository restructure** (developer-facing): consolidated root docs into `docs/`, moved
  the rubric + JSON schemas into `spec/`, split the monolith `constants.py` into a per-domain
  `constants/` package and `mcp_server.py` + `mcp_models.py` into an `mcp/` package (tools
  grouped by domain), mirrored `tests/` to the package layout, and **grouped the subpackages
  under five top-level groups** — `metrics/` (operational, quality, dataset), `analysis/`
  (diagnostics, calibration), `assurance/` (safety, trajectory, policy), and `interface/`
  (cli, mcp, adapters), with `constants/` and `core/` kept standalone. The top-level API
  (`evalsurfer.constants`, `evalsurfer.core`, and `evalsurfer.{ScoringModel, EvaluationPlanner,
  Signals}`) and all six console-script names are unchanged; the grouped subpackages' import
  paths moved (e.g. `evalsurfer.diagnostics` → `evalsurfer.analysis.diagnostics`), and
  `evalsurfer-mcp` now targets `evalsurfer.interface.mcp.server:main`.

### Notes

- Fully additive; the deterministic core still makes **zero LLM calls** and has **zero
  runtime dependencies** (the `[mcp]` extra remains optional).

## [0.1.2] — 2026-07-09

### Changed

- CI publish is idempotent: PyPI uses skip-existing and npm skips when the version is
  already published, so re-runs never fail.
- The npm publish step is best-effort (`continue-on-error`) so npm flakiness never reds a
  release.

### Added

- PyPI and npm version badges in the README.

## [0.1.1] — 2026-07-09

### Fixed

- `.gitignore` no longer excludes `npm/bin/cli.js`, so the npm package ships its CLI shim.
- Synced package versions to 0.1.1 across PyPI and npm.

## [0.1.0] — 2026-07-09

Initial release.

### Added

- Three-pillar rubric — Application Quality / Safety / Operational (29 criteria).
- Adaptive planner with a coverage score; 1–5 criterion scoring → pillar score ×2 (0–10)
  → `pass` / `pass_with_fixes` / `fail`, with a safety floor and critical override.
- Diagnostics: SHAP-style score attribution, root-cause breakdown, regression diff,
  maturity level, industry weighting profiles, human-review gate, personas, failure map,
  and a golden self-test.
- Operational metrics from request traces, plus SLO-based operational auto-scoring.
- Judge calibration ("eval of the eval"): agreement, false-pass / false-fail rate, and
  score variance across repeated judge runs.
- Executable red-team probe templates with deterministic PII detection, and
  agent-trajectory diffs (missing / unnecessary / out-of-order tools, bad params, error
  recovery).
- Ecosystem adapters (RAGAS / promptfoo / OpenTelemetry / LangSmith) and a CI-gate GitHub
  Action; a machine-readable release guardrail policy.
- A 36-tool MCP server and a portable [agentskills.io](https://agentskills.io) skill
  (Claude Code, Cursor, and other compatible harnesses), console scripts, and a
  zero-dependency core.

[0.1.3]: https://github.com/di37/EvalSurfer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/di37/EvalSurfer/releases/tag/v0.1.0
