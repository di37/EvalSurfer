# `examples/golden/` — calibration golden set

Golden data for the "eval of the eval": a hand-authored oracle for one target,
paired with the judge reports to score against it.

| File | What it is |
| --- | --- |
| [`calibration.json`](calibration.json) | A `CalibrationCase` (signals, expected applicable pillars, per-criterion score bands, expected decision, top-issue severity, safety escalation) plus a `judge_reports` array of reports the judge produced for that target. |

## Use it

```bash
evalsurfer calibrate examples/golden/calibration.json --pretty
```

The agent can also call the `calibrate` / `calibrate_one` MCP tools directly (see [`../../docs/mcp.md`](../../docs/mcp.md)).

Returns `agreement`, `false_pass_rate`, `false_fail_rate`, and `score_variance`
across the runs. The scoring logic lives in
[`../../evalsurfer/calibration/`](../../evalsurfer/calibration/).

To calibrate your own judge: copy this file, set the `expected_*` fields to what a
trustworthy judge *should* conclude, and drop in several real judge reports for
the same target.
