# ABOUTME: ASGI tests for HTTPS MCP health + Bearer gate at /mcp.
# ABOUTME: Confirms /mcp and /mcp/ both reach Streamable HTTP, not the site login.
import psycopg2
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from httpx import ASGITransport, AsyncClient

from ulmg import models
from ulmg.mcp_app import services
from ulmg.mcp_app.db import db_sync
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


@override_settings(ALLOWED_HOSTS=["*"])
class MCPStaleConnectionTestCase(TransactionTestCase):
    """
    MCP HTTP runs on Starlette, not Django's ASGI handler, so a worker
    thread can keep a Postgres connection the server has already closed.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="stale_owner", email="stale@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Stale Owner", email="stale@example.com"
        )
        self.raw, self.token = models.OwnerAPIToken.create_token(
            self.owner, label="agent"
        )
        self.app = create_mcp_http_app()

    def tearDown(self):
        # A test that closes the driver connection must hand the runner a
        # usable one, or the flush between tests dies the same way production did.
        connection.settings_dict["CONN_MAX_AGE"] = 0
        connection.settings_dict["CONN_HEALTH_CHECKS"] = False
        connection.close()

    async def _health(self):
        transport = ASGITransport(app=self.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(
                "/health",
                headers={"Authorization": f"Bearer {self.raw}"},
            )

    async def test_bearer_health_after_driver_connection_closed(self):
        def _close_driver_connection():
            connection.ensure_connection()
            connection.connection.close()
            self.assertNotEqual(connection.connection.closed, 0)
            self.assertIsNotNone(connection.connection)

        await sync_to_async(_close_driver_connection)()
        with self.assertLogs("ulmg.mcp_app.db", level="WARNING") as logs:
            resp = await self._health()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["service"], "ulmg-mcp")
        self.assertTrue(
            any("already closed" in line for line in logs.output)
        )
        await sync_to_async(self.token.refresh_from_db)()
        self.assertIsNotNone(self.token.last_used_at)

    async def test_bearer_health_after_server_drops_backend(self):
        def _terminate_backend():
            # Persistent age, health checks off: nothing but a failed query
            # tells Django this backend is gone.
            connection.close()
            connection.settings_dict["CONN_MAX_AGE"] = None
            connection.settings_dict["CONN_HEALTH_CHECKS"] = False
            try:
                connection.ensure_connection()
                self.assertIsNone(connection.close_at)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pid = cursor.fetchone()[0]
                admin = psycopg2.connect(**connection.get_connection_params())
                admin.autocommit = True
                try:
                    with admin.cursor() as cursor:
                        cursor.execute("SELECT pg_terminate_backend(%s)", [pid])
                finally:
                    admin.close()
            finally:
                connection.settings_dict["CONN_MAX_AGE"] = 0
                connection.settings_dict["CONN_HEALTH_CHECKS"] = False

        await sync_to_async(_terminate_backend)()
        with self.assertLogs("ulmg.mcp_app.db", level="WARNING") as logs:
            resp = await self._health()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["auth"], "bearer")
        self.assertTrue(
            any(
                "reconnecting" in line or "already closed" in line
                for line in logs.output
            )
        )
        await sync_to_async(self.token.refresh_from_db)()
        self.assertIsNotNone(self.token.last_used_at)

    async def test_db_sync_query_after_driver_connection_closed(self):
        def _close_driver_connection():
            connection.ensure_connection()
            connection.connection.close()

        await sync_to_async(_close_driver_connection)()
        with self.assertLogs("ulmg.mcp_app.db", level="WARNING") as logs:
            data = await db_sync(services.list_teams)
        self.assertIn("teams", data)
        self.assertTrue(any("already closed" in line for line in logs.output))
