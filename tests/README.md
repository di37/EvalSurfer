# `tests/` — the deterministic test suite

Standard-library `unittest` tests covering the whole package: scoring, planner,
report validation, operational metrics + SLO, every diagnostic, red-team,
trajectory, calibration, adapters, the `Evaluator`, the CLI, the report schema,
multi-harness skill parity, release guardrails, and the MCP tool server. No
network and no model calls.

## Run

```bash
# From the repository root:
python -m unittest discover -s tests -t .

# A single module:
python -m unittest tests.core.test_scoring -v
```

`-t .` (top-level dir = repo root) puts `evalsurfer` on the import path;
`tests/__init__.py` makes the folder a discoverable package.

## Layout

`tests/` mirrors the package: one `test_<module>.py` per source module, grouped into the
same subpackages (e.g. [`core/test_scoring.py`](core/test_scoring.py) ↔
`evalsurfer/core/scoring.py`). Two suites are cross-cutting:

- [`spec/test_report_schema.py`](spec/test_report_schema.py) — validates `examples/report.json` against `spec/report.schema.json` (uses the optional `jsonschema` dev extra).
- [`skill/test_skill_parity.py`](skill/test_skill_parity.py) — asserts the three staged `SKILL.md` copies (`skills/`, `.claude/`, `.cursor/`) stay byte-identical.

Two more are worth calling out:

- [`mcp/test_mcp_server.py`](mcp/test_mcp_server.py) — drives all 47 tools of the EvalSurfer MCP server; `@skipUnless`-skips the whole suite when the optional `[mcp]` extra isn't installed.
- [`policy/test_guardrails.py`](policy/test_guardrails.py) — covers the release-guardrail policy (`policy/guardrails.py`): minimum decision, safety floor, and sensitive-path / critical-issue blocking.

To install the one optional dev dependency (`jsonschema`):

```bash
python -m pip install -e ".[dev]"
```
