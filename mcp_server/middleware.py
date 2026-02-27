"""ASGI middleware for per-request API key authentication (HTTP transports)."""

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

    Session-based auth (no repeat key needed):
      MCP clients such as mcporter send the API key with the initial
      'initialize' request but omit it from subsequent requests, relying on
      the Mcp-Session-Id to prove prior authentication.  To support this, the
      middleware caches {session_id → auth} when a new session is created
      (detected by a Mcp-Session-Id header on the response).  A request that
      carries a known session ID is accepted without re-presenting the key.

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
        # Maps Mcp-Session-Id → AuthContext for sessions that have already
        # authenticated.  Populated on the first successful request that
        # produces a new session ID in the response headers.
        self._session_auth: dict = {}

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

        # ── 1. Try API key from request headers ───────────────────────────────
        auth = self._auth_from_key(headers)

        # ── 2. Fall back to session-based auth ────────────────────────────────
        if auth is None:
            session_id = headers.get(b"mcp-session-id", b"").decode().strip()
            if session_id:
                auth = self._session_auth.get(session_id)

        if auth is None:
            await self._send_401(send, "Missing or invalid API key")
            return

        set_current_auth(auth)

        # Wrap 'send' so we can capture the Mcp-Session-Id from the response
        # headers and register it in our session-auth cache.
        _captured_auth = auth

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                for k, v in message.get("headers", []):
                    if k.lower() == b"mcp-session-id":
                        sid = v.decode().strip()
                        if sid:
                            self._session_auth[sid] = _captured_auth
                        break
            await send(message)

        await self.app(scope, receive, send_wrapper)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _auth_from_key(self, headers: dict):
        """Return AuthContext if a valid API key is present, else None."""
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
