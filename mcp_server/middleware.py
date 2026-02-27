"""ASGI middleware for per-request API key authentication (SSE transport)."""

import json
import sqlite3

from mcp_server.auth import resolve_auth, set_current_auth

# Paths that are publicly accessible without authentication.
_PUBLIC_PREFIXES = ("/.well-known/", "/oauth/")


class ApiKeyMiddleware:
    """Pure ASGI middleware that authenticates every HTTP request via API key.

    Accepts the key from either:
      - Authorization: Bearer <key>
      - X-API-Key: <key>

    Public paths (/.well-known/*, /oauth/*) are forwarded without auth.

    On authentication failure returns a 401 with:
      - WWW-Authenticate: Bearer realm="activity-manager", resource_metadata="<url>"
      - JSON body: {"error": "...", "error_description": "..."}
    """

    def __init__(self, app, conn: sqlite3.Connection, base_url: str = "") -> None:
        self.app = app
        self.conn = conn
        self._resource_metadata_url = (
            f"{base_url}/.well-known/oauth-protected-resource" if base_url else ""
        )

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Public discovery endpoints — no auth required.
        path = scope.get("path", "")
        if any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        auth_header = headers.get(b"authorization", b"").decode()
        api_key_header = headers.get(b"x-api-key", b"").decode()

        api_key = ""
        if auth_header.lower().startswith("bearer "):
            api_key = auth_header[7:].strip()
        if not api_key:
            api_key = api_key_header.strip()

        try:
            auth = resolve_auth(self.conn, api_key)
        except PermissionError as exc:
            await self._send_401(send, str(exc))
            return

        set_current_auth(auth)
        await self.app(scope, receive, send)

    async def _send_401(self, send, error_description: str) -> None:
        body = json.dumps(
            {"error": "invalid_token", "error_description": error_description}
        ).encode()

        www_auth = 'Bearer realm="activity-manager"'
        if self._resource_metadata_url:
            www_auth += f', resource_metadata="{self._resource_metadata_url}"'

        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                    [b"www-authenticate", www_auth.encode()],
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
