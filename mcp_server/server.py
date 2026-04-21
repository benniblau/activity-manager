"""Entry point for the Activity Manager MCP server.

Supports two transport modes selected via AM_MCP_TRANSPORT env var:

  stdio (default) — launched as a subprocess by Claude Desktop / Claude Code.
      AM_API_KEY=am_<key> python -m mcp_server.server

  http — HTTP streamable transport (MCP spec 2025-03-26); endpoint at /mcp.
      AM_MCP_TRANSPORT=http AM_MCP_HTTP_HOST=0.0.0.0 AM_MCP_HTTP_PORT=8080 python -m mcp_server.server

  HTTP mode requires an API key on every request via one of:
    Authorization: Bearer am_<key>
    X-API-Key: am_<key>

Environment variables:
    AM_API_KEY          - Required for stdio mode. API key created via /admin/profile.
    DATABASE_PATH       - Optional. Path to activities.db (default: ./activities.db).
    AM_MCP_TRANSPORT    - Optional. 'stdio' (default) or 'http'.
    AM_MCP_HTTP_HOST    - Optional. Bind host for HTTP mode (default: 0.0.0.0).
    AM_MCP_HTTP_PORT    - Optional. Bind port for HTTP mode (default: 8080).
"""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure project root is on sys.path before any app.* imports
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP

from mcp_server.db import open_db
from mcp_server.auth import resolve_auth, set_current_auth
from mcp_server.tools import register_all_tools


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Activity Manager MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.environ.get("AM_MCP_TRANSPORT", "stdio"),
        help="Transport mode (default: stdio)",
    )
    args = parser.parse_args()

    transport = args.transport
    host = os.environ.get("AM_MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.environ.get("AM_MCP_HTTP_PORT", "8080"))

    conn = open_db()  # exits 2 on failure

    mcp = FastMCP(name="activity-manager")
    register_all_tools(mcp, conn)

    if transport == "http":
        import uvicorn
        from starlette.applications import Starlette
        from starlette.routing import Mount
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
        from mcp_server.middleware import ApiKeyMiddleware

        session_manager = StreamableHTTPSessionManager(
            app=mcp._mcp_server, stateless=True
        )

        @asynccontextmanager
        async def lifespan(app):
            async with session_manager.run():
                yield

        def _normalize_path(inner):
            async def wrapped(scope, receive, send):
                if scope["type"] == "http" and not scope.get("path"):
                    scope = {**scope, "path": "/"}
                await inner(scope, receive, send)
            return wrapped

        app = Starlette(
            routes=[
                Mount(
                    "/mcp",
                    app=ApiKeyMiddleware(
                        _normalize_path(session_manager.handle_request), conn
                    ),
                )
            ],
            lifespan=lifespan,
        )

        logger.info(
            "Starting activity-manager MCP HTTP server on %s:%d — endpoint: http://%s:%d/mcp",
            host, port, host, port,
        )
        logger.info("Send API key as: Authorization: Bearer am_<key>")
        uvicorn.run(app, host=host, port=port, log_level="info")
    else:
        # stdio mode: validate key once at startup, set auth context for the process.
        raw_key = os.environ.get("AM_API_KEY", "")
        try:
            auth = resolve_auth(conn, raw_key)
        except PermissionError as exc:
            logger.error("Authentication failed: %s", exc)
            sys.exit(1)

        set_current_auth(auth)
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
