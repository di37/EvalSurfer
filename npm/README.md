# evalsurfer (npm)

An `npx` launcher for the **EvalSurfer** MCP server. EvalSurfer is an agent-native
AI-evaluation protocol — your coding agent is the judge, and it calls EvalSurfer's
36 deterministic tools for the measurement. See the
[main project](https://github.com/di37/EvalSurfer).

The server itself is a **Python** package (`evalsurfer[mcp]`); this wrapper just
launches it, so you need Python available via one of **uv** (recommended), **pipx**,
or a prior `pip install`.

## Use

Run it directly:

```bash
npx evalsurfer
```

Or wire it into your agent's MCP config (`.mcp.json` for Claude Code,
`.cursor/mcp.json` for Cursor) — nothing to install first:

```json
{ "mcpServers": { "evalsurfer": { "command": "npx", "args": ["-y", "evalsurfer"] } } }
```

The wrapper resolves a launcher in this order: `uvx --from "evalsurfer[mcp]"
evalsurfer-mcp` → `pipx run` → an already-installed `evalsurfer-mcp`. Python users
can skip npm entirely: `uvx --from "evalsurfer[mcp]" evalsurfer-mcp`.

MIT © Doula Isham Rashik Hasan
