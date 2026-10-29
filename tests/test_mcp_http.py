# ABOUTME: ASGI tests for HTTPS MCP health + Bearer gate at /mcp.
# ABOUTME: Confirms /mcp and /mcp/ both reach Streamable HTTP, not the site login.
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from httpx import ASGITransport, AsyncClient

from ulmg import models
from ulmg.mcp_app.http_app import create_mcp_http_app, create_site_asgi_application

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "claude", "version": "1"},
    },
}
_MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


async def _site_login_redirect(scope, receive, send):
    """Stand-in for Django when a request misses the MCP mount."""
    await send(
        {
            "type": "http.response.start",
            "status": 302,
            "headers": [(b"location", b"/accounts/login/")],
        }
    )
    await send({"type": "http.response.body", "body": b""})


@override_settings(ALLOWED_HOSTS=["*"])
class MCPHttpAuthTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="http_owner", email="http@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="HTTP Owner", email="http@example.com"
        )
        self.raw, _ = models.OwnerAPIToken.create_token(self.owner, label="http")
        self.app = create_mcp_http_app()

    async def test_health_requires_token(self):
        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            self.assertEqual(resp.status_code, 401)

    async def test_health_with_bearer(self):
        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/health",
                headers={"Authorization": f"Bearer {self.raw}"},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["service"], "ulmg-mcp")
            self.assertEqual(resp.json()["auth"], "bearer")
            self.assertEqual(resp.json()["transport"], "streamable-http")


@override_settings(ALLOWED_HOSTS=["*"])
class MCPSitePathTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="site_owner", email="site@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Site Owner", email="site@example.com"
        )
        self.raw, _ = models.OwnerAPIToken.create_token(self.owner, label="claude")
        self.app = create_site_asgi_application(_site_login_redirect)

    async def test_slashless_mcp_is_the_mcp_server(self):
        transport = ASGITransport(app=self.app)
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                bare = await client.post("/mcp", headers=_MCP_HEADERS, json=_INITIALIZE)
                self.assertEqual(bare.status_code, 401)
                self.assertIn("application/json", bare.headers["content-type"])
                self.assertEqual(bare.json()["error"], "Unauthorized")
                self.assertNotIn("location", bare.headers)

                slashed = await client.post("/mcp/", headers=_MCP_HEADERS, json=_INITIALIZE)
                self.assertEqual(slashed.status_code, 401)
                self.assertEqual(slashed.json()["error"], "Unauthorized")

                other = await client.get("/teams/")
                self.assertEqual(other.status_code, 302)
                self.assertEqual(other.headers["location"], "/accounts/login/")

    async def test_slashless_mcp_initialize_with_bearer(self):
        transport = ASGITransport(app=self.app)
        headers = {**_MCP_HEADERS, "Authorization": f"Bearer {self.raw}"}
        async with self.app.router.lifespan_context(self.app):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/mcp", headers=headers, json=_INITIALIZE)
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertEqual(body["jsonrpc"], "2.0")
                self.assertIn("serverInfo", body["result"])
