# `.github/workflows/` — continuous integration

GitHub Actions workflows for the repository.

| File | Trigger | What it does |
| --- | --- | --- |
| [`ci.yml`](ci.yml) | push to `main`, and every pull request | Installs the package with dev extras, runs the full `unittest` suite on Python 3.11 / 3.12, then smoke-tests the `metrics` and `plan` CLIs. |

## Notes

- The test matrix mirrors `requires-python = ">=3.11"` in [`../../pyproject.toml`](../../pyproject.toml); add a Python version here and there together.
- `fail-fast: false` so one version failing still reports the others.
- The core package has **no runtime dependencies**; only the `[dev]` extra (`jsonschema`) is installed, for the schema test.

> Not to be confused with the release **gate** action at
> [`../../action.yml`](../../action.yml), which is a reusable composite action
> that fails a build when an EvalSurfer report is below a minimum decision.
