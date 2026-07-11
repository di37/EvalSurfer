"""EvalSurfer as an MCP server (optional ``[mcp]`` extra).

The deterministic functions of EvalSurfer, exposed as agent-callable MCP tools.
Kept import-light on purpose: importing this package name pulls in no heavy
dependencies. Import :mod:`evalsurfer.interface.mcp.server` (or run ``evalsurfer-mcp``) to
start the stdio server. The ``evalsurfer`` package never imports ``mcp`` or
``pydantic`` — only this subpackage does — so the package stays zero-dependency.
"""
