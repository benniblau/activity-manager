"""ASGI middleware for per-request API key authentication (HTTP transport)."""

import json
import sqlite3

from mcp_server.auth import resolve_auth, set_current_auth


class ApiKeyMiddleware:
    """Pure ASGI middleware that authenticates every HTTP request via API key.

    Accepts the key from either:
      - Authorization: Bearer <key>
      - X-API-Key: <key>

    On authentication failure returns a 401 with a WWW-Authenticate header.
    """

    def __init__(self, app, conn: sqlite3.Connection) -> None:
        self.app = app
        self.conn = conn

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        auth = self._auth_from_key(headers)

        if auth is None:
            await self._send_401(send, "Missing or invalid API key")
            return

        set_current_auth(auth)
        await self.app(scope, receive, send)

    def _auth_from_key(self, headers: dict):
        auth_header = headers.get(b"authorization", b"").decode()
        api_key_header = headers.get(b"x-api-key", b"").decode()

        api_key = ""
        if auth_header.lower().startswith("bearer "):
            api_key = auth_header[7:].strip()
        if not api_key:
            api_key = api_key_header.strip()

        if not api_key:
            return None
        try:
            return resolve_auth(self.conn, api_key)
        except PermissionError:
            return None

    async def _send_401(self, send, error_description: str) -> None:
        body = json.dumps(
            {"error": "invalid_token", "error_description": error_description}
        ).encode()

        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                    [b"www-authenticate", b'Bearer realm="activity-manager"'],
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
