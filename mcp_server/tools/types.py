"""Activity type and gear tools for the MCP server (always read-only)."""

import sqlite3
from typing import Optional

from app.repositories.type_repository import TypeRepository
from app.repositories.gear_repository import GearRepository
from mcp_server.auth import AuthContext


def register_type_tools(mcp, conn: sqlite3.Connection, auth: AuthContext) -> None:
    """Register type and gear read-only tools."""

    type_repo = TypeRepository(db=conn)
    gear_repo = GearRepository(db=conn)

    @mcp.tool()
    def list_standard_types() -> list:
        """List all standard Strava activity types.

        Returns:
            List of standard type dicts with name, category, display_name, icon, color.
        """
        rows = type_repo.get_standard_types()
        return [dict(r) for r in rows]

    @mcp.tool()
    def list_extended_types(base_sport_type: Optional[str] = None) -> list:
        """List custom extended activity type classifications.

        Args:
            base_sport_type: Optional filter (e.g. 'Run', 'Ride').

        Returns:
            List of extended type dicts with id, base_sport_type, custom_name, color_class.
        """
        rows = type_repo.get_extended_types()
        if base_sport_type:
            rows = [r for r in rows if r.get("base_sport_type") == base_sport_type]
        return [dict(r) for r in rows]

    @mcp.tool()
    def list_gear() -> list:
        """List all gear (bikes, shoes, etc.) with usage statistics.

        Returns:
            List of gear dicts including stats (total_activities, total_distance_km, etc.).
        """
        gear_list = gear_repo.get_all_gear_with_stats()
        result = []
        for g in gear_list:
            item = dict(g)
            # Convert distance stats to km for readability
            if "stats" in item and item["stats"]:
                stats = dict(item["stats"])
                stats["total_distance_km"] = round(
                    (stats.get("total_distance") or 0) / 1000, 2
                )
                item["stats"] = stats
            result.append(item)
        return result
