# ABOUTME: Tests that local MCP roster tools resolve the authenticated owner.
# ABOUTME: Covers get_team_roster, get_roster_compliance, and get_season_context.
import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from httpx import ASGITransport, AsyncClient

from ulmg import models
from ulmg.mcp_app.context import reset_current_owner, set_current_owner
from ulmg.mcp_app.http_app import create_site_asgi_application
from ulmg.mcp_app.tools import build_mcp


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


def _tool_text(result):
    content = result[0] if isinstance(result, tuple) else result
    block = content[0] if isinstance(content, list) else content
    return json.loads(block.text)


@override_settings(
    CURRENT_SEASON=2026,
    CURRENT_SEASON_TYPE="offseason",
    MLB_ROSTER_SIZE=30,
    ALLOWED_HOSTS=["*"],
)
class LocalRosterToolTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="roster_owner", email="roster@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Roster Owner", email="roster@example.com"
        )
        self.team = models.Team.objects.create(
            city="Boston",
            abbreviation="BOS",
            nickname="Beans",
            owner_obj=self.owner,
        )
        self.other = models.Team.objects.create(
            city="New York", abbreviation="NYK", nickname="Knights"
        )
        models.Player.objects.create(
            name="Ace Pitcher",
            position="P",
            level="V",
            team=self.team,
            is_owned=True,
            is_ulmg_mlb_roster=True,
        )
        models.Player.objects.create(
            name="Other Ace",
            position="P",
            level="V",
            team=self.other,
            is_owned=True,
            is_ulmg_mlb_roster=True,
        )
        self.raw, _ = models.OwnerAPIToken.create_token(self.owner, label="agent")
        self.mcp = build_mcp(mode="local")
        self.app = create_site_asgi_application(_site_login_redirect)

    async def test_roster_tools_resolve_the_authenticated_owner(self):
        owner_token = set_current_owner(self.owner)
        try:
            own = _tool_text(await self.mcp.call_tool("get_team_roster", {}))
            other = _tool_text(
                await self.mcp.call_tool("get_team_roster", {"abbreviation": "NYK"})
            )
            context = _tool_text(await self.mcp.call_tool("get_season_context", {}))
            compliance = _tool_text(
                await self.mcp.call_tool(
                    "get_roster_compliance", {"abbreviation": "BOS"}
                )
            )
        finally:
            reset_current_owner(owner_token)

        self.assertEqual(own["team"]["abbreviation"], "BOS")
        self.assertEqual({p["name"] for p in own["mlb"]}, {"Ace Pitcher"})
        self.assertEqual(other["team"]["abbreviation"], "NYK")
        self.assertEqual({p["name"] for p in other["mlb"]}, {"Other Ace"})
        self.assertEqual(context["my_team"]["abbreviation"], "BOS")
        self.assertEqual(compliance["team"]["abbreviation"], "BOS")
        self.assertEqual(compliance["counts"]["mlb_30man"], 1)

    async def test_https_get_team_roster_for_another_team(self):
        transport = ASGITransport(app=self.app)
        headers = {**_MCP_HEADERS, "Authorization": f"Bearer {self.raw}"}
        call = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "get_team_roster",
                "arguments": {"abbreviation": "NYK"},
            },
        }
        with self.assertLogs("mcp.server", "INFO"), self.assertLogs("httpx", "INFO"):
            async with self.app.router.lifespan_context(self.app):
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.post("/mcp", headers=headers, json=call)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertNotIn("error", body)
        payload = json.loads(body["result"]["content"][0]["text"])
        self.assertNotIn("error", payload)
        self.assertEqual(payload["team"]["abbreviation"], "NYK")
        self.assertEqual({p["name"] for p in payload["mlb"]}, {"Other Ace"})
