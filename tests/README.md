# `tests/` — the deterministic test suite

Standard-library `unittest` tests mirroring CIMAA packages. No network and no
model calls.

## Run

```bash
python -m unittest discover -s tests -t .
python -m unittest tests.core.test_scoring -v
```

## Layout

```
tests/
  core/                 ↔ evalsurfer/core/
  metrics/
    operational/        ↔ evalsurfer/metrics/operational/
    quality/            ↔ evalsurfer/metrics/quality/
    dataset/            ↔ evalsurfer/metrics/dataset/
  analysis/
    diagnostics/        ↔ evalsurfer/analysis/diagnostics/
    calibration/        ↔ evalsurfer/analysis/calibration/
  assurance/
    policy/             ↔ evalsurfer/assurance/policy/
    safety/             ↔ evalsurfer/assurance/safety/
    trajectory/         ↔ evalsurfer/assurance/trajectory/
  interface/
    cli/ mcp/ adapters/ skill/
    test_pipeline.py    ↔ evalsurfer/interface/pipeline.py
  spec/                 — schema + fixture checks
```

Cross-cutting:

- `spec/test_report_schema.py` — `examples/report.json` vs `spec/report.schema.json`
- `interface/skill/test_skill_parity.py` — staged `SKILL.md` copies stay identical
- `interface/mcp/test_mcp_server.py` — all MCP tools (`[mcp]` extra; skips otherwise)
