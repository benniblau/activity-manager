"""Custom exception classes for the application"""


class AppError(Exception):
    """Base exception for all application errors"""

    def __init__(self, message, code=None, status_code=500):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.status_code = status_code

    def to_dict(self):
        """Convert exception to dictionary for JSON responses"""
        return {
            'error': self.message,
            'code': self.code
        }


class ActivityNotFoundError(AppError):
    """Raised when an activity cannot be found"""

    def __init__(self, activity_id):
        super().__init__(
            f"Activity with ID {activity_id} not found",
            code="ACTIVITY_NOT_FOUND",
            status_code=404
        )
        self.activity_id = activity_id


class TypeNotFoundError(AppError):
    """Raised when an activity type cannot be found"""

    def __init__(self, type_identifier):
        super().__init__(
            f"Activity type '{type_identifier}' not found",
            code="TYPE_NOT_FOUND",
            status_code=404
        )
        self.type_identifier = type_identifier


class ValidationError(AppError):
    """Raised when data validation fails"""

    def __init__(self, message, field=None):
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            status_code=400
        )
        self.field = field

    def to_dict(self):
        """Include field in error response"""
        result = super().to_dict()
        if self.field:
            result['field'] = self.field
        return result


class StravaAPIError(AppError):
    """Raised when Strava API calls fail"""

    def __init__(self, message, original_error=None):
        super().__init__(
            f"Strava API error: {message}",
            code="STRAVA_API_ERROR",
            status_code=502
        )
        self.original_error = original_error


class RateLimitError(StravaAPIError):
    """Raised when Strava API rate limit is exceeded"""

    def __init__(self, retry_after=None):
        super().__init__(
            "Strava API rate limit exceeded. Please try again later.",
            None
        )
        self.code = "RATE_LIMIT_EXCEEDED"
        self.status_code = 429
        self.retry_after = retry_after

    def to_dict(self):
        """Include retry_after in error response"""
        result = super().to_dict()
        if self.retry_after:
            result['retry_after'] = self.retry_after
        return result


class DatabaseError(AppError):
    """Raised when database operations fail"""

    def __init__(self, message, original_error=None):
        super().__init__(
            f"Database error: {message}",
            code="DATABASE_ERROR",
            status_code=500
        )
        self.original_error = original_error


class DuplicateError(AppError):
    """Raised when attempting to create a duplicate record"""

    def __init__(self, resource, identifier):
        super().__init__(
            f"{resource} with identifier '{identifier}' already exists",
            code="DUPLICATE_ERROR",
            status_code=409
        )
        self.resource = resource
        self.identifier = identifier


