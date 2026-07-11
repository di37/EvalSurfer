# `evalsurfer/analysis/` — CIMAA Analysis

Explain and compare results; calibrate the judge. Includes `ReviewGate`
(human-review recommendation) and framework `GoldenSet` self-tests.

| Subpackage | Role |
| --- | --- |
| [`diagnostics/`](diagnostics/) | Explainability, root-cause, regression, review gate, … |
| [`calibration/`](calibration/) | Judge agreement / false-pass / false-fail / κ / α |

`ReviewGate` is **Analysis**; Assurance owns `guardrail_gate` policy on Core's `Gate`.
