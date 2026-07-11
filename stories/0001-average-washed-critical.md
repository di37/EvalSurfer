# 0001 — A critical safety issue shipped behind a healthy average

- **Date**: 2026-06-14 *(illustrative)*
- **Severity**: S3 — see [failure-modes.md](../docs/failure-modes.md#severity)
- **Failure mode**: [Average-Washing](../docs/failure-modes.md#average-washing)
- **Status**: resolved

## What happened

- A clinical-support RAG assistant was evaluated before a release. The scorecard read **overall 7.1/10, safety 8.4/10** — comfortably "green".
- The team approved the release off those two numbers, pasted into a slide.
- A week later a user who missed a dose was told to **double up on warfarin** — advice the retrieved guideline explicitly forbids.

## Impact

A harmful, ungrounded medical answer reached a real user. The exact problem *was*
in the report — `harmful_content` scored **1/5** with evidence — but it was one
criterion averaged against four 5s, so the safety category still read 8.4.

## Root cause

The team gated on **aggregate scores**, not on EvalSurfer's decision. The
critical safety issue never changed the headline number, so it never changed the
ship decision.

## What caught it (or should have)

`ScoringModel.decide()` already returns **`fail`** when a `critical` safety issue
is present, *regardless of the averages*. The report's `decision` field said
`fail`; nobody read it — they read the 7.1.

## Fix

Wire `evalsurfer gate` into CI and block on the **decision**, not the overall
score. Re-running the gate on the same report returned exit code 1.

## Prevention

Adopt a `guardrails.json` that makes the safety stance non-negotiable, enforced
in CI:

```json
{ "min_decision": "pass", "min_safety": 8.0, "block_on_critical_issue": true }
```

Any `critical` issue now blocks the merge and demands human review.

## Lessons

- Never gate on a mean; a single critical failure hides in an average.
- Enforce the **decision**, not the dashboard — the number is for humans, the
  decision is for the gate.
