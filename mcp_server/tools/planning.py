"""Planned activity tools for the MCP server."""

import sqlite3
from typing import Optional

from app.repositories.planned_activity_repository import PlannedActivityRepository
from mcp_server.auth import AuthContext


def register_planning_tools(mcp, conn: sqlite3.Connection, auth: AuthContext) -> None:
    """Register planning read (and optionally write) tools."""

    repo = PlannedActivityRepository(db=conn)

    @mcp.tool()
    def get_planned_day(date: str) -> list:
        """Get planned activities for a specific day.

        Args:
            date: Date in YYYY-MM-DD format.

        Returns:
            List of planned activity dictionaries ordered by sort_order.
        """
        rows = repo.get_by_day(date, auth.user_id)
        return [dict(r) for r in rows]

    @mcp.tool()
    def get_planned_week(start_date: str, end_date: str) -> list:
        """Get planned activities for a date range.

        Args:
            start_date: Start date (YYYY-MM-DD), inclusive.
            end_date: End date (YYYY-MM-DD), inclusive.

        Returns:
            List of planned activity dictionaries ordered by date then sort_order.
        """
        rows = repo.get_by_week(start_date, end_date, auth.user_id)
        return [dict(r) for r in rows]

    # ---- Write tools (readwrite scope only) ----

    if auth.can_write():

        @mcp.tool()
        def create_planned_activity(
            day_date: str,
            sport_type: Optional[str] = None,
            extended_type_id: Optional[int] = None,
            planned_distance: Optional[float] = None,
            planned_duration: Optional[int] = None,
            notes: Optional[str] = None,
        ) -> dict:
            """Create a new planned activity on a training calendar day.

            Args:
                day_date: Date in YYYY-MM-DD format.
                sport_type: Standard sport type (e.g. 'Run', 'Ride').
                extended_type_id: Extended type ID for sub-classification.
                planned_distance: Target distance in meters.
                planned_duration: Target duration in seconds.
                notes: Free-form notes for the planned workout.

            Returns:
                The newly created planned activity dictionary.
            """
            data = {"user_id": auth.user_id, "day_date": day_date}
            if sport_type is not None:
                data["sport_type"] = sport_type
            if extended_type_id is not None:
                data["extended_type_id"] = extended_type_id
            if planned_distance is not None:
                data["planned_distance"] = planned_distance
            if planned_duration is not None:
                data["planned_duration"] = planned_duration
            if notes is not None:
                data["notes"] = notes

            new_id = repo.create(data)

            # Return the newly created row
            day_plans = repo.get_by_day(day_date, auth.user_id)
            for plan in day_plans:
                if plan["id"] == new_id:
                    return dict(plan)
            return {"id": new_id}

        @mcp.tool()
        def update_planned_activity(
            plan_id: int,
            sport_type: Optional[str] = None,
            extended_type_id: Optional[int] = None,
            planned_distance: Optional[float] = None,
            planned_duration: Optional[int] = None,
            notes: Optional[str] = None,
            matched_activity_id: Optional[int] = None,
        ) -> dict:
            """Update an existing planned activity.

            Args:
                plan_id: ID of the planned activity to update.
                sport_type: Standard sport type.
                extended_type_id: Extended type ID.
                planned_distance: Target distance in meters.
                planned_duration: Target duration in seconds.
                notes: Free-form notes.
                matched_activity_id: ID of an actual activity to link.

            Returns:
                Updated planned activity as a dict with a 'rowcount' key.
            """
            data = {}
            if sport_type is not None:
                data["sport_type"] = sport_type
            if extended_type_id is not None:
                data["extended_type_id"] = extended_type_id
            if planned_distance is not None:
                data["planned_distance"] = planned_distance
            if planned_duration is not None:
                data["planned_duration"] = planned_duration
            if notes is not None:
                data["notes"] = notes
            if matched_activity_id is not None:
                data["matched_activity_id"] = matched_activity_id

            rowcount = repo.update(plan_id, auth.user_id, data)
            if rowcount == 0:
                raise ValueError(f"Planned activity {plan_id} not found or access denied")

            return {"plan_id": plan_id, "updated": True}

        @mcp.tool()
        def delete_planned_activity(plan_id: int) -> dict:
            """Delete a planned activity from the training calendar.

            Args:
                plan_id: ID of the planned activity to delete.

            Returns:
                Dict with {deleted: True, plan_id: <id>}.
            """
            rowcount = repo.delete(plan_id, auth.user_id)
            if rowcount == 0:
                raise ValueError(f"Planned activity {plan_id} not found or access denied")
            return {"deleted": True, "plan_id": plan_id}
