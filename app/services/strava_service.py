"""Strava service for handling Strava API interactions"""

import time
from datetime import datetime
from app.repositories import ActivityRepository, TypeRepository
from app.utils.errors import StravaAPIError, RateLimitError, ValidationError
from app.utils.database_helpers import dict_to_db_values


class StravaService:
    """Service for Strava API operations and data synchronization"""

    def __init__(self, strava_client, db=None, user_id=None):
        """Initialize Strava service

        Args:
            strava_client: Initialized Strava API client (stravalib.Client)
            db: Optional database connection (for testing)
            user_id: User ID for multi-user support (required)
        """
        self.client = strava_client
        self.activity_repo = ActivityRepository(db)
        self.type_repo = TypeRepository(db)
        self.user_id = user_id
        self._validated_sport_types = set()  # Cache for validated sport types

    def sync_activities(self, limit=30, after=None, before=None, fetch_details=True):
        """Sync activities from Strava

        Args:
            limit: Maximum number of activities to fetch (default: 30, max: 200)
            after: Fetch activities after this Unix timestamp
            before: Fetch activities before this Unix timestamp
            fetch_details: If True, fetch full details (including description) for new activities

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

        print(f"[Strava Sync] Starting sync: limit={limit}, after={after}, before={before}, fetch_details={fetch_details}")

        try:
            # Fetch activities from Strava
            strava_activities = self.client.get_activities(
                limit=limit,
                after=after,
                before=before
            )

            # Convert generator to list to get count
            activities_list = list(strava_activities)
            print(f"[Strava Sync] Fetched {len(activities_list)} activities from Strava")

            created_count = 0
            updated_count = 0
            skipped_count = 0
            errors = []

            # Disable auto-commit for batch operation (much faster)
            self.activity_repo.set_auto_commit(False)
            self.type_repo.set_auto_commit(False)

            try:
                # Process each activity
                for strava_activity in activities_list:
                    try:
                        activity_id = self._extract_value(strava_activity, 'id')
                        activity_name = self._extract_value(strava_activity, 'name')

                        if not activity_id:
                            print(f"[Strava Sync] Skipping activity with no ID: {strava_activity}")
                            skipped_count += 1
                            continue

                        # Check if activity already exists
                        existing = self.activity_repo.get_by_id('activities', activity_id)

                        if existing:
                            # Check if existing activity is missing description
                            needs_details = fetch_details and not existing.get('description')

                            if needs_details:
                                try:
                                    # Fetch full details to get description
                                    detailed_activity = self.client.get_activity(activity_id)
                                    activity_data = self.transform_strava_data(detailed_activity)
                                except Exception as detail_err:
                                    print(f"[Strava Sync] Failed to fetch details for {activity_id}: {detail_err}")
                                    # Fall back to summary data if detail fetch fails
                                    activity_data = self.transform_strava_data(strava_activity)
                            else:
                                # Update with summary data
                                activity_data = self.transform_strava_data(strava_activity)

                            self.upsert_activity(activity_data)
                            updated_count += 1
                            print(f"[Strava Sync] Updated: {activity_id} - {activity_name}")
                        else:
                            # New activity - fetch full details if requested
                            if fetch_details:
                                try:
                                    # Fetch full details (includes description)
                                    detailed_activity = self.client.get_activity(activity_id)
                                    activity_data = self.transform_strava_data(detailed_activity)
                                except Exception as detail_err:
                                    print(f"[Strava Sync] Failed to fetch details for new activity {activity_id}: {detail_err}")
                                    # Fall back to summary data if detail fetch fails
                                    activity_data = self.transform_strava_data(strava_activity)
                            else:
                                activity_data = self.transform_strava_data(strava_activity)

                            # Validate required fields before insert
                            missing_fields = []
                            for field in ['name', 'sport_type', 'start_date_local', 'elapsed_time']:
                                if not activity_data.get(field):
                                    missing_fields.append(field)

                            if missing_fields:
                                print(f"[Strava Sync] Activity {activity_id} missing required fields: {missing_fields}")
                                print(f"[Strava Sync] Activity data: {activity_data}")
                                errors.append({
                                    'activity_id': activity_id,
                                    'error': f'Missing required fields: {missing_fields}'
                                })
                                continue

                            self.upsert_activity(activity_data)
                            created_count += 1
                            print(f"[Strava Sync] Created: {activity_id} - {activity_name}")

                    except Exception as e:
                        import traceback
                        activity_id = getattr(strava_activity, 'id', 'unknown')
                        print(f"[Strava Sync] Error processing activity {activity_id}: {e}")
                        print(traceback.format_exc())
                        errors.append({
                            'activity_id': activity_id,
                            'error': str(e)
                        })

                # Commit all changes at once
                self.activity_repo.commit()
                self.type_repo.commit()
                print(f"[Strava Sync] Committed changes to database")

            finally:
                # Re-enable auto-commit
                self.activity_repo.set_auto_commit(True)
                self.type_repo.set_auto_commit(True)

            result_msg = f'Sync completed: {created_count} created, {updated_count} updated'
            if skipped_count > 0:
                result_msg += f', {skipped_count} skipped'
            if errors:
                result_msg += f', {len(errors)} errors'

            print(f"[Strava Sync] {result_msg}")

            return {
                'created': created_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'errors': errors,
                'message': result_msg
            }

        except Exception as e:
            import traceback
            error_msg = str(e)
            print(f"[Strava Sync] Fatal error: {error_msg}")
            print(traceback.format_exc())

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

    def _extract_value(self, obj, attr_name):
        """Extract value from stravalib object, handling various formats"""
        if not hasattr(obj, attr_name):
            return None

        value = getattr(obj, attr_name)

        if value is None:
            return None

        # Handle pydantic RootModel (has 'root' attribute)
        if hasattr(value, 'root'):
            value = value.root

        # Handle enums
        if hasattr(value, 'value'):
            value = value.value

        # Handle datetime objects
        if hasattr(value, 'isoformat'):
            return value.isoformat()

        # Handle "root='Value'" string pattern
        if isinstance(value, str):
            if value.startswith("root='") and value.endswith("'"):
                return value[6:-1]
            if value == 'None':
                return None

        return value

    def transform_strava_data(self, strava_activity):
        """Transform Strava activity object to database format

        Args:
            strava_activity: Strava activity object from stravalib

        Returns:
            Dictionary with activity data ready for database

        Raises:
            ValidationError: If required fields are missing
        """
        # Build activity data by extracting attributes directly from stravalib object
        # This is more reliable than to_dict() which may not include all fields
        activity_data = {}

        # Required fields
        activity_data['id'] = self._extract_value(strava_activity, 'id')
        activity_data['name'] = self._extract_value(strava_activity, 'name')

        # Sport type - try sport_type first, then type
        sport_type = self._extract_value(strava_activity, 'sport_type')
        if not sport_type:
            sport_type = self._extract_value(strava_activity, 'type')
        if not sport_type:
            sport_type = 'Workout'
        # Clean up sport type if it has the weird format
        if isinstance(sport_type, str) and '/' in sport_type:
            parts = sport_type.split('/')
            if len(parts) == 2:
                sport_type = ''.join(word.capitalize() for word in parts[1].replace('(', '').replace(')', '').split())
        activity_data['sport_type'] = sport_type

        # Time fields
        activity_data['start_date'] = self._extract_value(strava_activity, 'start_date')
        activity_data['start_date_local'] = self._extract_value(strava_activity, 'start_date_local')
        activity_data['elapsed_time'] = self._extract_value(strava_activity, 'elapsed_time')
        activity_data['moving_time'] = self._extract_value(strava_activity, 'moving_time')

        # Distance and elevation
        activity_data['distance'] = self._extract_value(strava_activity, 'distance')
        activity_data['total_elevation_gain'] = self._extract_value(strava_activity, 'total_elevation_gain')

        # Heart rate
        activity_data['average_heartrate'] = self._extract_value(strava_activity, 'average_heartrate')
        activity_data['max_heartrate'] = self._extract_value(strava_activity, 'max_heartrate')
        activity_data['has_heartrate'] = self._extract_value(strava_activity, 'has_heartrate')

        # Speed
        activity_data['average_speed'] = self._extract_value(strava_activity, 'average_speed')
        activity_data['max_speed'] = self._extract_value(strava_activity, 'max_speed')

        # Power/watts
        activity_data['average_watts'] = self._extract_value(strava_activity, 'average_watts')
        activity_data['max_watts'] = self._extract_value(strava_activity, 'max_watts')
        activity_data['weighted_average_watts'] = self._extract_value(strava_activity, 'weighted_average_watts')
        activity_data['device_watts'] = self._extract_value(strava_activity, 'device_watts')
        activity_data['kilojoules'] = self._extract_value(strava_activity, 'kilojoules')

        # Cadence
        activity_data['average_cadence'] = self._extract_value(strava_activity, 'average_cadence')
        activity_data['max_cadence'] = self._extract_value(strava_activity, 'max_cadence')

        # Calories
        activity_data['calories'] = self._extract_value(strava_activity, 'calories')

        # Elevation details
        activity_data['elev_high'] = self._extract_value(strava_activity, 'elev_high')
        activity_data['elev_low'] = self._extract_value(strava_activity, 'elev_low')

        # Temperature
        activity_data['average_temp'] = self._extract_value(strava_activity, 'average_temp')

        # Perceived exertion
        activity_data['perceived_exertion'] = self._extract_value(strava_activity, 'perceived_exertion')
        activity_data['prefer_perceived_exertion'] = self._extract_value(strava_activity, 'prefer_perceived_exertion')

        # Location
        activity_data['start_latlng'] = self._extract_value(strava_activity, 'start_latlng')
        activity_data['end_latlng'] = self._extract_value(strava_activity, 'end_latlng')
        activity_data['timezone'] = self._extract_value(strava_activity, 'timezone')
        activity_data['utc_offset'] = self._extract_value(strava_activity, 'utc_offset')
        activity_data['location_city'] = self._extract_value(strava_activity, 'location_city')
        activity_data['location_state'] = self._extract_value(strava_activity, 'location_state')
        activity_data['location_country'] = self._extract_value(strava_activity, 'location_country')

        # Identifiers
        activity_data['resource_state'] = self._extract_value(strava_activity, 'resource_state')
        activity_data['external_id'] = self._extract_value(strava_activity, 'external_id')
        activity_data['upload_id'] = self._extract_value(strava_activity, 'upload_id')
        activity_data['workout_type'] = self._extract_value(strava_activity, 'workout_type')

        # Flags
        activity_data['trainer'] = self._extract_value(strava_activity, 'trainer')
        activity_data['commute'] = self._extract_value(strava_activity, 'commute')
        activity_data['manual'] = self._extract_value(strava_activity, 'manual')
        activity_data['private'] = self._extract_value(strava_activity, 'private')
        activity_data['flagged'] = self._extract_value(strava_activity, 'flagged')
        activity_data['has_kudoed'] = self._extract_value(strava_activity, 'has_kudoed')

        # Social & engagement
        activity_data['kudos_count'] = self._extract_value(strava_activity, 'kudos_count')
        activity_data['comment_count'] = self._extract_value(strava_activity, 'comment_count')
        activity_data['athlete_count'] = self._extract_value(strava_activity, 'athlete_count')
        activity_data['photo_count'] = self._extract_value(strava_activity, 'photo_count')
        activity_data['total_photo_count'] = self._extract_value(strava_activity, 'total_photo_count')
        activity_data['pr_count'] = self._extract_value(strava_activity, 'pr_count')
        activity_data['achievement_count'] = self._extract_value(strava_activity, 'achievement_count')

        # Device
        activity_data['device_name'] = self._extract_value(strava_activity, 'device_name')

        # Gear
        gear = self._extract_value(strava_activity, 'gear')
        if gear:
            if hasattr(gear, 'id'):
                activity_data['gear_id'] = gear.id
            elif isinstance(gear, dict):
                activity_data['gear_id'] = gear.get('id')

        # Description (only available in detailed activity)
        desc = self._extract_value(strava_activity, 'description')
        if desc and str(desc).strip() and str(desc) != 'None':
            activity_data['description'] = str(desc)

        # Map data
        activity_data['map'] = self._extract_value(strava_activity, 'map')

        # Clean up None values for optional fields but keep required fields even if None
        required_fields = {'id', 'name', 'sport_type', 'start_date_local', 'elapsed_time'}
        activity_data = {k: v for k, v in activity_data.items() if v is not None or k in required_fields}

        # Ensure elapsed_time has a default if missing
        if activity_data.get('elapsed_time') is None:
            activity_data['elapsed_time'] = activity_data.get('moving_time', 0)

        # Auto-create sport type if it doesn't exist in standard types
        # Use cache to avoid repeated database queries
        sport_type = activity_data['sport_type']
        if sport_type not in self._validated_sport_types:
            if not self.type_repo.validate_sport_type(sport_type):
                self.type_repo.auto_create_type(sport_type)
            self._validated_sport_types.add(sport_type)

        # Calculate day_date from start_date_local
        if activity_data.get('start_date_local'):
            try:
                # Parse the datetime and extract just the date
                start_local = activity_data['start_date_local']
                if isinstance(start_local, str):
                    dt = datetime.fromisoformat(start_local.replace('Z', '+00:00'))
                else:
                    dt = start_local

                activity_data['day_date'] = dt.date().isoformat()
            except Exception:
                # If parsing fails, use start_date_local as is (already YYYY-MM-DD)
                pass

        # Debug logging
        print(f"[Strava Sync] Transformed activity {activity_data.get('id')}: {activity_data.get('name')} ({activity_data.get('sport_type')})")

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

        # Add user_id to activity data
        if self.user_id:
            activity_data['user_id'] = self.user_id

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
