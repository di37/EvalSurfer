# EvalSurfer Roadmap

EvalSurfer is a skill-first, agent-native evaluation protocol for AI applications:
your coding agent is the judge, and a deterministic, zero-dependency CIMAA stack does the
measurement — the framework itself makes **zero LLM calls**. This document sets the
direction for the next releases.

It is informed by a review of current LLM-evaluation practice and academic methodology
(e.g. Stanford's CME 295 lecture on LLM evaluation) — covering automatic/reference
metrics, LLM-as-a-judge and its biases, retrieval and agent-tool evaluation, benchmarks,
human annotation, and statistical rigor. Two findings shape everything below:

1. **The landscape validates EvalSurfer's design.** It independently arrives at
   application-eval (not model-eval); a Quality / Safety / Operational risk model that is
   exactly EvalSurfer's three categories; criteria-based rubric scoring; LLM-as-judge; and a
   repeatable deterministic measurement stack. Nothing contradicts the design — the items
   below are **additive**.
2. **It endorses the zero-LLM split.** The rigorous view is that hard-coded metrics
   are preferable *precisely because* an LLM-judge "introduces another layer of potential
   errors." That is EvalSurfer's exact stance: **deterministic metrics live in the Metrics
   layer (and Core scoring rules); judgment lives in the agent.** Every roadmap item is
   placed on the correct side of that line.

## Design principles (unchanged)

- **Zero LLM calls in the `evalsurfer` package.** The harness agent is the judge; CIMAA
  layers only measure. Automatic metrics (BLEU, kappa, Recall@k, pass^k, weighted
  aggregation) are code → Metrics / Core. Judgment techniques (pairwise, bias-swap voting,
  fact decomposition, RAG/web fact-checking) are the agent's job → skill/MCP.
- **Zero runtime dependencies in the package** (outside optional extras). Anything needing
  a library goes in an optional extra, never the default install.
- **One capability, three surfaces.** Every capability is an MCP tool, a CLI verb, and a
  Python import — deterministic, immutable, tested.

## Already shipped (0.1.x)

Three categories — Application Quality / Safety / Operational (judged rubric criteria; reference metrics sit alongside under Metrics) · adaptive planner
+ coverage · 1–5 → `pass` / `pass_with_fixes` / `fail` with a safety floor · diagnostics
(attribution, root-cause, regression diff, maturity, industry profiles, Analysis `ReviewGate`,
personas, failure map, golden self-test) · operational metrics from traces · calibration
(judge agreement, false-pass/fail, variance) · red-team + PII detection · agent-trajectory
diffs · RAGAS/promptfoo/OTel/LangSmith adapters · guardrails + CI gate · a **48-tool** MCP
server + a portable skill. (0.1.3 added datasets, deterministic quality metrics, and
chance-corrected calibration on top of the earlier 36-tool surface.)

---

## v0.1.3 — Datasets, deterministic metrics & judge calibration — ✅ implemented

**Status:** implemented and tested on `main` (full suite green; **48 MCP tools**) and staged
for the 0.1.3 release. The widest, most-repeated gap was a **first-class golden dataset** and
the **reference-based** and **programmatic** methods that ride on it — all deterministic, all
in the Metrics / Analysis layers. What shipped, per item:

### 1. First-class eval dataset — `dataset`
- **What.** A versioned dataset artifact: cases with an input, optional gold
  answer / label / score, and coverage tags (`normal` / `difficult` / `edge` / `random`).
- **Contamination controls (from academic rigor).** Content-hash every case, support a
  canary/blocklist, and keep a held-out/fresh split — so eval cases can't leak into what's
  being evaluated (critical once the v0.2 flywheel folds production data back in) and so
  "Goodhart" gaming is detectable.
- **Build.** Sample cases from the request traces EvalSurfer already ingests; stable IDs so
  v1 ↔ v2 diff the same set.
- **Surface (shipped).** `dataset_from_traces` / `dataset_diff` / `dataset_contamination` /
  `dataset_coverage` MCP tools · `evalsurfer dataset` verb (+ `evalsurfer-dataset`) ·
  `spec/dataset.schema.json` · `evalsurfer/metrics/dataset/` (`DatasetCase`, `Dataset`).

### 2. Deterministic quality metrics — `quality_metrics` (code, zero LLM calls)
- **Retrieval:** Recall@k / Precision@k / MRR (from question → gold-doc-IDs). Reuse the
  same machinery for a **tool-selection recall** metric — the tool router is recall-oriented,
  and a router miss *is* a recall error.
- **Classification / extraction:** exact-match, accuracy, F1.
- **Named reference metrics (task-typed):** **BLEU** (translation), **ROUGE** (summarization),
  **METEOR** (order-aware, synonym/stem matches) — report a recognizable number, with the
  known caveat that these are stylistically brittle and correlate only weakly with humans.
- **Surface (shipped).** `retrieval_metrics` / `match_metrics` / `text_metrics` MCP tools ·
  `evalsurfer quality` verb (+ `evalsurfer-quality`) · `evalsurfer/metrics/quality/`. Shipped as a
  dedicated `quality` verb rather than `metrics --quality` (cleaner input shape; the two
  payloads are unrelated).

### 3. Calibration++ — reference-based + judge-vs-human + chance correction
- **Reference-based mode:** compare an output to a per-item gold answer/score.
- **Judge ↔ human agreement:** MAE / rank-correlation between the agent-judge and human
  gold scores, per criterion — the canonical way to validate an LLM judge (drive error → 0),
  and a Goodhart guard ("don't over-optimize the proxy").
- **Chance-corrected agreement:** add **Cohen's κ (2 raters) / Fleiss's κ (n raters) /
  Krippendorff's α** as the chance-corrected alternative to calibration's raw boolean
  `agreement` (which is ~50% by chance on a binary call) — cheap, deterministic, and sharpens
  the "eval of the eval." (The existing `calibrate` boolean remains for now; κ/α are the
  preferred signal, and folding them into `Calibrator` is a follow-up.)
- **Surface (shipped).** `cohen_kappa` / `fleiss_kappa` / `krippendorff_alpha` /
  `reference_calibrate` MCP tools · `evalsurfer agreement` verb · `AgreementStats` +
  `ReferenceCalibrator` in `evalsurfer/analysis/calibration/`. Shipped as **new** tools alongside
  `calibrate` (not a replacement). Reference-scoring of an output against a gold *answer*
  lives in item 2's text/match metrics; `reference_calibrate` compares judge *scores* against
  human *scores* (per-criterion error, MAE, Spearman rank correlation).

**Done. ✅** Build an eval golden dataset (incl. from traces, with contamination guards) → score
retrieval/classification/text with deterministic metrics → calibrate the judge against human
gold with chance-corrected agreement — all with **zero LLM calls in the `evalsurfer` package**.

---

## v0.1.4 / 0.2.0 — Granularity, judge robustness & the agent-failure taxonomy

### 4. Granularity axis (component → workflow → application)
A `tier` tag on every criterion so one single-pass run is sliced and **gated per tier**, plus
a workflow/interaction check and **component-scoped** operational metrics. The canonical case:
a retriever passes *and* a generator passes, yet the app is wrong because the **ranking seam**
failed. The tool-selection recall metric (item 2) lands here as a component-tier check.

### 5. Judge robustness — the full bias taxonomy + operating guidance
*(Judgment technique → the agent's job; EvalSurfer ships it as skill guidance + calibration checks.)*
- **Position bias** — a judge favors whichever answer is shown first. Remedy: score A-vs-B
  *and* B-vs-A and take the majority/average. **(Promoted from backlog — now a named technique.)**
- **Verbosity bias** — favors longer answers. Remedy: state it in the rubric, add in-context
  examples, apply a length penalty.
- **Self-enhancement bias** — a model prefers its own outputs. Remedy: let users designate a
  **judge model distinct from (and ideally bigger than) the generator**. **(Promoted from backlog.)**
- **Operating guidance:** rationale-**before**-score, **structured output** (guaranteed
  parseable `score` + `rationale`), low temperature (0.1–0.2) for reproducibility, and an
  optional **binary pass/fail mode** (academic evidence says binary is easier for both the
  judge and human alignment and removes granularity noise — see Open Questions).

### 6. Pairwise / preference judging + ranking *(promoted from backlog)*
A second judge mode alongside single-output: "is A or B better?" — the Chatbot-Arena pattern,
and the source of preference labels for reward models. Aggregate pairwise results with
**Elo / Bradley–Terry** into a ranking. Pairs with the position-bias swap (item 5).

### 7. Canonical agent-tool failure taxonomy (as the failure-map schema)
Adopt the 7-mode taxonomy across the three tool stages as the schema for the existing failure
map + trajectory diffs:
- **Predict:** (1) no-tool / over-refusal "punt", (2) tool hallucination, (3) wrong tool,
  (4) right tool + wrong arguments.
- **Call:** (5) wrong/error tool output, (6) no response / false confirmation
  (prefer **empty JSON over `None`**).
- **Synthesize:** (7) can't fold the tool result into the answer.
Each mode carries a remedy (router recall, API "three knobs" = name/args/docstring, grounding,
trimming verbose tool output).

### 8. Claim-level factuality / hallucination scoring
Upgrade the factuality criterion from a single judged 1–5 to **decompose → verify →
weighted-aggregate**: the agent extracts atomic claims and verifies each via RAG/web; the
**Core/Metrics** layer computes the weighted score `Σ αᵢ·correctnessᵢ / Σ αᵢ`. (Decomposition/verification =
agent + retrieval; the aggregation math = a deterministic Core/Metrics helper.)

### 9. Reliability & frontier reporting *(deterministic)*
- **pass^k** (probability *all* k attempts succeed) alongside pass@k — the right reliability
  statistic for agents/automation, distinct from run-to-run variance.
- **Pareto-frontier** view — plot quality against cost / safety / latency and take the
  best-per-cost border (EvalSurfer already has both quality and operational numbers).

### 10. Quick wins
- **Decision-questions report layer** — map the verdict to real questions (ship-ready? did v2
  improve? RAG grounded? safe? latency ok?).
- **Method + reference labels** — tag each criterion with its method (programmatic / human /
  LLM) and reference-based vs reference-free.
- **Named-incident probes** — real, cited failures as red-team / golden entries (hallucinated
  policy → legal liability; jailbroken binding offer; fabricated citations).
- **New Safety criterion** — *unauthorized commitment / fabricated authority*.
- **Explicit tonality / brand-voice** quality criterion.
- **HarmBench-style safety principles** — score a red-team probe as a failure if the harmful
  act was *attempted* even when the output was low-quality; add a **copyright-generation**
  safety category; treat safety verdicts as **policy-specific** (extends industry profiles).

---

## v0.2.x+ — Online eval & the data flywheel

- **Data flywheel** — capture production failures → append to the golden dataset (through the
  contamination guards of item 1) → re-run the regression. EvalSurfer already has
  regression-diff + trace ingest.
- **Online / production eval** — A/B testing, live user ratings, continuous monitoring — the
  counterpart to today's offline/CI gate.

---

## Backlog — not yet motivated by the review

- **Statistical confidence** — bootstrap confidence intervals and sample-size determination
  (how many cases a verdict actually needs). The reviewed material argues rigor via chance
  baselines (κ), pass^k reliability, and judge↔human correlation, but does **not** cover
  bootstrap CIs or power analysis — so this stays parked until there's a clear pull.
- **Model-benchmark literacy** (MMLU / SWE-bench / tau-bench / HarmBench awareness for
  base-model selection) — foundation-model territory, out of EvalSurfer's application scope;
  possibly a thin advisory later.

---

## Open design questions (honest tensions surfaced by the review)

- **Binary vs 1–5 scoring.** Academic guidance prefers a binary pass/fail judge scale (easier
  for the judge, better human alignment, less noise). EvalSurfer scores 1–5. Plan: offer a
  binary judging mode (item 5) and empirically check whether 1–5 granularity adds decision
  value or just judge noise.
- **Self-enhancement vs "the agent IS the judge."** When the app under test shares a model
  family with the judging agent (especially in the flywheel), self-preference bias is real.
  Mitigation: let users designate a distinct/bigger judge model. This is a skill/harness
  concern — it does **not** break the zero-LLM package rule.
- **Calibration as a recurring gate (Goodhart).** The judge score is a *proxy* for human
  ratings; over-optimizing it is a trap. Make judge↔human calibration (item 3) a periodic
  requirement, not an afterthought.

---

*Nothing here changes the product promise: your agent judges, the tools measure, and the
framework never calls a model. Feedback and disagreement welcome — open an issue.*
