"""Activity tools for the MCP server."""

import sqlite3
from typing import Optional

from app.repositories.activity_repository import ActivityRepository
from mcp_server.auth import get_current_auth


def register_activity_tools(mcp, conn: sqlite3.Connection) -> None:
    """Register activity read and write tools."""

    repo = ActivityRepository(db=conn)

    @mcp.tool()
    def get_activity(activity_id: int) -> dict:
        """Get a single activity by ID.

        Args:
            activity_id: The Strava activity ID.

        Returns:
            Activity dictionary with all fields.
        """
        auth = get_current_auth()
        try:
            return dict(repo.get_activity(activity_id, user_id=auth.user_id))
        except Exception as exc:
            raise ValueError(f"Activity {activity_id} not found: {exc}")

    @mcp.tool()
    def list_activities(
        sport_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        extended_type_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list:
        """List activities with optional filters.

        Args:
            sport_type: Filter by sport type (e.g. 'Run', 'Ride').
            start_date: ISO date string (YYYY-MM-DD), inclusive lower bound.
            end_date: ISO date string (YYYY-MM-DD), inclusive upper bound.
            extended_type_id: Filter by extended type ID.
            limit: Max results to return (capped at 200).
            offset: Number of results to skip for pagination.

        Returns:
            List of activity dictionaries.
        """
        auth = get_current_auth()
        filters = {}
        if sport_type:
            filters["sport_type"] = sport_type
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date
        if extended_type_id is not None:
            filters["extended_type_id"] = extended_type_id

        rows = repo.get_activities(
            filters=filters,
            limit=min(limit, 200),
            offset=offset,
            user_id=auth.user_id,
        )
        return [dict(r) for r in rows]

    @mcp.tool()
    def search_activities(query: str, limit: int = 20) -> list:
        """Full-text search activities by name or description.

        Args:
            query: Search string (case-insensitive).
            limit: Max results to return.

        Returns:
            List of matching activity dictionaries.
        """
        auth = get_current_auth()
        q = query.lower()
        all_activities = repo.get_activities(user_id=auth.user_id, limit=1000)
        matches = [
            dict(a) for a in all_activities
            if q in (a.get("name") or "").lower()
            or q in (a.get("description") or "").lower()
        ]
        return matches[:limit]

    @mcp.tool()
    def get_activity_stats(
        sport_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """Aggregate statistics across activities.

        Args:
            sport_type: Optional filter by sport type.
            start_date: Optional lower date bound (YYYY-MM-DD).
            end_date: Optional upper date bound (YYYY-MM-DD).

        Returns:
            Dict with total_count, total_distance_km, total_elevation_m,
            total_time_hours, avg_distance_km.
        """
        auth = get_current_auth()
        filters = {}
        if sport_type:
            filters["sport_type"] = sport_type
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date

        activities = repo.get_activities(
            filters=filters, limit=10000, user_id=auth.user_id
        )

        total = len(activities)
        total_dist = sum((a.get("distance") or 0) for a in activities)
        total_elev = sum((a.get("total_elevation_gain") or 0) for a in activities)
        total_time = sum((a.get("moving_time") or 0) for a in activities)

        return {
            "total_count": total,
            "total_distance_km": round(total_dist / 1000, 2),
            "total_elevation_m": round(total_elev, 1),
            "total_time_hours": round(total_time / 3600, 2),
            "avg_distance_km": round(total_dist / 1000 / total, 2) if total else 0,
        }

    # ---- Write tools (readwrite scope only) ----

    @mcp.tool()
    def update_activity_annotation(
        activity_id: int,
        feeling_before_text: Optional[str] = None,
        feeling_before_pain: Optional[int] = None,
        feeling_during_text: Optional[str] = None,
        feeling_during_pain: Optional[int] = None,
        feeling_after_text: Optional[str] = None,
        feeling_after_pain: Optional[int] = None,
        coach_comment: Optional[str] = None,
        extended_type_id: Optional[int] = None,
    ) -> dict:
        """Update feeling annotations and optional extended type for an activity.

        Args:
            activity_id: Activity ID to update.
            feeling_before_text: How you felt before the activity.
            feeling_before_pain: Pain level before (0–10).
            feeling_during_text: How you felt during the activity.
            feeling_during_pain: Pain level during (0–10).
            feeling_after_text: How you felt after the activity.
            feeling_after_pain: Pain level after (0–10).
            coach_comment: Coach comment to attach.
            extended_type_id: Extended activity type ID.

        Returns:
            Updated activity dictionary.
        """
        auth = get_current_auth()
        if not auth.can_write():
            raise PermissionError("readwrite scope required")

        # Validate ownership
        try:
            repo.get_activity(activity_id, user_id=auth.user_id)
        except Exception:
            raise ValueError(f"Activity {activity_id} not found or access denied")

        # Validate pain values
        for field, val in [
            ("feeling_before_pain", feeling_before_pain),
            ("feeling_during_pain", feeling_during_pain),
            ("feeling_after_pain", feeling_after_pain),
        ]:
            if val is not None and not (0 <= val <= 10):
                raise ValueError(f"{field} must be between 0 and 10, got {val}")

        data = {}
        if feeling_before_text is not None:
            data["feeling_before_text"] = feeling_before_text
        if feeling_before_pain is not None:
            data["feeling_before_pain"] = feeling_before_pain
        if feeling_during_text is not None:
            data["feeling_during_text"] = feeling_during_text
        if feeling_during_pain is not None:
            data["feeling_during_pain"] = feeling_during_pain
        if feeling_after_text is not None:
            data["feeling_after_text"] = feeling_after_text
        if feeling_after_pain is not None:
            data["feeling_after_pain"] = feeling_after_pain
        if coach_comment is not None:
            data["coach_comment"] = coach_comment
        if extended_type_id is not None:
            data["extended_type_id"] = extended_type_id

        updated = repo.update_activity(activity_id, data)
        return dict(updated)
