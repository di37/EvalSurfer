# `evalsurfer/calibration/` — the eval of the eval

An EvalSurfer report is produced by the agent/skill acting as a judge. This
module never runs that judge — it **scores the judge**, by comparing its reports
against a hand-authored oracle. Deterministic, no model calls, inputs never
mutated.

| Module | Public API | Purpose |
| --- | --- | --- |
| [`calibrate.py`](calibrate.py) | `Calibrator`, `CalibrationCase` | Freeze what a trustworthy judge should conclude, then check one report (`check_report`) or aggregate many (`summarize`). |

> **As MCP tools:** the harness LLM calls these directly via the `evalsurfer[mcp]` server — `calibrate`, `calibrate_one`. See [`../mcp_server.py`](../mcp_server.py) and [`../../docs/mcp.md`](../../docs/mcp.md).

## What a case pins

A `CalibrationCase` freezes, for one target: the planner's applicable pillars,
the expected score band per criterion, the pass/fix/fail decision, the severity
of the worst reported issue, and whether a critical safety issue should escalate.

## What the summary reports

`Calibrator.summarize(case, judge_reports)` aggregates across repeated runs:

| Metric | Meaning |
| --- | --- |
| `agreement` | fraction whose decision matches the oracle |
| `false_pass_rate` | fraction judged pass/pass_with_fixes when the oracle expects a fail |
| `false_fail_rate` | fraction judged fail when the oracle expects a (conditional) pass |
| `score_variance` | population variance of the overall scores across runs |

```bash
evalsurfer calibrate examples/golden/calibration.json --pretty
```

The judge reports are external input from the agent/skill; this layer only reads
what they already contain. See the [calibration example](../../examples/golden/).
