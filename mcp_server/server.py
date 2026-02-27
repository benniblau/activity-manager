"""Entry point for the Activity Manager MCP server.

Supports two transport modes selected via MCP_TRANSPORT env var:

  stdio (default) — launched as a subprocess by Claude Desktop / Claude Code.
      AM_API_KEY=am_<key> python -m mcp_server.server

  sse — HTTP Server-Sent Events, suitable for running as a persistent daemon.
      MCP_TRANSPORT=sse MCP_HOST=127.0.0.1 MCP_PORT=8001 AM_API_KEY=am_<key> \
          python -m mcp_server.server

Environment variables:
    AM_API_KEY       - Required. API key created via /admin/profile.
    DATABASE_PATH    - Optional. Path to activities.db (default: ./activities.db).
    MCP_TRANSPORT    - Optional. 'stdio' (default) or 'sse'.
    MCP_HOST         - Optional. Bind host for SSE mode (default: 127.0.0.1).
    MCP_PORT         - Optional. Bind port for SSE mode (default: 8001).
"""

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path before any app.* imports
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

from mcp_server.db import open_db
from mcp_server.auth import resolve_auth
from mcp_server.tools import register_all_tools


def main() -> None:
    raw_key = os.environ.get("AM_API_KEY", "")
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8001"))

    conn = open_db()  # exits 2 on failure

    try:
        auth = resolve_auth(conn, raw_key)
    except PermissionError as exc:
        print(f"[mcp_server] Authentication failed: {exc}", file=sys.stderr)
        sys.exit(1)

    mcp = FastMCP(name="activity-manager", host=host, port=port)
    register_all_tools(mcp, conn, auth)

    if transport == "sse":
        print(
            f"[mcp_server] Starting SSE server on http://{host}:{port} "
            f"(user_id={auth.user_id}, scope={auth.scope})",
            file=sys.stderr,
        )
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
