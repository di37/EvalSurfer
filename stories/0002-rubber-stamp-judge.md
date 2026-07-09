# 0002 — A cheap judge passed ungrounded RAG answers

- **Date**: 2026-06-22 *(illustrative)*
- **Severity**: S2 — see [failure-modes.md](../docs/failure-modes.md#severity)
- **Failure mode**: [Judge Theater](../docs/failure-modes.md#judge-theater)
- **Status**: resolved

## What happened

- To keep eval costs down, a team wired a small, cheap model as the judge for a
  support RAG bot and ran a single pass per answer.
- The judge kept returning **5/5** on fluent, confident answers.
- Users then reported answers that cited policies that don't exist — hallucinations
  the eval had rated top marks.

## Impact

Weeks of false confidence. The eval was **reliable** (same score every run) but
not **valid** — it rewarded fluency over grounding, exactly the well-documented
verbosity / self-enhancement bias of LLM-as-judge.

## Root cause

A single, weak, **uncalibrated** judge. Nobody had ever checked whether its
"pass" meant anything — *quis custodiet ipsos custodes?*

## What caught it (or should have)

Running `Calibrator` against a small hand-authored oracle (answers with known
grounding verdicts) surfaced a **`false_pass_rate` of 0.40** — the judge passed
40% of answers a trustworthy judge would fail.

## Fix

- Swap in a stronger judge model and use **self-consistency** on borderline calls.
- Add the calibration set to the pipeline and review its numbers before trusting
  a release.

## Prevention

Run the golden calibration set in CI and treat the judge itself as gated:

- Block releases when the judge's `false_pass_rate` exceeds an agreed threshold.
- Use **multiple judges** for high-impact releases; see the skill's Judge
  Reliability guidance.

## Lessons

- Evaluate the evaluator — an uncalibrated green light is not evidence.
- Reproducible ≠ correct. Consistency without calibration just means you're
  wrong the same way every time.
