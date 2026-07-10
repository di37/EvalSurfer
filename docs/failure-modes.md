# Evaluation Failure Modes

Real ways AI **evaluation itself** fails — and how EvalSurfer's design mitigates
each. Use this when an eval result feels wrong, when a bad release slipped
through, or when deciding how far to trust a score.

> Each mitigation below is exposed as an MCP tool the harness LLM calls — see
> [the MCP tool server](mcp.md). The core makes no model calls; the agent judges,
> the tools measure.

> Format inspired by the failure-mode catalog in
> [cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering),
> adapted from *operating agent loops* to *evaluating AI applications*.

## Severity

| Severity | Meaning |
| --- | --- |
| **S1 — Misleading** | Noisy or wasted signal; no wrong decision reached |
| **S2 — Wrong decision** | A bad release passes, or a good one is blocked |
| **S3 — Unsafe shipped** | A harmful or unsafe application ships because the eval missed it |

---

## Judge Theater

**Symptom**: The judge marks an output "pass" that is actually wrong, ungrounded, or unsafe.

**Severity**: S2 → S3

**Causes**:
- LLM-as-judge biases — position, verbosity, and self-enhancement — reward style over substance ([Zheng et al., 2023](https://arxiv.org/abs/2306.05685)); the most *consistent* judges can be the least *valid* ([2026](https://arxiv.org/abs/2606.19544v1)).
- Vague rubric ("looks good"), or the judge shares a model/context with the app being judged.

**How EvalSurfer mitigates**:
- **Calibration** (`Calibrator`, "eval of the eval"; MCP `calibrate` / `calibrate_one`) measures a judge's agreement, false-pass / false-fail rate, and score variance against a hand-authored oracle.
- **Evidence is required** per criterion, so a "pass" must cite what supports it.
- The **decision is deterministic** — computed from criterion scores, not asserted by the judge — and the skill recommends self-consistency or multiple judges for borderline calls.

---

## Ungrounded Score

**Symptom**: A number with no justification — you cannot tell *why* something scored 3/5.

**Severity**: S1 → S2

**Causes**: Scores emitted without evidence; no attribution from score back to cause.

**How EvalSurfer mitigates**: Every criterion carries `evidence`; the `Explainer` (MCP `explain`) attributes the gap from a perfect 10 to individual criteria; the report schema makes evidence a first-class field.

---

## Over-Evaluation

**Symptom**: Criteria the inputs can't support get graded anyway — e.g. RAG groundedness on an answer with no retrieved context — producing spurious low scores.

**Severity**: S1

**Causes**: A fixed, full rubric applied regardless of what evidence is present.

**How EvalSurfer mitigates**: The **adaptive planner** (MCP `plan`) infers which criteria apply from the signals present and records every skip with a reason; unassessable criteria are marked `Not assessed`, never guessed.

---

## Fabricated Signal

**Symptom**: The eval reports a verdict for something it cannot actually determine — e.g. "prompt-injection resistance: pass" without ever probing it.

**Severity**: S2 → S3

**Causes**: Pressure to fill every cell of the rubric; a tool that invents a result rather than admitting it can't decide.

**How EvalSurfer mitigates**: Where a check needs a judge or a live app run, the deterministic layer does its half and **flags `needs_judgment`** rather than fabricating a signal (red-team triage, agent-trajectory final-answer consistency). Only reliably-decidable checks (e.g. PII regex) return a hard verdict.

---

## Average-Washing

**Symptom**: A critical safety failure is hidden by a healthy pillar average — overall looks fine, so it ships.

**Severity**: S3

**Causes**: Trusting aggregate means; one criterion at 1/5 disappears into four at 5/5.

**How EvalSurfer mitigates**: The decision logic has an explicit **safety floor** and a **critical-issue override** — a single `critical` safety issue fails the release regardless of the averages (e.g. overall `7.1`, safety pillar `8.4`, decision **fail**).

---

## Metric Myopia

**Symptom**: Answer quality is graded thoroughly while safety and operational readiness are ignored — the app is "good" but unsafe, too slow, or too expensive to run.

**Severity**: S2 → S3

**Causes**: Quality-only rubrics; treating safety and ops as someone else's problem.

**How EvalSurfer mitigates**: **Three pillars** — Application Quality, Safety (assessed by default), and Operational — including deterministic SLO scoring of the five numbers of inference (TTFT, inter-token latency, throughput, P99 tail, $/1M tokens).

---

## Judge Drift

**Symptom**: The same input yields a different verdict across runs, models, or harnesses — results aren't reproducible.

**Severity**: S2

**Causes**: A stochastic judge, and scaffolding (scoring, aggregation, gating) coupled to that stochastic call so *nothing* is reproducible.

**How EvalSurfer mitigates**: The core **separates measurement from judgment** — planning, aggregation, decision, operational scoring, and diagnostics are fully deterministic; only the subjective scores come from the judge. `Calibrator.score_variance` quantifies the remaining judgment drift.

---

## Regression Blindness

**Symptom**: A new version silently regresses on one criterion while the overall score looks flat or better.

**Severity**: S2

**Causes**: Comparing only headline numbers between versions.

**How EvalSurfer mitigates**: `RegressionDiffer` (`diagnose --before`, MCP `regression_diff`) reports per-criterion **improvements *and* regressions**, pillar deltas, and any decision change — so a `relevance` drop is visible even as `completeness` rises.

---

## Coverage Illusion

**Symptom**: A score is reported as if it covered the whole app, when most criteria were actually skipped.

**Severity**: S1 → S2

**Causes**: No accounting of how much of the applicable rubric was actually assessed.

**How EvalSurfer mitigates**: Every report carries a **coverage score** (assessed ÷ applicable criteria; MCP `coverage`) plus the list of `missing` criteria — so a thin evaluation can't masquerade as a thorough one.

---

## Gate Rubber-Stamp

**Symptom**: Teams trust the pass/fail without reading it; critical issues auto-merge because "the eval was green".

**Severity**: S2 → S3

**Causes**: No human gate for high-risk changes; comprehension debt — nobody reads the report.

**How EvalSurfer mitigates**: `ReviewGate` (MCP `review_gate`) returns `needs_human_review` with reasons (unresolved `critical` issues, low-confidence criteria); the release `gate` exposes exit codes for CI; the skill's Judge Reliability guidance mandates human review for unresolved `critical`, legal/compliance risk, or judge disagreement. These gates are enforceable in CI via a machine-readable `guardrails.json` policy (`evalsurfer gate --policy`, MCP `guardrail_gate` / `gate`). See [SECURITY.md](SECURITY.md#using-the-ci-gate-safely).

---

## Contributing

Hit an evaluation failure mode not listed here? Open an issue or PR with the
symptom, the cause, and what mitigated it.
