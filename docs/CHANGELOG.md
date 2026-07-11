# Changelog

All notable changes to EvalSurfer are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] — Unreleased

Datasets, deterministic reference metrics, and chance-corrected judge calibration —
all additive and backward-compatible, all zero-LLM in the `evalsurfer` package. The MCP server grows from
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
  - Surfaces: `evalsurfer agreement` CLI verb, the `evalsurfer-agreement` script, and MCP
    tools `cohen_kappa` / `fleiss_kappa` / `krippendorff_alpha` / `reference_calibrate`.
- MCP server: **36 → 47 tools**. Test suite: 640 → 828 tests.

### Changed

- **Repository restructure** (developer-facing): consolidated root docs into `docs/`, moved
  the rubric + JSON schemas into `spec/`, split the monolith `constants.py` into a per-domain
  `constants/` package and `mcp_server.py` + `mcp_models.py` into an `mcp/` package (tools
  grouped by domain), mirrored `tests/` to the package layout, and **grouped the subpackages
  under five top-level groups** — `metrics/` (operational, quality, dataset), `analysis/`
  (diagnostics, calibration), `assurance/` (safety, trajectory, policy), and `interface/`
  (cli, mcp, adapters), with `constants/` and `core/` kept standalone. The top-level API
  (`evalsurfer.constants`, `evalsurfer.core`, and `evalsurfer.{ScoringModel, EvaluationPlanner,
  Signals}`) and all six pre-existing console-script names are unchanged; the grouped subpackages' import
  paths moved (e.g. `evalsurfer.diagnostics` → `evalsurfer.analysis.diagnostics`), and
  `evalsurfer-mcp` now targets `evalsurfer.interface.mcp.server:main`.
- **Rubric restructured around CIMAA** (breaking, pre-1.0): the report's `pillars` block is
  replaced by the two CIMAA layers it always described — `metrics` (the **quality** and
  **operational** categories) and `assurance` (the **safety** category). "Pillar" (and the
  short-lived "dimension") is retired throughout: `constants.PILLARS` / `PILLAR_*` →
  `CATEGORIES` / `CATEGORY_*` plus `LAYERS`; `Criterion.pillar` → `.category`; `PlannedPillar`
  → `PlannedCategory`; `ScoringModel.pillar_score` → `category_score` (new `iter_categories` /
  `category_block` helpers); the MCP tool `score_pillar` → `score_category`; and
  `report["pillars"][cat]` → `report[layer][cat]` (`report["metrics"]["quality"]`,
  `report["assurance"]["safety"]`). Scores, thresholds, and decisions are unchanged;
  `report.schema.json`, `framework.json` / `framework.yaml`, the skill (`SKILL.md` ×3), the
  examples, and the docs were all updated to match.
- **Multi-concern modules split into packages** (developer-facing): 19 modules that mixed
  value objects, a service class, and helper functions in one file (e.g. `core/planner.py`,
  `core/report.py`, `metrics/operational/metrics.py`) became focused packages
  (`models.py` · a role-named service module · `helpers.py` · a re-exporting `__init__.py`).
  Every public import path is unchanged.
- **CIMAA naming cleanup** (breaking, pre-1.0): the quality subgroup
  `core_generation_quality` / `GROUP_CORE_GENERATION` is renamed to `generation_quality` /
  `GROUP_GENERATION` (display: "Generation Quality") so it no longer collides with the
  CIMAA **Core** layer. Docs, skills, MCP tool grouping, and package READMEs now treat
  Core as planner · scoring · report · evaluate; Assurance owns `guardrail_gate` on top of
  Core's `Gate`; Metrics owns reference metrics + dataset; Analysis owns diagnostics +
  calibration.

### Fixed

- **METEOR stemming for `-ted` verbs**: the light stemmer no longer strips `-ted` as a unit
  (which turned `started` → `star`), so past-tense `-ted` verbs stem-match correctly
  (`metrics/quality/tokenize.py`).
- **Red-team PII triage no longer reports an unprovable clean pass**: a PII probe with no
  pattern match is now flagged `needs_judgment=True` (names, addresses, and non-US formats
  are not deterministically detectable) instead of `needs_judgment=False`, and the SSN
  detector also matches bare nine-digit and space/dot-separated forms
  (`assurance/safety/redteam/`).
- **Krippendorff's α returns `null` when there is no pairable data** (every unit has fewer
  than two valid ratings) instead of a misleading `1.0` "perfect agreement"
  (`analysis/calibration/agreement.py`).
- **Tail-latency ratio uses a nearest-rank P50** — consistent with the nearest-rank P99 —
  rather than the interpolated `statistics.median` (`metrics/operational/`).
- **Out-of-order request timestamps fail fast** at `RequestTrace.from_mapping` with a clear
  message instead of raising deep inside `OperationalMetrics.summarize`.
- **Unassessed evaluations report a `null` overall score** instead of a misleading `0.0`;
  `report.schema.json` now permits a null `overall.score`, matching `ReportValidator`.
- **Failure map**: a `pass_with_fixes` decision renders the Response stage as `ok`, not
  `fail` — `fail` is reserved for a `fail` decision so severity is not overstated.
- Stale schema `$id` URLs (now under `spec/`), the `PersonaAggregator` "weighted" and
  `ReviewGate` "disagreement" doc claims, an inaccurate retrieval-MRR docstring, and the
  dead `Evaluator._flatten_scores` alias.

### Notes

- Fully additive; the deterministic `evalsurfer` package still makes **zero LLM calls** and
  has **zero runtime dependencies** (the `[mcp]` extra remains optional).

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

- Three-category rubric — Application Quality / Safety / Operational (judged criteria; reference metrics are additional under Metrics).
- Adaptive planner with a coverage score; 1–5 criterion scoring → category score ×2 (0–10)
  → `pass` / `pass_with_fixes` / `fail`, with a safety floor and critical override.
- Diagnostics: SHAP-style score attribution, root-cause breakdown, regression diff,
  maturity level, industry weighting profiles, Analysis `ReviewGate` (human-review), personas, failure map,
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
  zero-dependency `evalsurfer` package.

[0.1.3]: https://github.com/di37/EvalSurfer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/di37/EvalSurfer/releases/tag/v0.1.0
