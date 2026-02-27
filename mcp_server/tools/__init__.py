"""Tool registration for the Activity Manager MCP server."""

import sqlite3

from mcp_server.auth import AuthContext
from mcp_server.tools.activities import register_activity_tools
from mcp_server.tools.days import register_day_tools
from mcp_server.tools.planning import register_planning_tools
from mcp_server.tools.types import register_type_tools


def register_all_tools(mcp, conn: sqlite3.Connection, auth: AuthContext) -> None:
    """Register all tool modules with the FastMCP instance."""
    register_activity_tools(mcp, conn, auth)
    register_day_tools(mcp, conn, auth)
    register_planning_tools(mcp, conn, auth)
    register_type_tools(mcp, conn, auth)
