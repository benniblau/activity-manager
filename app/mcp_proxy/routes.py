"""Reverse-proxy routes that forward MCP traffic to the standalone MCP server.

Exposing /mcp through the main Flask app means clients only need one URL
(e.g. https://activity.example.com/mcp) and the MCP port (8001) never
needs to be publicly accessible.

The RFC 9728 / RFC 8414 discovery endpoints are also proxied so that
auth discovery works at the same domain as the Flask app.

Configure the upstream address via the MCP_UPSTREAM_URL environment variable
(default: http://127.0.0.1:8001).  It must match MCP_HOST/MCP_PORT in the
MCP server's systemd unit.
"""

import os

import requests
from flask import Blueprint, Response, request, stream_with_context

mcp_proxy_bp = Blueprint("mcp_proxy", __name__)

# Hop-by-hop headers that must not be forwarded (RFC 2616 §13.5.1).
_HOP_BY_HOP = frozenset(
    [
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    ]
)

# Routes handled by this proxy (relative to the upstream MCP server root).
# The Flask routes below map these 1-to-1.
_PROXIED_PATHS = [
    "/mcp",
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-authorization-server",
    "/oauth/token",
    "/oauth/authorize",
]


def _upstream() -> str:
    return os.environ.get("MCP_UPSTREAM_URL", "http://127.0.0.1:8001").rstrip("/")


def _proxy(path: str) -> Response:
    """Forward the current Flask request to the MCP server and stream back the response."""
    url = f"{_upstream()}{path}"

    # Forward all headers except hop-by-hop ones and Host (rewritten by requests).
    forward_headers = {
        k: v
        for k, v in request.headers
        if k.lower() not in _HOP_BY_HOP and k.lower() != "host"
    }

    upstream_resp = requests.request(
        method=request.method,
        url=url,
        headers=forward_headers,
        data=request.get_data(),
        stream=True,
        timeout=None,  # SSE / long-poll connections must not time out.
    )

    # Strip headers that Flask/WSGI will set itself or that are stream-incompatible.
    _drop = _HOP_BY_HOP | {"content-encoding", "content-length"}
    response_headers = [
        (k, v)
        for k, v in upstream_resp.headers.items()
        if k.lower() not in _drop
    ]

    return Response(
        stream_with_context(upstream_resp.iter_content(chunk_size=None)),
        status=upstream_resp.status_code,
        headers=response_headers,
    )


# ── MCP endpoint (Streamable HTTP transport) ────────────────────────────────

@mcp_proxy_bp.route("/mcp", methods=["GET", "POST", "DELETE", "PUT", "OPTIONS"])
def mcp():
    return _proxy("/mcp")


# ── Auth discovery (RFC 9728 / RFC 8414) ────────────────────────────────────
# These must be at the Flask app's domain so MCP clients following the
# WWW-Authenticate → resource_metadata chain arrive at working endpoints.

@mcp_proxy_bp.route("/.well-known/oauth-protected-resource")
def protected_resource_metadata():
    return _proxy("/.well-known/oauth-protected-resource")


@mcp_proxy_bp.route("/.well-known/oauth-authorization-server")
def authorization_server_metadata():
    return _proxy("/.well-known/oauth-authorization-server")


@mcp_proxy_bp.route("/oauth/token", methods=["GET", "POST"])
def oauth_token():
    return _proxy("/oauth/token")


@mcp_proxy_bp.route("/oauth/authorize", methods=["GET", "POST"])
def oauth_authorize():
    return _proxy("/oauth/authorize")
