# CIMAA alignment inconsistencies

Audit of places where EvalSurfer docs, package layout, or code blur CIMAA layer
ownership. Check off items as they are fixed.

CIMAA layers (for reference):

| Letter | Layer | Owns |
| --- | --- | --- |
| C | Core | planner · scoring · report (`ReportValidator`, `Gate`) · evaluate (assemble) |
| I | Interface | skill · MCP · CLI · adapters · `pipeline` · MCP/CLI `evaluate` (full run) |
| M | Metrics | operational / SLO · reference quality metrics · eval golden dataset |
| A | Analysis | diagnostics · calibration · `ReviewGate` · framework `GoldenSet` |
| A | Assurance | red-team · trajectory · `guardrail_gate` / guardrail policy |

---

## A–G. Prior passes — closed (items 1–88)

Import firewall, Interface-owned full `evaluate`, nested MCP tools, Quality≠Metrics,
47-tool counts, adapters under `tools/interface/`, quality `report.py` in Metrics, etc.

---

## H. Fifth audit (2026-07-11) — fixed

### Examples / tutorial “assemble” shorthand

- [x] **89.** `examples/mcp/README.md` — “Full run — `evaluate`” with pipeline order.
- [x] **90.** `examples/to_judge/README.md` — Interface pipeline wording.
- [x] **91.** `examples/README.md` §3 title — Interface pipeline.
- [x] **92.** `examples/judge/README.md` diagram — Interface pipeline report.
- [x] **93.** `examples/judge/README.md` Step 2 — full-run wording.
- [x] **94.** `examples/README.md` §1 Path B — Interface pipeline.
- [x] **95.** Root README MCP workflow —
  `scope → judge → Interface evaluate → gate / guardrail_gate`.

### Docstrings — unqualified “the gate”

- [x] **96.** `assurance/policy/__init__.py` — Assurance `guardrail_gate`.
- [x] **97.** `constants/policy.py` — Assurance wording.
- [x] **98.** `guardrails/models.py` — Assurance `Guardrails` / `guardrail_gate`.

Also cleaned: `guardrails/__init__.py`, `llm_judge.py`, `scenarios/_lib.sh`.

---

## I. Sixth audit (2026-07-11) — fixed

### Quality rubric ≠ Metrics layer

- [x] **99.** `evalsurfer/constants/categories.py` — docstring/comments clarify
  `LAYER_*` / `LAYER_BY_CATEGORY` as **report section nesting**, not CIMAA
  ownership (quality agent-judged / Core-assembled; Metrics = reference + ops).

### Interface `evaluate` grouping

- [x] **100.** `evalsurfer/interface/mcp/server.py` — `__all__` splits Interface
  full-run `evaluate` from Core assemble / gate.

---

## J. Seventh audit (2026-07-11) — fixed

### Report nesting still described as layer ownership

- [x] **101.** `evalsurfer/core/scoring.py` — `category_block` says the CIMAA
  layer “assesses” the category; it should say report section nesting.
- [x] **102.** `evalsurfer/core/planner/models.py` — `EvaluationPlan.to_dict`
  repeats “layer that assesses them” for `metrics` / `assurance` report keys.
- [x] **103.** `evalsurfer/core/report/validator.py` — validation contract says
  layer blocks carry categories “they assess”; these are report sections.
- [x] **104.** `tests/analysis/diagnostics/test_explainability.py` — helper
  docstring repeats the stale ownership wording.
- [x] **105.** `tests/analysis/diagnostics/test_root_cause.py` — same stale
  helper wording.
- [x] **106.** `tests/analysis/diagnostics/test_review_gate.py` — same stale
  helper wording.

### Release metadata

- [x] **107.** Citation sources disagree: `CITATION.cff` correctly tracks the
  latest tagged release (`v0.1.0`), while README's direct BibTeX cites the
  unreleased development version `0.1.3`. Decide release-vs-development
  citation policy and add `CITATION.cff` to `docs/RELEASING.md`.

### Naming and Interface parity

- [x] **108.** `evalsurfer/metrics/dataset/{dataset,contamination}.py` — Metrics
  calls its eval dataset a “golden set”, colliding with Analysis `GoldenSet`;
  consistently use **golden dataset** for the Metrics artifact.
- [x] **109.** `evalsurfer/interface/cli/main.py` — CLI `diagnose` cannot pass
  maturity `signals`, while the MCP `diagnose` surface can.
- [x] **110.** `evalsurfer/analysis/diagnostics/profiles.py` — broken Sphinx
  reference `scoring.ScoringModel.overall_score` lacks the importable module
  path.

### Root documentation

- [x] **111.** `README.md` report section — calls `metrics.*` / `assurance.*`
  “CIMAA layer” nesting despite those being report section keys.
- [x] **112.** `README.md` repository map — says `spec/framework.*` defines
  “CIMAA layers”; its `metrics` / `assurance` fields define report nesting.
- [x] **113.** `README.md` Metrics chapter — “two measured categories” includes
  agent-judged Quality, blurring Quality with Metrics measurement.

### Agent-facing skill catalog

- [x] **114.** All three `SKILL.md` copies — Core MCP list omits `coverage`.
- [x] **115.** All three `SKILL.md` copies — Metrics MCP list omits
  `cost_per_request` and `token_efficiency`.
- [x] **116.** All three `SKILL.md` copies — “helpers by CIMAA layer” lists
  only Core, Interface, and Analysis; add Metrics and Assurance helpers.

### Spec, safety examples, and enforcement

- [x] **117.** `spec/framework.{json,yaml}` — four red-team cases use IDs and
  prompts that differ from Assurance `RedTeam.CASES`, which has six cases
  (including PII and discriminatory-ranking probes).
- [x] **118.** `README.md` safety red-team table — its six prompts/expected
  behaviors do not match the executable Assurance case battery; either share
  the canonical cases or label the table as illustrative.
- [x] **119.** `evalsurfer/interface/cli/main.py` — module docstring claims to
  enumerate every verb but omits `quality`, `dataset`, and `agreement`.
- [x] **120.** `evalsurfer/interface/cli/README.md` — console-script table
  omits `evalsurfer-quality`, `evalsurfer-dataset`, and `evalsurfer-mcp`.
- [x] **121.** Tests do not enforce three documented consistency guarantees:
  Core's import firewall, `framework.json` ↔ `framework.yaml` parity, or
  framework red-team cases ↔ `RedTeam.CASES` parity.

---

## K. Eighth audit (2026-07-11) — fixed

- [x] **122.** All three `SKILL.md` copies now route agents to the canonical
  six-case `redteam_template` battery, including PII and bias probes.
- [x] **123.** Root README documents `diagnose --signals` for maturity.
- [x] **124.** Analysis diagnostics README documents `--signals` / `--before`.
- [x] **125.** README's direct BibTeX title now matches `CITATION.cff`.
- [x] **126.** Verified test count updated from 815 to 820.
- [x] **127.** Tracker status and footer updated after the eighth pass.

Also fixed during review: strict wrapped Signals validation, raw-sample
disambiguation, Interface coverage in the Core import firewall, typing stubs,
and Black/Ruff formatting.

---

## Verified still true

- [x] Core → no Interface/Metrics/Analysis/Assurance imports.
- [x] Skills byte-identical; MCP nested by layer.
- [x] Gates / ReviewGate / guardrail_gate disambiguated in docs.
- [x] 47 tools; no stale test dirs; MCP tools do not import CLI.
- [x] Full suite: 820 tests pass.
- [x] No open items.

---

*Last audited: 2026-07-11 (eighth pass). All items 1–127 closed.*
