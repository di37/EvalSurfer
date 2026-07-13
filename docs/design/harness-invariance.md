# Design: Harness-Invariant Judgment Reliability (HIJR)

**Status:** implemented (`evalsurfer/analysis/calibration/harness/`, the
`harness_invariance` MCP tool, and the `evalsurfer harness-invariance` CLI verb;
test anchor: `tests/analysis/calibration/test_harness.py`). §10's "published
Brennan example" cross-check was replaced by an equivalent model-recovery test
(the anchor fixture is constructed from known effects, which the estimators must
recover exactly) — no textbook dataset was available to cite honestly.
Post-review amendments: a top-level `notes` array carries every promised
caveat/reason (confounded design, Φ(λ) optimism, unattainable recommendation,
partial rank-correlation coverage); per-target `weighted_flip` implemented;
invalid decisions counted **and named** in `decisions.invalid` (non-string
decisions preserved via `str()` rather than dropped); duplicate criterion ids
across report sections rejected; D-study caps bounded by `DSTUDY_MAX_LIMIT`;
`harness_diagnostics.rank_correlation_pairs` exposes partial coverage.
**Layer:** Analysis (`evalsurfer/analysis/calibration/harness/`).
**Surfaces:** one MCP tool (`harness_invariance`), one CLI verb (`evalsurfer harness-invariance`), one Python import.
**Invariants preserved:** zero LLM calls, zero runtime dependencies, frozen value objects, stateless service, inputs never mutated, fail-fast validation at the boundary.

---

## 1. What this is, and the exact claim it makes

When the same portable rubric (`SKILL.md`) judges the same targets in different
harnesses (Claude Code, Cursor, Codex, …), the verdicts differ for three
distinct reasons:

1. the **targets** genuinely differ in quality (the signal we want),
2. the **harnesses** systematically differ (severity, tool access, context handling),
3. the **same harness disagrees with itself** across repeated runs (stochasticity).

HIJR is a deterministic variance decomposition that separates these three
sources from a `target × harness × replication` grid of EvalSurfer reports, and
turns them into: one dependability coefficient for the release gate, a
"how many harnesses × runs do you need" prescription, and a per-criterion
profile of which rubric criteria are harness-sensitive (the rubric-hardening
loop).

### The claim, positioned honestly against prior art

We do **not** claim to be first to apply ICC / Generalizability Theory to LLM
judges. That is published, and Related Work must cite it head-on:

| Prior art | What it already does | What it does not do |
| --- | --- | --- |
| Song, Lee & Jiao, [arXiv 2507.19980](https://arxiv.org/abs/2507.19980) (+ Elsevier companion) | G-theory with **seven LLM systems as a random rater facet**, same rubric, target-vs-rater variance separation, G- and D-studies | Raters are bare models scoring essays; no agent scaffold, no replication facet, rubric implementation not held byte-identical |
| Mustahsan et al., [arXiv 2512.06710](https://arxiv.org/abs/2512.06710) | ICC for **agentic** evaluation; targets × **replications** of a single system | One system at a time — no between-system facet; judge variance explicitly not decomposed |
| Siro et al., [arXiv 2602.08672](https://arxiv.org/html/2602.08672v1) (EACL 2026) | Cross-**model** judge ICC under a shared rubric; the thesis that judgment reflects the judging system | No replication facet, no variance decomposition into components, models ≠ harnesses |
| Tang et al., [arXiv 2604.12227](https://arxiv.org/abs/2604.12227) | ICC with an LLM as an added rater; **per-criterion ICC profiles** | Single LLM; cross-system deferred to future work |

What is **not** instantiated anywhere in the surveyed literature, and is the
contribution:

1. **The rater facet is the harness** — the full agent scaffold (model + tools +
   context handling + orchestration), not a bare model.
2. **Both facets in one crossed design** — between-harness variance *and*
   within-harness run stochasticity are separated in a single
   `p × h × r` decomposition. 2507.19980 has systems but no replications;
   2512.06710 has replications but one system.
3. **The facet is well-defined by construction.** In all prior work, changing
   the judge system also changed the prompt/rubric implementation, confounding
   the facet. EvalSurfer's skill-parity test enforces a byte-identical rubric
   across harnesses, so "harness" varies while the rubric provably does not.
4. **Gate-level dependability at the actual cut scores.** The decision
   thresholds (6.5 / 8.0 on the 0–10 overall) are explicit constants, so we
   report criterion-referenced dependability **Φ(λ)** at exactly the lines that
   gate releases — not just a generic coefficient.

What we explicitly do **not** lean on for novelty: "zero model calls." All
post-hoc G-theory is computed deterministically over already-collected scores;
it remains EvalSurfer's product property, not a research differentiator.

Terminology note: "harness-invariant" / "harness as a variance facet" is
unclaimed vocabulary in the surveyed literature; use it consistently.

---

## 2. Data model

### Input: a judgment grid

One judgment = one EvalSurfer report produced by harness *h* judging target *t*
on replication *r*, all running the byte-identical skill. The tool accepts the
reports EvalSurfer already emits — no new judging output format.

```json
{
  "judgments": [
    {
      "target": "sample-014",
      "harness": "claude-code",
      "replication": 1,
      "report": { "overall": {"score": 7.8, "decision": "pass_with_fixes"}, "...": "..." }
    }
  ],
  "dependability_target": 0.8,
  "dstudy_max_harnesses": 5,
  "dstudy_max_replications": 5
}
```

- `report` may be a full report (projected via the existing `ScoringModel`
  traversal helpers — no new report-walking code) or a pre-projected slim record
  `{"score": <0-10>, "decision": <...>, "criteria": {cid: 1-5|null}}`.
- `target`, `harness` are opaque non-empty strings; `replication` a positive int.

### Design requirements (fail-fast, v1)

| Rule | Rationale |
| --- | --- |
| ≥ 2 targets, ≥ 2 harnesses | Below this no between-facet variance is estimable |
| **Complete crossed grid**: every `(target, harness)` cell present | The expected-mean-squares estimators below are exact only for balanced designs |
| **Equal replication count `n_r` per cell** (n_r ≥ 1) | Same; unbalanced designs need REML (out of scope, §12) |
| `overall.score` non-null and numeric in every judgment | A null overall cannot be decomposed; reject with the offending `(target, harness, replication)` named |
| Duplicate `(t, h, r)` keys rejected | Ambiguous cell contents |

Violations raise `ValueError` with a message naming the exact hole in the grid
(matching the boundary-validation style of `RequestTrace.from_mapping`).

---

## 3. The statistical model

Two-facet crossed random-effects design with replications within cells —
`p × h` with `r` observations per cell, where `p` indexes targets ("persons" in
G-theory), `h` harnesses:

```
X_thr = μ + τ_t + η_h + (τη)_th + e_thr
```

| Component | Symbol | Meaning |
| --- | --- | --- |
| Target (universe score) | σ²_t | Real quality differences between targets — the signal |
| Harness main effect | σ²_h | Systematic severity/leniency differences between harnesses |
| Target × harness interaction | σ²_th | Harnesses *rank targets differently* — the damaging component |
| Replication (residual) | σ²_e | Same harness, same target, different run |

### Estimation (standard two-way ANOVA expected mean squares)

With `n_t` targets, `n_h` harnesses, `n_r` replications per cell, cell means
`x̄_th`, marginal means `x̄_t·`, `x̄_·h`, grand mean `x̄`:

```
SS_t  = n_h·n_r·Σ_t (x̄_t· − x̄)²                    df = n_t − 1
SS_h  = n_t·n_r·Σ_h (x̄_·h − x̄)²                    df = n_h − 1
SS_th = n_r·Σ_{t,h} (x̄_th − x̄_t· − x̄_·h + x̄)²      df = (n_t−1)(n_h−1)
SS_e  = Σ_{t,h,r} (x_thr − x̄_th)²                   df = n_t·n_h·(n_r−1)

σ̂²_e  = MS_e
σ̂²_th = (MS_th − MS_e) / n_r
σ̂²_h  = (MS_h − MS_th) / (n_t·n_r)
σ̂²_t  = (MS_t − MS_th) / (n_h·n_r)
```

- **Negative estimates are clamped to 0** (standard practice) and reported in a
  `clamped: [...]` list — never silently.
- **`n_r = 1` degradation:** σ²_th and σ²_e are confounded. The result reports a
  single `residual` component, sets `replication: null` and
  `interaction: null`, and flags `"confounded": true`, appending the reason to
  the top-level `notes` array (a study with `n_r ≥ 2` is required to separate
  them). This degraded mode is the
  classic two-way ICC (McGraw & Wong ICC(2,1)-agreement corresponds to
  σ²_t / (σ²_t + σ²_h + σ²_residual)) — one line in the output makes that
  correspondence explicit for reviewers.
- All shares/coefficients rounded to `SHARE_PRECISION` (3); means to
  `SCORE_PRECISION` (1). Pure `statistics` + arithmetic — no numpy.

### Outputs from this stage

```json
{
  "design": {"targets": 24, "harnesses": 4, "replications": 3, "balanced": true},
  "grand_mean": 7.2,
  "variance_components": {"target": 1.84, "harness": 0.21, "interaction": 0.34, "replication": 0.42, "clamped": []},
  "shares": {"target": 0.655, "harness": 0.075, "interaction": 0.121, "replication": 0.149}
}
```

`shares.target` is the headline "harness invariance" number: the fraction of
score variance that is a property of the *target* rather than of who judged it
or when.

---

## 4. Coefficients and the D-study

For a hypothetical deployment with `n'_h` harnesses and `n'_r` replications
each (scores averaged):

```
relative error   σ²_δ = σ²_th/n'_h + σ²_e/(n'_h·n'_r)
absolute error   σ²_Δ = σ²_h/n'_h + σ²_th/n'_h + σ²_e/(n'_h·n'_r)

Generalizability (norm-referenced)  Eρ² = σ²_t / (σ²_t + σ²_δ)
Dependability (criterion-referenced) Φ   = σ²_t / (σ²_t + σ²_Δ)
```

**Gate dependability at the cut scores (Brennan–Kane Φ_λ):** EvalSurfer's
decisions hinge on absolute thresholds — `FAIL_OVERALL_THRESHOLD = 6.5`,
`PASS_OVERALL_THRESHOLD = 8.0` — so we report

```
Φ(λ) = (σ²_t + (μ̂ − λ)²) / (σ²_t + (μ̂ − λ)² + σ²_Δ)      for λ ∈ {6.5, 8.0}
```

read directly from the same constants the scoring model uses. Caveat appended to the
top-level `notes` array: using the estimated μ̂ makes Φ(λ) slightly optimistic (the unbiased
correction is a §12 refinement).

**D-study grid:** compute Eρ² and Φ for `n'_h ∈ 1..dstudy_max_harnesses` ×
`n'_r ∈ 1..dstudy_max_replications`, and report the cheapest `(n'_h, n'_r)`
(fewest total runs, ties → fewer harnesses) reaching `dependability_target`
(default 0.8):

```json
{
  "coefficients": {"generalizability": 0.87, "dependability": 0.83, "dependability_at_cuts": {"6.5": 0.91, "8.0": 0.85}},
  "dstudy": [{"harnesses": 1, "replications": 1, "generalizability": 0.65, "dependability": 0.58}, ...],
  "recommended": {"harnesses": 2, "replications": 2, "dependability": 0.82, "target": 0.8}
}
```

If no grid point reaches the target, `recommended` is `null` and the reason is
appended to the top-level `notes` array — never a silent best-effort. If `σ²_t = 0` (all targets identical), every
coefficient is **`null`** (undefined — no signal to generalize), mirroring the
Krippendorff-α `None` convention; never a fake 1.0 or 0.0.

---

## 5. Decision-level analysis (pass / pass_with_fixes / fail)

Variance decomposition on the 0–10 score does not directly answer "does the
*verdict* flip?". Deterministic categorical companions, reusing existing code:

- **Per-target:** modal decision across all `(h, r)`; `flip_rate` = fraction of
  judgments differing from the mode; `weighted_flip` uses the existing
  `DECISION_RANK` band distance (`fail↔pass` = 2, adjacent = 1).
- **Between-harness agreement:** existing `AgreementStats.fleiss_kappa` over
  per-harness modal decisions (harnesses as raters, targets as items).
- **Attribution without a latent model:** two empirical probabilities —
  `P(flip | same harness, different replication)` vs
  `P(flip | different harness)` — computed over all pairs. If the second is
  much larger, verdict instability is harness-driven, not stochastic. A full
  categorical variance decomposition (threshold/latent-trait model) is out of
  scope (§12); these probabilities are honest and assumption-free.

```json
{"decisions": {"fleiss_kappa": 0.71, "mean_flip_rate": 0.11,
  "p_flip_within_harness": 0.06, "p_flip_between_harness": 0.19,
  "per_target": [{"target": "sample-014", "modal": "pass_with_fixes", "flip_rate": 0.25, "weighted_flip": 0.5}], "invalid": []}}
```

---

## 6. Per-criterion invariance profile (the rubric-hardening loop)

The same `p × h × r` decomposition runs per criterion on its 1–5 scores.
Because the planner legitimately skips criteria per target, per-criterion grids
are subsets:

- A criterion is profiled over the targets where it was assessed in **every**
  `(h, r)` judgment (the complete subgrid). Targets partially assessed for that
  criterion are dropped *for that criterion's profile only* and counted in
  `dropped_targets`.
- If the surviving subgrid has < 2 targets, the criterion is `skipped` with the
  reason — never silently absent.
- A criterion is flagged `harness_sensitive` when its harness-linked share
  exceeds `HARNESS_SENSITIVITY_SHARE` (constant, default 0.25):
  `shares.harness + shares.interaction > 0.25`.

```json
{"criteria": [
  {"id": "groundedness_faithfulness", "shares": {"target": 0.71, "harness": 0.04, "interaction": 0.10, "replication": 0.15}, "harness_sensitive": false},
  {"id": "citation_accuracy", "shares": {"target": 0.31, "harness": 0.22, "interaction": 0.29, "replication": 0.18}, "harness_sensitive": true, "dropped_targets": 3}
]}
```

The actionable loop, documented in the skill and README: a `harness_sensitive`
criterion is a rubric defect — reword its instructions, back it with a
deterministic Metrics check, or route it to multi-judge/human review via
`ReviewGate`. Re-run the study; the share should fall. *(Per-criterion ICC
profiling exists in 2604.12227 — the novelty here is only the harness facet and
the hardening loop, and the doc says so.)*

---

## 7. Facet diagnostics — the exchangeability question, answered honestly

Treating harness as a *random* facet assumes the studied harnesses are
exchangeable samples from a universe of harnesses. With κ ≈ 3–5 harnesses this
is not statistically testable, and harness tool/context differences may violate
it. We do not hand-wave this; we report both interpretations plus the
diagnostics a reader needs:

1. **Random-facet view** (default): Eρ², Φ as in §4 — "generalizing to
   harnesses like these."
2. **Fixed-facet view**: when you only ever deploy these exact harnesses,
   σ²_h averages out and σ²_th/n_h folds into the universe score
   (`σ²_t* = σ²_t + σ²_th/n_h`); report the corresponding Φ_fixed — always ≥ the
   random-facet Φ, with a plain-English note on which question each answers.
3. **Severity vs. disagreement split:** per-harness marginal means (is a
   harness systematically harsher — calibratable) vs. the σ²_th share (do
   harnesses *rank targets differently* — not fixable by offset calibration).
4. **Rank stability:** mean pairwise Spearman ρ between per-harness target
   rankings, reusing the tie-aware rank correlation already in
   `analysis/calibration/reference.py` (promote the private `_spearman` to a
   shared helper rather than duplicating it).

```json
{"harness_diagnostics": {
  "per_harness_mean": {"claude-code": 7.4, "cursor": 6.9, "codex": 7.3},
  "mean_rank_correlation": 0.83,
  "rank_correlation_pairs": {"defined": 3, "total": 3},
  "fixed_facet_dependability": 0.88,
  "note": "random-facet Φ generalizes to unseen harnesses; fixed-facet Φ applies only to these three"
}}
```

---

## 8. Module layout & API

Follows the restructure convention (frozen models / stateless service /
helpers / re-exporting `__init__`):

```
evalsurfer/analysis/calibration/harness/
  __init__.py          # re-exports HarnessInvariance + value objects
  models.py            # frozen: Judgment, DesignSummary, VarianceComponents,
                       #         DStudyPoint, CriterionProfile, HarnessResult
  decomposition.py     # HarnessInvariance service (all @staticmethod)
  helpers.py           # grid validation, projection from full reports
                       # (via ScoringModel), sums-of-squares, EMS solvers
```

Public API (stateless, namespace-style like `ScoringModel` / `AgreementStats`):

```python
HarnessInvariance.analyze(payload: Mapping) -> dict
    # full result: design, variance_components, shares, coefficients,
    # dstudy, recommended, decisions, criteria, harness_diagnostics
HarnessInvariance.decompose(grid) -> VarianceComponents          # the core math, reusable
HarnessInvariance.dstudy(components, *, max_h, max_r, target) -> list[DStudyPoint]
```

### Constants (`evalsurfer/constants/calibration.py` additions)

```python
METRIC_HARNESS_INVARIANCE: Final = "harness_invariance"
FACET_TARGET / FACET_HARNESS / FACET_INTERACTION / FACET_REPLICATION  # output keys
DEFAULT_DEPENDABILITY_TARGET: Final = 0.8
HARNESS_SENSITIVITY_SHARE: Final = 0.25
DSTUDY_MAX_HARNESSES: Final = 5
DSTUDY_MAX_REPLICATIONS: Final = 5
DSTUDY_MAX_LIMIT: Final = 100        # upper bound on caller-supplied caps (grid is materialized)
# Cut scores reuse constants/scoring.py: FAIL_OVERALL_THRESHOLD, PASS_OVERALL_THRESHOLD
```

### Surfaces

- **MCP:** one new tool `harness_invariance` in
  `interface/mcp/tools/analysis/calibration.py` (pydantic input model with
  `extra="allow"` reports, delegating to `HarnessInvariance.analyze`).
  **Tool count 47 → 48** — blast radius below.
- **CLI:** new verb `evalsurfer harness-invariance study.json [--pretty]`
  in `interface/cli/main.py` (+ handler module `cli/harness.py` exposing
  `build_report()` per the established CLI reuse pattern). No new console
  script — the unified verb suffices for a study-analysis command.
- **Python:** `from evalsurfer.analysis.calibration.harness import HarnessInvariance`.

### Doc blast radius (the "47 tools" sweep)

The tool count is asserted or stated in: `tests/interface/mcp/test_mcp_server.py`
(`_TOOLS` set — the CI gate), `README.md` (~4 places), `docs/mcp.md`,
`CITATION.cff` abstract, `npm/README.md`, `.github/workflows/README.md`,
`skills/eval-surfer/SKILL.md` ×3 (byte-parity enforced — edit the canonical one
and re-stage), `evalsurfer/interface/mcp/README.md`, ROADMAP, CHANGELOG. All
must move 47 → 48 in the same commit or CI fails (by design).

---

## 9. Validation & failure modes (fail-fast catalogue)

| Condition | Behavior |
| --- | --- |
| non-mapping payload / judgment | `TypeError` |
| < 2 targets or < 2 harnesses | `ValueError` naming the shortfall |
| incomplete grid | `ValueError` listing missing `(target, harness)` cells (up to 10, then "+N more") |
| unequal replications | `ValueError` with the offending cells and counts |
| duplicate `(t,h,r)` | `ValueError` naming the key |
| null / non-numeric overall score | `ValueError` naming the judgment |
| unknown `decision` values | excluded from §5, counted and named per judgment in `decisions.invalid`; §3–4 unaffected |
| all scores identical (σ²_t = 0) | components computed; coefficients `null` (undefined, not 1.0) |
| `n_r = 1` | confounded mode (§3), flagged, never silently wrong |
| negative variance estimate | clamped to 0, listed in `clamped` |

---

## 10. Test plan (TDD — tests first)

`tests/analysis/calibration/test_harness.py`, mirroring the suite layout:

1. **Hand-computed fixture (the anchor):** a 3 targets × 2 harnesses × 2 reps
   grid with integer scores whose SS/MS/σ² are derived by hand in comments
   (same style as `GoldenSet` and the Krippendorff tests). Asserts every
   component, share, Eρ², Φ, and Φ(6.5)/Φ(8.0) to 3 decimals.
2. **Textbook cross-check:** a published two-facet G-study example (Brennan,
   *Generalizability Theory*, synthetic data) reproduced to published values —
   external validation the reviewers can re-run.
3. **Degradations:** `n_r = 1` → confounded mode; σ²_t = 0 → null coefficients;
   negative component → clamped + listed; ICC(2,1) correspondence in the
   confounded mode against a hand value.
4. **Fail-fast:** every row of the §9 table.
5. **Decision level:** constructed flips where within-harness pairs agree and
   between-harness pairs flip → `p_flip_between > p_flip_within`; Fleiss κ
   against the existing implementation.
6. **Criterion profile:** planner-skipped criteria produce the documented
   subgrid/skip behavior; `harness_sensitive` threshold boundary (share =
   0.25 exactly → not flagged; strictly above → flagged).
7. **Immutability & projection:** payload deep-compared before/after; full
   reports and slim records produce identical results.
8. **Surfaces:** MCP tool registers (`_TOOLS` 48) and round-trips; CLI verb
   exits 0/1 correctly.

Estimated ≈ 45–60 new tests.

---

## 11. What this asks of the cross-harness study (protocol requirements)

The empirical study and this method are one package; the study design must
satisfy the estimators:

1. **`n_r ≥ 2` replications per (target, harness) — non-negotiable.** With one
   run per cell, harness-disagreement and run-noise are mathematically
   inseparable (§3). Recommend `n_r = 3`.
2. **Complete grid:** every harness judges every target. Pick the target set
   *after* confirming all harnesses can access it (no harness-specific tooling
   in the samples).
3. **Sizing for stable components:** with κ = 4–5 harnesses, n_t ≥ 20–30
   targets gives the interaction term reasonable degrees of freedom
   ((n_t−1)(n_h−1) ≥ ~60). Total runs = n_t · n_h · n_r ≈ 240–450.
4. **Hold everything else fixed:** same skill bytes (the parity test is the
   audit trail), same MCP server version, same target artifacts; record
   harness + model version per judgment in metadata.
5. **Stratify targets** across the maturity levels / scenario types so the
   per-criterion profiles cover RAG, tool-use, and multi-turn criteria — else
   those criteria are `skipped` in the profile.
6. Deliverable then writes itself: components + Φ(λ) + D-study ("you need 2
   harnesses × 2 runs for a 0.8-dependable gate") + the criterion league table
   + fixed-vs-random views, against baselines (single dedicated LLM judge;
   human subset if available).

---

## 12. Out of scope (v1) — recorded so they're deliberate

- **Unbalanced designs** (missing cells / unequal reps) via REML — needs
  iterative optimization; revisit only if real studies can't deliver balance.
- **Confidence intervals on variance components** (Satterthwaite / jackknife) —
  additive later; jackknife-over-targets is stdlib-feasible.
- **Categorical latent-trait decomposition of decisions** — §5's empirical flip
  probabilities are the honest v1.
- **Unbiased Φ(λ)** correction for estimated μ̂.
- **Additional facets** (occasion, model-version-within-harness) — the EMS
  machinery generalizes, but each facet multiplies study cost.

## 13. Decisions taken (defaults chosen; say the word to change)

| Decision | Choice | Alternative rejected |
| --- | --- | --- |
| Where it lives | `analysis/calibration/harness/` | New top-level `analysis/reliability/` — over-structure for one capability |
| Facet model | Two facets + replication, fully crossed | Three named facets (occasion) — study cost, v2 |
| Balance | Required, fail-fast | Harmonic-mean quasi-balance — silently approximate, contradicts house style |
| CLI | Unified verb only | New console script — script sprawl (agreement precedent) |
| MCP surface | One tool | Separate `harness_dstudy` tool — result already contains it |
| Undefined coefficients | `null` | 1.0/0.0 conventions — same bug class as the Krippendorff fix |
