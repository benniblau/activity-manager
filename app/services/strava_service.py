"""Strava service for handling Strava API interactions"""

import time
from datetime import datetime
from app.repositories import ActivityRepository, TypeRepository
from app.utils.errors import StravaAPIError, RateLimitError, ValidationError
from app.utils.database_helpers import dict_to_db_values


class StravaService:
    """Service for Strava API operations and data synchronization"""

    def __init__(self, strava_client, db=None):
        """Initialize Strava service

        Args:
            strava_client: Initialized Strava API client (stravalib.Client)
            db: Optional database connection (for testing)
        """
        self.client = strava_client
        self.activity_repo = ActivityRepository(db)
        self.type_repo = TypeRepository(db)
        self._validated_sport_types = set()  # Cache for validated sport types

    def sync_activities(self, limit=30, after=None, before=None):
        """Sync activities from Strava

        Args:
            limit: Maximum number of activities to fetch (default: 30, max: 200)
            after: Fetch activities after this Unix timestamp
            before: Fetch activities before this Unix timestamp

        Returns:
            Dictionary with sync results:
                - created: Number of new activities created
                - updated: Number of activities updated
                - errors: List of errors (activity_id, error message)
                - message: Summary message

        Raises:
            StravaAPIError: If Strava API call fails
            RateLimitError: If rate limit is exceeded
        """
        # Validate and cap limit
        if limit > 200:
            limit = 200

        try:
            # Fetch activities from Strava
            strava_activities = self.client.get_activities(
                limit=limit,
                after=after,
                before=before
            )

            created_count = 0
            updated_count = 0
            errors = []

            # Disable auto-commit for batch operation (much faster)
            self.activity_repo.set_auto_commit(False)
            self.type_repo.set_auto_commit(False)

            try:
                # Process each activity
                for strava_activity in strava_activities:
                    try:
                        # Use summary data directly (no additional API call for details)
                        # This is much faster but won't include description field
                        activity_data = self.transform_strava_data(strava_activity)
                        created, _ = self.upsert_activity(activity_data)

                        if created:
                            created_count += 1
                        else:
                            updated_count += 1

                    except Exception as e:
                        errors.append({
                            'activity_id': strava_activity.id,
                            'error': str(e)
                        })

                # Commit all changes at once
                self.activity_repo.commit()
                self.type_repo.commit()

            finally:
                # Re-enable auto-commit
                self.activity_repo.set_auto_commit(True)
                self.type_repo.set_auto_commit(True)

            return {
                'created': created_count,
                'updated': updated_count,
                'errors': errors,
                'message': f'Sync completed: {created_count} created, {updated_count} updated'
            }

        except Exception as e:
            error_msg = str(e)

            # Check for rate limit error
            if '429' in error_msg or 'rate limit' in error_msg.lower():
                raise RateLimitError()

            raise StravaAPIError(f"Failed to sync activities: {error_msg}", e)

    def fetch_activity_details(self, activity_id):
        """Fetch full details for a single activity

        Args:
            activity_id: Strava activity ID

        Returns:
            Activity dictionary

        Raises:
            StravaAPIError: If fetch fails
        """
        try:
            activity = self.client.get_activity(activity_id)
            return self.transform_strava_data(activity)
        except Exception as e:
            raise StravaAPIError(f"Failed to fetch activity {activity_id}: {str(e)}", e)

    def transform_strava_data(self, strava_activity):
        """Transform Strava activity object to database format

        Args:
            strava_activity: Strava activity object from stravalib

        Returns:
            Dictionary with activity data ready for database

        Raises:
            ValidationError: If required fields are missing
        """
        # Convert to dict
        if hasattr(strava_activity, 'to_dict'):
            activity_data = strava_activity.to_dict()
        else:
            activity_data = dict(strava_activity)

        # Explicitly add description if it exists
        # (to_dict() might not include it)
        if hasattr(strava_activity, 'description') and strava_activity.description:
            activity_data['description'] = strava_activity.description

        # Ensure sport_type exists
        if 'sport_type' not in activity_data or not activity_data['sport_type']:
            # Fallback to 'type' field or default
            activity_data['sport_type'] = activity_data.get('type', 'Workout')

        # Auto-create sport type if it doesn't exist in standard types
        # Use cache to avoid repeated database queries
        sport_type = activity_data['sport_type']
        if sport_type not in self._validated_sport_types:
            if not self.type_repo.validate_sport_type(sport_type):
                self.type_repo.auto_create_type(sport_type)
            self._validated_sport_types.add(sport_type)

        # Calculate day_date from start_date_local
        if 'start_date_local' in activity_data:
            try:
                # Parse the datetime and extract just the date
                if isinstance(activity_data['start_date_local'], str):
                    dt = datetime.fromisoformat(
                        activity_data['start_date_local'].replace('Z', '+00:00')
                    )
                else:
                    dt = activity_data['start_date_local']

                activity_data['day_date'] = dt.date().isoformat()
            except Exception:
                # If parsing fails, use start_date_local as is (already YYYY-MM-DD)
                pass

        return activity_data

    def upsert_activity(self, activity_data):
        """Insert or update an activity

        Args:
            activity_data: Activity data dictionary (must include 'id')

        Returns:
            Tuple of (created: bool, activity: dict)
                - created: True if new activity, False if updated
                - activity: The resulting activity dictionary

        Raises:
            ValidationError: If data is invalid
        """
        if 'id' not in activity_data:
            raise ValidationError("Activity data must include 'id'")

        # Use repository upsert method
        return self.activity_repo.upsert_from_strava(activity_data)

    def sync_single_activity(self, activity_id):
        """Sync a single activity from Strava

        Args:
            activity_id: Strava activity ID

        Returns:
            Dictionary with:
                - created: Boolean
                - activity: Activity dictionary
                - message: Success message

        Raises:
            StravaAPIError: If sync fails
        """
        try:
            # Fetch full details
            activity_data = self.fetch_activity_details(activity_id)

            # Upsert
            created, activity = self.upsert_activity(activity_data)

            action = 'created' if created else 'updated'
            return {
                'created': created,
                'activity': activity,
                'message': f'Activity {action} successfully'
            }

        except Exception as e:
            raise StravaAPIError(f"Failed to sync activity {activity_id}: {str(e)}", e)

    def handle_rate_limit(self, retry_after=60):
        """Handle rate limit by waiting

        Args:
            retry_after: Seconds to wait (default: 60)

        Note: This is a simple implementation. For production, consider:
        - Exponential backoff
        - Queue-based retry mechanism
        - Better error reporting to user
        """
        time.sleep(retry_after)

    def get_athlete_stats(self):
        """Get athlete statistics from Strava

        Returns:
            Dictionary with athlete stats

        Raises:
            StravaAPIError: If fetch fails
        """
        try:
            athlete = self.client.get_athlete()
            return {
                'id': athlete.id,
                'firstname': athlete.firstname,
                'lastname': athlete.lastname,
                'profile': athlete.profile,
                'city': athlete.city,
                'state': athlete.state,
                'country': athlete.country
            }
        except Exception as e:
            raise StravaAPIError(f"Failed to fetch athlete stats: {str(e)}", e)
