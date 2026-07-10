# Evaluation Anti-Patterns

Ten mistakes teams make when evaluating AI applications — and what to do instead.
Each maps to the EvalSurfer feature that prevents it.

> Each mitigation below is exposed as an MCP tool the harness LLM calls — see
> [the MCP tool server](mcp.md). The core makes no model calls; the agent judges,
> the tools measure.

> Format inspired by the anti-patterns list in
> [cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering),
> adapted from *agent loops* to *AI evaluation*. See also
> [failure-modes.md](failure-modes.md).

---

**1. One judge for high-stakes releases**
- *Problem*: A single LLM-as-judge run carries known biases and run-to-run variance, yet its verdict ships a release.
- *Instead*: Use single-judge only for low-risk dev checks; escalate to self-consistency for borderline decisions and to multiple judges (or a human) for high-impact releases — and **calibrate** the judge with `Calibrator` (MCP `calibrate` / `calibrate_one`).

**2. Scoring without evidence**
- *Problem*: A bare "3/5" can't be audited, reproduced, or trusted.
- *Instead*: Require `evidence` on every criterion; use the `Explainer` (MCP `explain`) to attribute the gap from a perfect 10 to specific criteria.

**3. Evaluating everything, regardless of inputs**
- *Problem*: Grading RAG or tool-use criteria on an app that has neither produces spurious low scores and noise.
- *Instead*: Let the **adaptive planner** (MCP `plan`) infer applicable criteria from the evidence present and report a **coverage score** (MCP `coverage`); mark the rest `Not assessed` with reasons.

**4. Trusting the aggregate (no safety floor)**
- *Problem*: A mean score buries a single critical failure, and it ships.
- *Instead*: Use decision logic with an explicit **safety floor** and a **critical-issue override** — one critical safety issue fails the release regardless of the average.

**5. No calibration — *quis custodiet ipsos custodes?***
- *Problem*: The judge is never itself evaluated, so you don't know if its passes mean anything.
- *Instead*: Run the "eval of the eval" — `Calibrator` (MCP `calibrate` / `calibrate_one`) scores agreement, false-pass / false-fail rate, and score variance against a hand-authored oracle; the `GoldenSet` validates the deterministic layer.

**6. Judge shares the app's model and context**
- *Problem*: Self-enhancement bias — a model grading its own family/output inflates the score.
- *Instead*: Delegate judgment to a *separate* agent/model via the portable skill; note the bias in high-stakes reviews and cross-check with a different judge.

**7. Quality-only; safety and ops as an afterthought**
- *Problem*: A "good" answer that is unsafe, too slow, or too expensive still fails in production.
- *Instead*: Evaluate all **three pillars** — safety is assessed by default; operational readiness is auto-scored (MCP `operational_score` / `metrics`) against SLOs (the five numbers of inference).

**8. Fabricating a verdict for what can't be measured**
- *Problem*: Reporting "injection-resistant: pass" or "answer consistent: yes" without actually testing it.
- *Instead*: Flag `needs_judgment` / `Not assessed` for anything the deterministic layer can't decide; only return hard verdicts where they're reliable (e.g. PII regex).

**9. No regression tracking between versions**
- *Problem*: v2 silently regresses on one criterion while the headline number improves.
- *Instead*: Diff versions with `RegressionDiffer` (`diagnose --before`, MCP `regression_diff`) — per-criterion improvements *and* regressions, plus any decision change.

**10. Auto-shipping on a green eval, no human gate**
- *Problem*: A passing report is treated as merge authorization for sensitive changes.
- *Instead*: Wire `ReviewGate` (MCP `review_gate`) + the release `gate` into CI, but require **human approval** for unresolved `critical` issues and for auth / payments / PII / infra paths. This is enforceable: a `guardrails.json` policy with `evalsurfer gate --policy … --changed-files …` (MCP `guardrail_gate` / `gate`) blocks the merge (non-zero exit) when a sensitive path is touched or any rule trips. See [SECURITY.md](SECURITY.md#using-the-ci-gate-safely).

---

## The through-line

Most of these reduce to one principle: **separate what can be measured
deterministically from what must be judged — make the measurement reproducible
and auditable, and never fabricate the judgment.** That principle is the reason
EvalSurfer's core makes no model calls and flags, rather than invents, anything
it cannot decide.
