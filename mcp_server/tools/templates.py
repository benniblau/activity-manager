"""Training template tools for the MCP server."""

import json
import sqlite3
from typing import Optional

from app.repositories.training_template_repository import TrainingTemplateRepository
from app.repositories.planned_activity_repository import PlannedActivityRepository
from app.utils.errors import AppError
from mcp_server.auth import get_current_auth


def register_template_tools(mcp, conn: sqlite3.Connection) -> None:
    """Register training template read and write tools."""

    repo = TrainingTemplateRepository(db=conn)

    @mcp.tool()
    def list_training_templates(sport_type: Optional[str] = None) -> str:
        """List all training templates for the current user.

        Args:
            sport_type: Optional filter (e.g. 'Run', 'Ride'). Omit for all templates.

        Returns:
            JSON array of template objects including segment_count.
        """
        auth = get_current_auth()
        rows = repo.get_templates(auth.user_id, sport_type=sport_type)
        return json.dumps([dict(r) for r in rows])

    @mcp.tool()
    def get_training_template(template_id: int) -> dict:
        """Get a training template with its full segment list.

        Args:
            template_id: ID of the training template.

        Returns:
            Template dict with a 'segments' list ordered by sort_order.
        """
        auth = get_current_auth()
        return repo.get_template_with_segments(template_id, auth.user_id)

    @mcp.tool()
    def create_training_template(
        name: str,
        sport_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> dict:
        """Create a new training template.

        Args:
            name: Template name (must be unique per user).
            sport_type: Optional base sport type (e.g. 'Run'). If set, the template
                        only appears in the plan picker for that sport.
            description: Optional free-form description.

        Returns:
            Newly created template dict.
        """
        auth = get_current_auth()
        if not auth.can_write():
            raise PermissionError("readwrite scope required")
        return dict(repo.create_template(
            {'name': name, 'sport_type': sport_type, 'description': description},
            auth.user_id,
        ))

    @mcp.tool()
    def add_template_segment(
        template_id: int,
        label: str,
        distance_meters: Optional[float] = None,
        duration_seconds: Optional[int] = None,
        target_pace_sec_per_km: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Add a segment to a training template (appended at the end).

        Args:
            template_id: ID of the template to add the segment to.
            label: Segment label, e.g. 'Warm-up', 'Tempo block', 'Cool-down'.
            distance_meters: Target segment distance in meters.
            duration_seconds: Target segment duration in seconds.
            target_pace_sec_per_km: Target pace in seconds per km (e.g. 300 = 5:00/km).
            notes: Optional free-form notes.

        Returns:
            Newly created segment dict.
        """
        auth = get_current_auth()
        if not auth.can_write():
            raise PermissionError("readwrite scope required")
        return dict(repo.create_segment(template_id, auth.user_id, {
            'label': label,
            'distance_meters': distance_meters,
            'duration_seconds': duration_seconds,
            'target_pace_sec_per_km': target_pace_sec_per_km,
            'notes': notes,
        }))

    @mcp.tool()
    def update_template_segment(
        segment_id: int,
        template_id: int,
        label: Optional[str] = None,
        distance_meters: Optional[float] = None,
        duration_seconds: Optional[int] = None,
        target_pace_sec_per_km: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> dict:
        """Update a segment in a training template.

        Args:
            segment_id: ID of the segment to update.
            template_id: ID of the parent template (for ownership check).
            label: New segment label.
            distance_meters: New distance in meters.
            duration_seconds: New duration in seconds.
            target_pace_sec_per_km: New target pace in seconds per km.
            notes: New notes.

        Returns:
            Updated segment dict.
        """
        auth = get_current_auth()
        if not auth.can_write():
            raise PermissionError("readwrite scope required")
        data = {}
        if label is not None:
            data['label'] = label
        if distance_meters is not None:
            data['distance_meters'] = distance_meters
        if duration_seconds is not None:
            data['duration_seconds'] = duration_seconds
        if target_pace_sec_per_km is not None:
            data['target_pace_sec_per_km'] = target_pace_sec_per_km
        if notes is not None:
            data['notes'] = notes
        return dict(repo.update_segment(segment_id, template_id, auth.user_id, data))

    @mcp.tool()
    def delete_template_segment(segment_id: int, template_id: int) -> dict:
        """Delete a segment from a training template.

        Args:
            segment_id: ID of the segment to delete.
            template_id: ID of the parent template (for ownership check).

        Returns:
            {deleted: True, segment_id: <id>}
        """
        auth = get_current_auth()
        if not auth.can_write():
            raise PermissionError("readwrite scope required")
        repo.delete_segment(segment_id, template_id, auth.user_id)
        return {'deleted': True, 'segment_id': segment_id}

    @mcp.tool()
    def assign_template_to_planned_activity(plan_id: int, template_id: Optional[int] = None) -> dict:
        """Assign (or unassign) a training template to a planned activity.

        Args:
            plan_id: ID of the planned activity.
            template_id: ID of the template to assign, or None/omit to clear.

        Returns:
            {plan_id: <id>, updated: True}
        """
        auth = get_current_auth()
        if not auth.can_write():
            raise PermissionError("readwrite scope required")
        plan_repo = PlannedActivityRepository(db=conn)
        rowcount = plan_repo.update(plan_id, auth.user_id, {'template_id': template_id})
        if rowcount == 0:
            raise ValueError(f"Planned activity {plan_id} not found or access denied")
        return {'plan_id': plan_id, 'updated': True}
