# Releasing EvalSurfer

EvalSurfer ships two packages so users can install it the way they already work:

- **PyPI** — `evalsurfer` (the real package: core + the `[mcp]` server extra).
- **npm** — `evalsurfer` (a thin `npx` launcher that runs the Python server).

The [`Publish` workflow](.github/workflows/publish.yml) pushes both when you
publish a GitHub Release. Set up the two credentials once, then release.

## One-time setup

**PyPI (trusted publishing — no token to store).**
1. Build once locally and create the project, or pre-register it as a
   [pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
2. On PyPI → the `evalsurfer` project → *Publishing*, add a **GitHub Actions**
   trusted publisher: owner `di37`, repo `EvalSurfer`, workflow `publish.yml`,
   environment `pypi`.
3. In the GitHub repo, create an **Environment** named `pypi` (Settings →
   Environments) — the workflow's `pypi` job references it.

**npm.**
1. Create the `evalsurfer` package owner/org on npm.
2. Add a repo secret `NPM_TOKEN` (Settings → Secrets → Actions) with an
   **Automation** token that has publish rights.

## Cut a release

1. Bump the version in **all three** — [`pyproject.toml`](pyproject.toml) and
   [`npm/package.json`](npm/package.json) (keep these two identical), plus
   `FRAMEWORK_VERSION` in [`evalsurfer/constants.py`](evalsurfer/constants.py),
   which backs `evalsurfer.__version__`.
2. Commit, tag (`git tag v0.1.0`), and push the tag.
3. Create a GitHub **Release** for the tag. Publishing it triggers the workflow,
   which builds and uploads to PyPI and npm.

## Manual fallback

```bash
# PyPI
python -m pip install --upgrade build twine
python -m build
python -m twine upload dist/*

# npm
cd npm && npm publish --access public
```

## Verify a release

```bash
uvx --from "evalsurfer[mcp]" evalsurfer-mcp --help   # Python path (no install)
npx -y evalsurfer --help                             # npm launcher path
```

> Until the first release lands, the `uvx` / `pipx` / `npx` commands in the README
> resolve only from a local checkout (`pip install -e ".[mcp]"`). They go live for
> everyone the moment `v0.1.0` is published.
