# `examples/` — reference inputs and worked scenarios

Sample JSON you can copy, adapt, and feed to the CLI or Python API, plus a full
demo suite. Nothing here calls a model or API.

| Path | What it is |
| --- | --- |
| [`sample.json`](sample.json) | A complete `evaluate` request: a RAG sample, per-criterion scores, evidence, traces + SLO, and top issues. The reference input shape. |
| [`report.json`](report.json) | A complete report — the reference *output* shape that validates against [`../report.schema.json`](../report.schema.json). |
| [`traces.json`](traces.json) | A request-traces payload for `evalsurfer metrics` (mixed field names, one failure). |
| [`agent_trace.json`](agent_trace.json) | An agent trajectory (`actual` vs `expected`) for `evalsurfer trajectory`. |
| [`golden/`](golden/) | Calibration golden set — an oracle plus judge reports for `evalsurfer calibrate`. |
| [`scenarios/`](scenarios/) | Six realistic, end-to-end use cases with an interactive `demo.sh` — exercises every functionality. |

## Quick try

```bash
evalsurfer evaluate examples/sample.json --pretty
evalsurfer metrics  examples/traces.json --pretty
evalsurfer trajectory examples/agent_trace.json --pretty
evalsurfer calibrate examples/golden/calibration.json --pretty

# The guided demo:
bash examples/scenarios/demo.sh
```

See [`scenarios/README.md`](scenarios/README.md) for the full walkthrough.
