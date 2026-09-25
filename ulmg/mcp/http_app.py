# ABOUTME: ASGI app exposing ULMG MCP over HTTPS Streamable HTTP.
# ABOUTME: Authenticates with OwnerAPIToken Bearer headers (no OAuth discovery).
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from asgiref.sync import sync_to_async
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from ulmg import models
from ulmg.mcp.context import reset_current_owner, set_current_owner
from ulmg.mcp.tools import build_mcp

logger = logging.getLogger(__name__)


class OwnerBearerMiddleware:
    """
    Require Authorization: Bearer ulmg_… for MCP HTTP traffic.
    Intentionally does NOT advertise OAuth resource_metadata (avoids client
    OAuth discovery loops). Plain Bearer realm only.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1").lower(): v.decode("latin-1")
            for k, v in scope.get("headers", [])
        }
        auth = headers.get("authorization", "")
        raw = None
        if auth.lower().startswith("bearer "):
            raw = auth[7:].strip()
        if not raw:
            raw = headers.get("x-ulmg-token", "").strip() or None

        token = await sync_to_async(models.OwnerAPIToken.authenticate)(raw)
        if token is None:
            body = b'{"error":"Unauthorized","detail":"Valid ULMG API token required"}'
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"www-authenticate", b'Bearer realm="ulmg"'),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        ctx_token = set_current_owner(token.owner)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_current_owner(ctx_token)


async def mcp_health(request: Request) -> Response:
    return JSONResponse(
        {
            "service": "ulmg-mcp",
            "phase": 1,
            "auth": "bearer",
            "transport": "streamable-http",
        }
    )


def create_mcp_http_app() -> Starlette:
    """
    Streamable HTTP MCP at `/` (mount this under `/mcp` on the site ASGI app).

    Clients connect to https://YOUR-HOST/mcp with:
      Authorization: Bearer ulmg_…
    """
    mcp = build_mcp(mode="local")
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    )
    mcp.settings.streamable_http_path = "/"
    mcp.settings.stateless_http = True
    mcp.settings.json_response = True

    inner = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app: Starlette):
        async with inner.router.lifespan_context(inner):
            yield

    return Starlette(
        routes=[
            Route("/health", endpoint=mcp_health, methods=["GET"]),
            Mount("/", app=inner),
        ],
        middleware=[Middleware(OwnerBearerMiddleware)],
        lifespan=lifespan,
    )


def create_site_asgi_application(django_asgi_app: ASGIApp) -> Starlette:
    """Compose Django + MCP under one HTTPS host."""
    mcp_app = create_mcp_http_app()

    @asynccontextmanager
    async def lifespan(app: Starlette):
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    return Starlette(
        routes=[
            Mount("/mcp", app=mcp_app),
            Mount("/", app=django_asgi_app),
        ],
        lifespan=lifespan,
    )
