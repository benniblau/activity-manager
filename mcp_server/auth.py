"""Resolve AM_API_KEY environment variable → AuthContext."""

import sqlite3
import sys
from dataclasses import dataclass

from app.repositories.api_key_repository import ApiKeyRepository


@dataclass
class AuthContext:
    user_id: int
    scope: str

    def can_write(self) -> bool:
        return self.scope == "readwrite"


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
