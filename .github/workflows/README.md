# `.github/workflows/` — continuous integration

GitHub Actions workflows for the repository.

| File | Trigger | What it does |
| --- | --- | --- |
| [`ci.yml`](ci.yml) | push to `main`, and every pull request | **`test`** job — installs `[dev]`, runs the full `unittest` suite on Python 3.11 / 3.12, smoke-tests the `metrics` / `plan` CLIs. **`mcp`** job — installs `[dev,mcp]` on 3.12, runs the suite including the 36-tool `test_mcp_server.py`, and smoke-tests the MCP server. |
| [`publish.yml`](publish.yml) | a published GitHub **Release** | Builds and publishes the Python package to **PyPI** (OIDC trusted publishing) and the npm launcher wrapper to **npm**. Setup + steps in [`../../RELEASING.md`](../../RELEASING.md). |

## Notes

- The test matrix mirrors `requires-python = ">=3.11"` in [`../../pyproject.toml`](../../pyproject.toml); add a Python version here and there together.
- `fail-fast: false` so one version failing still reports the others.
- The **core** package has **no runtime dependencies**; the `test` job installs only the `[dev]` extra (`jsonschema`), which also proves the core stays importable with no `mcp` / `pydantic`.
- The **`mcp`** job installs the `[mcp]` extra so [`test_mcp_server.py`](../../tests/test_mcp_server.py) runs (it `@skipUnless`-skips in the `test` job) and asserts all **36** tools register — closing what would otherwise be an MCP coverage gap while keeping the zero-dependency signal from the `test` job.

> Not to be confused with the release **gate** action at
> [`../../action.yml`](../../action.yml), which is a reusable composite action
> that fails a build when an EvalSurfer report is below a minimum decision.
