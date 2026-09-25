# ABOUTME: ASGI tests for HTTPS MCP health + Bearer gate at /mcp.
# ABOUTME: Confirms remote clients get 401 without a token and 200 on /mcp/health.
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from httpx import ASGITransport, AsyncClient

from ulmg import models
from ulmg.mcp.http_app import create_mcp_http_app


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
