"""Day journal tools for the MCP server."""

import sqlite3
from typing import Optional

from app.repositories.day_repository import DayRepository
from mcp_server.auth import get_current_auth


def register_day_tools(mcp, conn: sqlite3.Connection) -> None:
    """Register day journal read and write tools."""

    repo = DayRepository(db=conn)

    @mcp.tool()
    def get_day(date: str) -> dict:
        """Get journal entry for a specific date.

        Args:
            date: Date string in YYYY-MM-DD format.

        Returns:
            Day dictionary, or {} if no entry exists for that date.
        """
        auth = get_current_auth()
        result = repo.get_day(date, user_id=auth.user_id)
        return dict(result) if result else {}

    @mcp.tool()
    def get_days_in_range(start_date: str, end_date: str) -> list:
        """Get all journal entries within a date range.

        Args:
            start_date: Start date (YYYY-MM-DD), inclusive.
            end_date: End date (YYYY-MM-DD), inclusive.

        Returns:
            List of day dictionaries ordered by date.
        """
        auth = get_current_auth()
        rows = repo.get_days_in_range(start_date, end_date, user_id=auth.user_id)
        return [dict(r) for r in rows]

    @mcp.tool()
    def get_day_with_activities(date: str) -> dict:
        """Get a day's journal entry together with its activities.

        Args:
            date: Date string in YYYY-MM-DD format.

        Returns:
            Dict with 'day' (dict or None) and 'activities' (list).
        """
        auth = get_current_auth()
        result = repo.get_day_with_activities(date, user_id=auth.user_id)
        return {
            "day": dict(result["day"]) if result["day"] else None,
            "activities": [dict(a) for a in result["activities"]],
        }

    # ---- Write tools (readwrite scope only) ----

    @mcp.tool()
    def update_day(
        date: str,
        feeling_text: Optional[str] = None,
        feeling_pain: Optional[int] = None,
        coach_comment: Optional[str] = None,
    ) -> dict:
        """Create or update a daily journal entry.

        Args:
            date: Date in YYYY-MM-DD format.
            feeling_text: Overall feeling description for the day.
            feeling_pain: Overall pain/condition rating (0–10).
            coach_comment: Coach note for the day.

        Returns:
            Updated day dictionary.
        """
        auth = get_current_auth()
        if not auth.can_write():
            raise PermissionError("readwrite scope required")

        if feeling_pain is not None and not (0 <= feeling_pain <= 10):
            raise ValueError(f"feeling_pain must be between 0 and 10, got {feeling_pain}")

        data = {}
        if feeling_text is not None:
            data["feeling_text"] = feeling_text
        if feeling_pain is not None:
            data["feeling_pain"] = feeling_pain
        if coach_comment is not None:
            data["coach_comment"] = coach_comment

        updated = repo.update_day(date, auth.user_id, data)
        return dict(updated) if updated else {}
