#!/usr/bin/env node
"use strict";

// `npx evalsurfer` bootstrapper.
//
// The EvalSurfer MCP server is a Python package (`evalsurfer[mcp]`). This thin
// wrapper launches it, preferring uv (`uvx`, no install) and falling back to
// pipx, then an already-installed console script. stdio is inherited, so this
// process is a transparent MCP stdio pass-through between the harness and the
// Python server. Any extra args are forwarded.

const { spawnSync } = require("node:child_process");

const passthrough = process.argv.slice(2);
const SPEC = "evalsurfer[mcp]";

const strategies = [
  { cmd: "uvx", args: ["--from", SPEC, "evalsurfer-mcp", ...passthrough] },
  { cmd: "pipx", args: ["run", "--spec", SPEC, "evalsurfer-mcp", ...passthrough] },
  { cmd: "evalsurfer-mcp", args: passthrough }, // already on PATH (pip/pipx install)
];

function exists(cmd) {
  const probe = process.platform === "win32" ? "where" : "which";
  return spawnSync(probe, [cmd], { stdio: "ignore" }).status === 0;
}

for (const { cmd, args } of strategies) {
  if (cmd !== "evalsurfer-mcp" && !exists(cmd)) continue;
  const res = spawnSync(cmd, args, { stdio: "inherit" });
  if (res.error) {
    if (res.error.code === "ENOENT") continue; // launcher vanished; try the next
    console.error(`evalsurfer: failed to launch via ${cmd}: ${res.error.message}`);
    process.exit(1);
  }
  process.exit(res.status === null ? 1 : res.status);
}

console.error(
  [
    "evalsurfer: no Python launcher found.",
    "",
    "The EvalSurfer MCP server is a Python package. Install one of:",
    "  • uv   (recommended, zero-install) — https://docs.astral.sh/uv/  then retry: npx evalsurfer",
    '  • pipx — pipx install "evalsurfer[mcp]"  then: evalsurfer-mcp',
    '  • pip  — pip install "evalsurfer[mcp]"   then: evalsurfer-mcp',
  ].join("\n")
);
process.exit(1);
