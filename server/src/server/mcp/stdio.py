"""Run the MCP server over stdio (Claude Desktop, mcp-cli).

Stdio transport is local-process — auth comes from the OS user that spawned
the subprocess, so the agent_tokens check is intentionally skipped here.
"""

from __future__ import annotations

from server.mcp.server import mcp


def run() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
