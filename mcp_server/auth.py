"""API key authentication and per-request auth context."""

import sqlite3
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from app.repositories.api_key_repository import ApiKeyRepository


@dataclass
class AuthContext:
    user_id: int
    scope: str

    def can_write(self) -> bool:
        return self.scope == "readwrite"


# Per-async-task (per-request) auth context — set by middleware or server startup.
_current_auth: ContextVar[Optional[AuthContext]] = ContextVar("current_auth", default=None)


def get_current_auth() -> AuthContext:
    """Return the AuthContext for the current request/task.

    Raises:
        PermissionError: If no auth context has been set (unauthenticated request).
    """
    auth = _current_auth.get()
    if auth is None:
        raise PermissionError("Unauthenticated — missing or invalid API key")
    return auth


def set_current_auth(auth: AuthContext) -> None:
    """Set the AuthContext for the current async task."""
    _current_auth.set(auth)


def resolve_auth(conn: sqlite3.Connection, raw_key: str) -> AuthContext:
    """Validate the raw API key and return an AuthContext.

    Args:
        conn: Open sqlite3 connection.
        raw_key: The value of AM_API_KEY from the environment.

    Returns:
        AuthContext with user_id and scope.

    Raises:
        PermissionError: If the key is missing, invalid, or the user is inactive.
    """
    if not raw_key or not raw_key.startswith("am_"):
        raise PermissionError("AM_API_KEY is missing or malformed (must start with 'am_')")

    repo = ApiKeyRepository(db=conn)
    result = repo.validate_key(raw_key)

    if result is None:
        raise PermissionError("Invalid API key")

    # Verify the user is active
    cursor = conn.execute(
        "SELECT is_active FROM users WHERE id = ?", (result["user_id"],)
    )
    row = cursor.fetchone()
    if not row or not row["is_active"]:
        raise PermissionError("User account is not active")

    return AuthContext(user_id=result["user_id"], scope=result["scope"])
