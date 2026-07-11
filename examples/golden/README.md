# `examples/golden/` — calibration oracle (Analysis)

Hand-authored oracle for the "eval of the eval" (`Calibrator`), paired with judge
reports to score against it. This is **not** Analysis framework `GoldenSet`
(deterministic self-test) and **not** the Metrics eval golden dataset
(`metrics/dataset/`).

| File | What it is |
| --- | --- |
| [`calibration.json`](calibration.json) | A `CalibrationCase` (signals, expected applicable categories, per-criterion score bands, expected decision, top-issue severity, safety escalation) plus a `judge_reports` array of reports the judge produced for that target. |

## Use it

```bash
evalsurfer calibrate examples/golden/calibration.json --pretty
```

The agent can also call the `calibrate` / `calibrate_one` MCP tools directly (see [`../../docs/mcp.md`](../../docs/mcp.md)).

Returns `agreement`, `false_pass_rate`, `false_fail_rate`, and `score_variance`
across the runs. The scoring logic lives in
[`../../evalsurfer/analysis/calibration/`](../../evalsurfer/analysis/calibration/).

To calibrate your own judge: copy this file, set the `expected_*` fields to what a
trustworthy judge *should* conclude, and drop in several real judge reports for
the same target.
