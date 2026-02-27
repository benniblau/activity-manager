"""Entry point for the Activity Manager MCP server.

Supports three transport modes selected via MCP_TRANSPORT env var:

  stdio (default) — launched as a subprocess by Claude Desktop / Claude Code.
      AM_API_KEY=am_<key> python -m mcp_server.server

  streamable-http — MCP spec 2025-03-26 standard; single POST/GET endpoint at /mcp.
      Recommended for all HTTP deployments and modern clients (mcporter, etc.).
      MCP_TRANSPORT=streamable-http MCP_HOST=127.0.0.1 MCP_PORT=8001 python -m mcp_server.server

  sse — Legacy HTTP transport (deprecated in MCP spec 2025-03-26); two endpoints:
      GET /sse  and  POST /messages/
      MCP_TRANSPORT=sse MCP_HOST=127.0.0.1 MCP_PORT=8001 python -m mcp_server.server

  Both HTTP modes require an API key on every request via one of:
    Authorization: Bearer am_<key>
    X-API-Key: am_<key>

  Auth requirements are discoverable machine-readably via:
    GET /.well-known/oauth-protected-resource   (RFC 9728)
    GET /.well-known/oauth-authorization-server (RFC 8414)

Environment variables:
    AM_API_KEY       - Required for stdio mode. API key created via /admin/profile.
    DATABASE_PATH    - Optional. Path to activities.db (default: ./activities.db).
    MCP_TRANSPORT    - Optional. 'stdio' (default), 'streamable-http', or 'sse'.
    MCP_HOST         - Optional. Bind host for HTTP modes (default: 127.0.0.1).
    MCP_PORT         - Optional. Bind port for HTTP modes (default: 8001).
    MCP_BASE_URL     - Optional. Override the externally-accessible base URL used in
                       discovery metadata and WWW-Authenticate headers.
                       Defaults to http://{MCP_HOST}:{MCP_PORT}.
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
from mcp_server.auth import resolve_auth, set_current_auth
from mcp_server.tools import register_all_tools


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_PORT", "8001"))

    conn = open_db()  # exits 2 on failure

    mcp = FastMCP(name="activity-manager", host=host, port=port)
    register_all_tools(mcp, conn)

    if transport in ("streamable-http", "sse"):
        from starlette.applications import Starlette
        from starlette.routing import Mount
        import uvicorn

        from mcp_server.discovery import make_discovery_routes
        from mcp_server.middleware import ApiKeyMiddleware

        base_url = os.environ.get("MCP_BASE_URL", f"http://{host}:{port}")

        if transport == "streamable-http":
            mcp_app = mcp.streamable_http_app()
            endpoint = f"{base_url}/mcp"
        else:
            mcp_app = mcp.sse_app()
            endpoint = f"{base_url}/sse"

        # Combine RFC 9728/8414 discovery routes with the FastMCP app.
        # Discovery routes are public; the middleware skips auth for them.
        combined_app = Starlette(
            routes=[
                *make_discovery_routes(base_url),
                Mount("/", app=mcp_app),
            ]
        )
        app_with_auth = ApiKeyMiddleware(combined_app, conn, base_url=base_url)

        print(
            f"[mcp_server] Starting {transport} server — endpoint: {endpoint}\n"
            f"  Auth discovery: {base_url}/.well-known/oauth-protected-resource\n"
            f"  Send key as:    Authorization: Bearer am_<key>",
            file=sys.stderr,
        )
        uvicorn.run(app_with_auth, host=host, port=port)
    else:
        # stdio mode: validate key once at startup, set auth context for the process.
        raw_key = os.environ.get("AM_API_KEY", "")
        try:
            auth = resolve_auth(conn, raw_key)
        except PermissionError as exc:
            print(f"[mcp_server] Authentication failed: {exc}", file=sys.stderr)
            sys.exit(1)

        set_current_auth(auth)
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
