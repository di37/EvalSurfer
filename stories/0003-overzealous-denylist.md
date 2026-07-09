# 0003 — A guardrail denylist over-blocked and eroded trust

- **Date**: 2026-07-02 *(illustrative)*
- **Severity**: S1 — see [failure-modes.md](../docs/failure-modes.md#severity)
- **Failure mode**: guardrail misconfiguration (a *false block* — the inverse of
  [Gate Rubber-Stamp](../docs/failure-modes.md#gate-rubber-stamp))
- **Status**: resolved

## What happened

- A team added a sensitive-path denylist to `guardrails.json` with a broad
  pattern: `"sensitive_paths": ["*_key*"]`.
- It matched everyday files like `utils/monkey_key_map.py` and `tests/keyboard_test.py`.
- Every unrelated PR touching those files was flagged **human-review-required**
  and blocked, several times a day.
- Within a week developers were routing around the gate and ignoring its output.

## Impact

No unsafe release — but **review fatigue** and lost trust. A guardrail that cries
wolf is worse than none, because people learn to dismiss it (and then miss the
real escalation).

## Root cause

The glob was far too broad. `sensitive_paths` matching is case-insensitive and
`*` spans `/`, so `*_key*` matched any path containing `_key` anywhere.

## What caught it (or should have)

A rising **false-block rate** and developer complaints. The signal was there in
`sensitive_paths_touched` on every gate run — nobody was tracking it.

## Fix

Tighten the patterns to the paths that are actually sensitive:

```json
{ "sensitive_paths": ["secrets/**", "**/credentials/**", "*.pem", "*.key", "auth/**"] }
```

## Prevention

- Keep `sensitive_paths` **tight and specific**; prefer real secret/auth/infra
  directories over substring globs.
- Track the guardrail's own **false-block rate**; if it climbs, the policy — not
  the developers — is the problem.

## Lessons

- Guardrails have their own failure mode. Over-blocking is a failure too — it
  trains people to bypass the gate.
- Tune for signal: a gate is only useful while people still believe it.
