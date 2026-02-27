"""RFC 9728 / RFC 8414 discovery endpoints for the SSE MCP server.

Clients that receive a 401 from the MCP server will follow the
WWW-Authenticate header to /.well-known/oauth-protected-resource (RFC 9728),
then to /.well-known/oauth-authorization-server (RFC 8414) to learn how to
obtain credentials.

Since this server uses API keys (not OAuth tokens), the token endpoint returns
a clear error directing users to the Activity Manager admin panel.
"""

import json

from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route


def _json(data: dict, status: int = 200) -> Response:
    return Response(
        content=json.dumps(data),
        status_code=status,
        media_type="application/json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


def make_discovery_routes(base_url: str) -> list:
    """Return Starlette Route objects for all discovery endpoints.

    Args:
        base_url: Externally-accessible base URL of this MCP server,
                  e.g. 'http://127.0.0.1:8001'.
    """

    async def protected_resource_metadata(request: Request) -> Response:
        """RFC 9728 — declares this resource requires Bearer auth.

        We intentionally omit 'authorization_servers' because this server
        uses API keys rather than OAuth tokens.  Advertising a fake OAuth
        server causes clients like mcporter to attempt an OAuth flow that
        dead-ends with an error instead of simply sending the pre-shared key.
        """
        return _json(
            {
                "resource": base_url,
                "resource_name": "Activity Manager MCP",
                "scopes_supported": ["read", "readwrite"],
                "bearer_methods_supported": ["header"],
                "service_documentation": f"{base_url}/oauth/authorize",
            }
        )

    async def authorization_server_metadata(request: Request) -> Response:
        """RFC 8414 — describes how to obtain credentials for this server.

        Because this server issues API keys rather than OAuth tokens, the
        token_endpoint responds with an informative error.  Clients that
        support interactive auth will follow the authorization_endpoint to
        the admin panel where users can create keys.
        """
        return _json(
            {
                "issuer": base_url,
                "authorization_endpoint": f"{base_url}/oauth/authorize",
                "token_endpoint": f"{base_url}/oauth/token",
                "scopes_supported": ["read", "readwrite"],
                "response_types_supported": ["code"],
                "grant_types_supported": ["urn:ietf:params:oauth:grant-type:api-key"],
                "service_documentation": f"{base_url}/oauth/authorize",
            }
        )

    async def token_endpoint(request: Request) -> Response:
        """Informs OAuth clients that this server uses API keys, not OAuth tokens."""
        return _json(
            {
                "error": "invalid_request",
                "error_description": (
                    "This server authenticates via API keys, not OAuth tokens. "
                    "Create a key at the Activity Manager admin panel "
                    "(/admin/profile → API Keys) and send it as: "
                    "Authorization: Bearer am_<your_key>"
                ),
            },
            status=400,
        )

    async def authorize_endpoint(request: Request) -> Response:
        """Informs clients where to create API keys."""
        return _json(
            {
                "error": "invalid_request",
                "error_description": (
                    "This server uses API keys. "
                    "Create one at the Activity Manager admin panel (/admin/profile)."
                ),
            },
            status=400,
        )

    return [
        Route("/.well-known/oauth-protected-resource", protected_resource_metadata),
        Route("/.well-known/oauth-authorization-server", authorization_server_metadata),
        Route("/oauth/token", token_endpoint, methods=["GET", "POST"]),
        Route("/oauth/authorize", authorize_endpoint, methods=["GET", "POST"]),
    ]
