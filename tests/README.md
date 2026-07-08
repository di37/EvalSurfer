# `tests/` — the deterministic test suite

Standard-library `unittest` tests covering the whole package: scoring, planner,
report validation, operational metrics + SLO, every diagnostic, red-team,
trajectory, calibration, adapters, the `Evaluator`, the CLI, the report schema,
and multi-harness skill parity. No network and no model calls.

## Run

```bash
# From the repository root:
python -m unittest discover -s tests -t .

# A single module:
python -m unittest tests.test_scoring -v
```

`-t .` (top-level dir = repo root) puts `evalsurfer` on the import path;
`tests/__init__.py` makes the folder a discoverable package.

## Layout

One `test_<module>.py` per source module (e.g. [`test_scoring.py`](test_scoring.py)
↔ `core/scoring.py`). Two suites are cross-cutting:

- [`test_report_schema.py`](test_report_schema.py) — validates `examples/report.json` against `report.schema.json` (uses the optional `jsonschema` dev extra).
- [`test_skill_parity.py`](test_skill_parity.py) — asserts the three staged `SKILL.md` copies (`skills/`, `.claude/`, `.cursor/`) stay byte-identical.

To install the one optional dev dependency (`jsonschema`):

```bash
python -m pip install -e ".[dev]"
```
