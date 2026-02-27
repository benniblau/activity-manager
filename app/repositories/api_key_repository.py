"""Repository for API key management (MCP server authentication)"""

import hashlib
import secrets
from datetime import datetime
from .base import BaseRepository


class ApiKeyRepository(BaseRepository):
    """Repository for API key CRUD operations"""

    @staticmethod
    def generate_key() -> tuple:
        """Generate a new API key.

        Returns:
            Tuple of (raw_key, key_hash, key_prefix)
            raw_key   = "am_" + 32 hex chars (35 chars total)
            key_hash  = sha256(raw_key) hex digest
            key_prefix = first 11 chars of raw_key ("am_" + 8 chars)
        """
        raw_key = "am_" + secrets.token_hex(16)
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:11]
        return raw_key, key_hash, key_prefix

    def create_key(self, user_id, scope='read', label=None) -> dict:
        """Create a new API key for a user.

        Returns:
            Dict with {id, raw_key, key_prefix, scope, label, created_at}.
            NOTE: raw_key is only returned here, never stored in the database.
        """
        if scope not in ('read', 'readwrite'):
            raise ValueError(f"Invalid scope: {scope}")

        raw_key, key_hash, key_prefix = self.generate_key()
        now = datetime.utcnow().isoformat()

        row_id = self.insert('api_keys', {
            'key_hash': key_hash,
            'key_prefix': key_prefix,
            'user_id': user_id,
            'scope': scope,
            'label': label,
            'created_at': now,
        })

        return {
            'id': row_id,
            'raw_key': raw_key,
            'key_prefix': key_prefix,
            'scope': scope,
            'label': label,
            'created_at': now,
        }

    def validate_key(self, raw_key) -> dict | None:
        """Validate a raw API key and update last_used_at.

        Args:
            raw_key: The full raw key string (e.g. "am_abc123...")

        Returns:
            Dict with {user_id, scope} if valid, None otherwise.
        """
        if not raw_key or not raw_key.startswith('am_'):
            return None

        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        row = self.fetchone(
            'SELECT id, user_id, scope FROM api_keys WHERE key_hash = ?',
            (key_hash,)
        )
        if not row:
            return None

        # Update last_used_at
        db = self.get_db()
        db.execute(
            'UPDATE api_keys SET last_used_at = ? WHERE id = ?',
            (datetime.utcnow().isoformat(), row['id'])
        )
        db.commit()

        return {'user_id': row['user_id'], 'scope': row['scope']}

    def get_keys_for_user(self, user_id) -> list:
        """Return API keys for a user (without hashes).

        Returns:
            List of dicts with {id, key_prefix, scope, label, last_used_at, created_at}.
        """
        return self.fetchall(
            '''SELECT id, key_prefix, scope, label, last_used_at, created_at
               FROM api_keys
               WHERE user_id = ?
               ORDER BY created_at DESC''',
            (user_id,)
        )

    def delete_key(self, key_id, user_id) -> bool:
        """Delete an API key if it belongs to the given user.

        Returns:
            True if deleted, False if not found or not owned by user.
        """
        db = self.get_db()
        cursor = db.execute(
            'DELETE FROM api_keys WHERE id = ? AND user_id = ?',
            (key_id, user_id)
        )
        db.commit()
        return cursor.rowcount > 0
