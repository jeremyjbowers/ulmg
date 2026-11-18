# ABOUTME: Tests for MCP draft-prep wishlist writes and the draft board.
# ABOUTME: Covers follow, unfollow, tiers, notes, and the read-write key gate.
import json

from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from httpx import ASGITransport, AsyncClient

from ulmg import models
from ulmg.mcp_app import wishlist as wishlist_ops
from ulmg.mcp_app.context import (
    reset_current_owner,
    reset_current_token,
    set_current_owner,
    set_current_token,
)
from ulmg.mcp_app.http_app import create_site_asgi_application
from ulmg.mcp_app.tools import build_mcp


def _player(name, level, position="OF", team=None, carded_seasons=None):
    return models.Player.objects.create(
        name=name,
        position=position,
        level=level,
        team=team,
        is_owned=team is not None,
        carded_seasons=carded_seasons or [],
    )


def _post(client, path, payload, token):
    return client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="offseason")
class WishlistWriteServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="board_owner", email="board@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Board Owner", email="board@example.com"
        )
        self.team = models.Team.objects.create(
            city="Boston", abbreviation="BOS", nickname="Beans", owner_obj=self.owner
        )
        self.other = models.Team.objects.create(
            city="New York", abbreviation="NYK", nickname="Knights"
        )
        self.veteran = _player("Una Vet", "V")
        self.prospect = _player("Bea Prospect", "B")
        self.owned = _player("Owned Ace", "V", team=self.other)

    def _ranks(self, tier):
        wishlist = models.Wishlist.objects.get(owner=self.owner)
        return list(
            models.WishlistPlayer.objects.filter(wishlist=wishlist, tier=tier)
            .order_by("rank", "id")
            .values_list("player__name", "rank")
        )

    def test_follow_creates_a_watched_player_and_a_wishlist(self):
        payload = wishlist_ops.follow_player(self.owner, self.veteran.id)
        self.assertTrue(payload["created"])
        self.assertIsNone(payload["player"]["tier"])
        self.assertIsNone(payload["player"]["rank"])
        self.assertEqual(models.Wishlist.objects.filter(owner=self.owner).count(), 1)

    def test_follow_again_keeps_the_existing_tier(self):
        wishlist_ops.set_wishlist_tier(self.owner, self.veteran.id, tier=2, rank=1)
        payload = wishlist_ops.follow_player(self.owner, self.veteran.id)
        self.assertFalse(payload["created"])
        self.assertEqual(payload["player"]["tier"], 2)
        self.assertEqual(payload["player"]["rank"], 1)

    def test_set_tier_inserts_at_rank_and_renumbers(self):
        for name in ("Amy", "Bea", "Cam"):
            player = _player(name, "V")
            wishlist_ops.follow_player(self.owner, player.id)
            wishlist_ops.set_wishlist_tier(self.owner, player.id, tier=1)
        cam = models.Player.objects.get(name="Cam")
        wishlist_ops.set_wishlist_tier(self.owner, cam.id, tier=1, rank=1)
        self.assertEqual(
            self._ranks(1),
            [("Cam", 1), ("Amy", 2), ("Bea", 3)],
        )

    def test_clearing_a_tier_renumbers_who_remains(self):
        first = _player("First", "V")
        second = _player("Second", "V")
        wishlist_ops.set_wishlist_tier(self.owner, first.id, tier=1, rank=1)
        wishlist_ops.set_wishlist_tier(self.owner, second.id, tier=1, rank=2)
        payload = wishlist_ops.set_wishlist_tier(self.owner, first.id, tier=0)
        self.assertIsNone(payload["player"]["tier"])
        self.assertEqual(self._ranks(1), [("Second", 1)])

    def test_unfollow_removes_the_player_and_renumbers(self):
        first = _player("First", "A")
        second = _player("Second", "A")
        wishlist_ops.set_wishlist_tier(self.owner, first.id, tier=3, rank=1)
        wishlist_ops.set_wishlist_tier(self.owner, second.id, tier=3, rank=2)
        payload = wishlist_ops.unfollow_player(self.owner, first.id)
        self.assertTrue(payload["removed"])
        self.assertEqual(self._ranks(3), [("Second", 1)])
        again = wishlist_ops.unfollow_player(self.owner, first.id)
        self.assertFalse(again["removed"])

    def test_a_full_tier_rejects_a_new_player(self):
        for index in range(wishlist_ops.TIER_LIMIT):
            player = _player(f"Tiered {index}", "V")
            wishlist_ops.set_wishlist_tier(self.owner, player.id, tier=1)
        extra = _player("One Too Many", "V")
        wishlist_ops.follow_player(self.owner, extra.id)
        with self.assertRaises(wishlist_ops.WishlistError) as caught:
            wishlist_ops.set_wishlist_tier(self.owner, extra.id, tier=1)
        self.assertEqual(caught.exception.status, 409)
        row = models.WishlistPlayer.objects.get(player=extra)
        self.assertIsNone(row.tier)
        self.assertEqual(
            models.WishlistPlayer.objects.filter(
                wishlist__owner=self.owner, tier=1
            ).count(),
            wishlist_ops.TIER_LIMIT,
        )
        fresh = _player("Brand New", "V")
        with self.assertRaises(wishlist_ops.WishlistError):
            wishlist_ops.set_wishlist_tier(self.owner, fresh.id, tier=1)
        self.assertFalse(models.WishlistPlayer.objects.filter(player=fresh).exists())

    def test_reordering_inside_a_full_tier_is_allowed(self):
        first = None
        for index in range(wishlist_ops.TIER_LIMIT):
            player = _player(f"Full {index}", "V")
            wishlist_ops.set_wishlist_tier(self.owner, player.id, tier=2)
            if index == 0:
                first = player
        payload = wishlist_ops.set_wishlist_tier(
            self.owner, first.id, tier=2, rank=wishlist_ops.TIER_LIMIT
        )
        self.assertEqual(payload["player"]["rank"], wishlist_ops.TIER_LIMIT)
        self.assertEqual(payload["tier_count"], wishlist_ops.TIER_LIMIT)

    def test_note_follows_when_needed_and_keeps_a_tier(self):
        created = wishlist_ops.set_wishlist_note(
            self.owner, self.veteran.id, note="target in round 2"
        )
        self.assertTrue(created["created"])
        self.assertEqual(created["player"]["note"], "target in round 2")
        self.assertIsNone(created["player"]["tier"])
        wishlist_ops.set_wishlist_tier(self.owner, self.veteran.id, tier=4)
        updated = wishlist_ops.set_wishlist_note(self.owner, self.veteran.id, note="")
        self.assertFalse(updated["created"])
        self.assertEqual(updated["player"]["tier"], 4)
        self.assertEqual(updated["player"]["note"], "")

    def test_unknown_player_and_bad_tier_are_rejected(self):
        with self.assertRaises(wishlist_ops.WishlistError) as missing:
            wishlist_ops.follow_player(self.owner, 999999)
        self.assertEqual(missing.exception.status, 404)
        with self.assertRaises(wishlist_ops.WishlistError) as bad_tier:
            wishlist_ops.set_wishlist_tier(self.owner, self.veteran.id, tier=6)
        self.assertEqual(bad_tier.exception.status, 400)

    def test_draft_board_matches_offseason_open_eligibility_and_picks(self):
        wishlist_ops.set_wishlist_tier(self.owner, self.veteran.id, tier=1, rank=1)
        wishlist_ops.follow_player(self.owner, self.prospect.id)
        wishlist_ops.set_wishlist_tier(self.owner, self.owned.id, tier=1, rank=1)
        # The site's follow button stores tier 6, which the board shows as watched.
        site_style = _player("Site Follow", "A")
        wishlist = models.Wishlist.objects.get(owner=self.owner)
        models.WishlistPlayer.objects.create(
            wishlist=wishlist, player=site_style, tier=6, rank=999
        )
        models.DraftPick.objects.create(
            year="2026",
            season="offseason",
            draft_type="open",
            draft_round=1,
            pick_number=3,
            overall_pick_number=3,
            team=self.team,
        )
        models.DraftPick.objects.create(
            year="2026",
            season="offseason",
            draft_type="open",
            draft_round=1,
            pick_number=4,
            overall_pick_number=4,
            team=self.other,
        )
        board = wishlist_ops.get_draft_board(self.owner, draft_type="open")
        self.assertEqual(board["year"], 2026)
        self.assertEqual(board["season"], "offseason")
        self.assertEqual(len(board["my_picks"]), 1)
        self.assertEqual(board["my_picks"][0]["overall_pick_number"], 3)
        self.assertEqual([row["team"] for row in board["order"]], ["BOS", "NYK"])
        self.assertTrue(board["order"][0]["mine"])
        self.assertFalse(board["order"][1]["mine"])
        tier_names = {player["name"] for player in board["tiers"][0]["players"]}
        self.assertEqual(tier_names, {"Una Vet"})
        watched_names = {player["name"] for player in board["watched"]}
        self.assertEqual(watched_names, {"Site Follow"})

    def test_aa_board_is_unowned_b_players(self):
        wishlist_ops.follow_player(self.owner, self.prospect.id)
        wishlist_ops.follow_player(self.owner, self.veteran.id)
        board = wishlist_ops.get_draft_board(self.owner, draft_type="aa")
        names = {player["name"] for player in board["watched"]}
        self.assertEqual(names, {"Bea Prospect"})
        self.assertEqual(board["tiers"][0]["players"], [])


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class MidseasonDraftBoardTestCase(TestCase):
    def test_midseason_open_board_requires_a_prior_card(self):
        user = User.objects.create_user(
            username="mid_owner", email="mid@example.com", password="x"
        )
        owner = models.Owner.objects.create(
            user=user, name="Mid Owner", email="mid@example.com"
        )
        carded = _player("Carded Vet", "V", carded_seasons=[2025])
        uncarded = _player("Uncarded Vet", "V")
        wishlist_ops.follow_player(owner, carded.id)
        wishlist_ops.follow_player(owner, uncarded.id)
        board = wishlist_ops.get_draft_board(owner, draft_type="open")
        names = {player["name"] for player in board["watched"]}
        self.assertEqual(names, {"Carded Vet"})
        self.assertEqual(board["season"], "midseason")


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="offseason")
class WishlistWriteAPITestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="api_owner", email="api@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="API Owner", email="api@example.com"
        )
        self.team = models.Team.objects.create(
            city="Boston", abbreviation="BOS", nickname="Beans", owner_obj=self.owner
        )
        self.player = _player("Wishlist Target", "V")
        self.read_token, _ = models.OwnerAPIToken.create_token(
            self.owner, label="read", scope=models.OwnerAPIToken.SCOPE_READ
        )
        self.write_token, _ = models.OwnerAPIToken.create_token(
            self.owner, label="write", scope=models.OwnerAPIToken.SCOPE_READ_WRITE
        )

    def test_read_key_can_load_the_board_and_cannot_write(self):
        board = self.client.get(
            "/api/mcp/v1/draft-board/",
            HTTP_AUTHORIZATION=f"Bearer {self.read_token}",
        )
        self.assertEqual(board.status_code, 200)
        self.assertEqual(board.json()["draft_type"], "open")
        for path in (
            "/api/mcp/v1/wishlist/follow/",
            "/api/mcp/v1/wishlist/unfollow/",
            "/api/mcp/v1/wishlist/tier/",
            "/api/mcp/v1/wishlist/note/",
        ):
            with self.assertLogs("django.request", "WARNING") as logs:
                response = _post(
                    self.client,
                    path,
                    {"player_id": self.player.id, "tier": 1, "note": "x"},
                    self.read_token,
                )
            self.assertEqual(response.status_code, 403, path)
            self.assertIn(f"Forbidden: {path}", logs.output[0])
        self.assertFalse(
            models.WishlistPlayer.objects.filter(player=self.player).exists()
        )

    def test_missing_token_is_unauthorized(self):
        with self.assertLogs("django.request", "WARNING") as logs:
            response = self.client.post(
                "/api/mcp/v1/wishlist/follow/",
                data=json.dumps({"player_id": self.player.id}),
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Unauthorized: /api/mcp/v1/wishlist/follow/", logs.output[0])

    def test_write_key_follows_sets_a_tier_notes_and_unfollows(self):
        followed = _post(
            self.client,
            "/api/mcp/v1/wishlist/follow/",
            {"player_id": self.player.id},
            self.write_token,
        )
        self.assertEqual(followed.status_code, 200)
        self.assertTrue(followed.json()["created"])
        self.assertIsNone(followed.json()["player"]["tier"])

        listed = self.client.get(
            "/api/mcp/v1/wishlist/",
            HTTP_AUTHORIZATION=f"Bearer {self.write_token}",
        )
        self.assertEqual(listed.json()["players"][0]["name"], "Wishlist Target")

        tiered = _post(
            self.client,
            "/api/mcp/v1/wishlist/tier/",
            {"player_id": self.player.id, "tier": 2, "rank": 1},
            self.write_token,
        )
        self.assertEqual(tiered.status_code, 200)
        self.assertEqual(tiered.json()["player"]["tier"], 2)
        self.assertEqual(tiered.json()["tier_count"], 1)

        noted = _post(
            self.client,
            "/api/mcp/v1/wishlist/note/",
            {"player_id": self.player.id, "note": "like the bat"},
            self.write_token,
        )
        self.assertEqual(noted.status_code, 200)
        self.assertEqual(noted.json()["player"]["note"], "like the bat")
        self.assertEqual(noted.json()["player"]["tier"], 2)

        removed = _post(
            self.client,
            "/api/mcp/v1/wishlist/unfollow/",
            {"player_id": self.player.id},
            self.write_token,
        )
        self.assertEqual(removed.status_code, 200)
        self.assertTrue(removed.json()["removed"])
        self.assertEqual(
            self.client.get(
                "/api/mcp/v1/wishlist/",
                HTTP_AUTHORIZATION=f"Bearer {self.write_token}",
            ).json()["count"],
            0,
        )

    def test_bad_payloads_are_400(self):
        with self.assertLogs("django.request", "WARNING") as missing_logs:
            missing = _post(
                self.client, "/api/mcp/v1/wishlist/follow/", {}, self.write_token
            )
        self.assertEqual(missing.status_code, 400)
        self.assertIn("Bad Request: /api/mcp/v1/wishlist/follow/", missing_logs.output[0])
        with self.assertLogs("django.request", "WARNING") as nonsense_logs:
            nonsense = self.client.post(
                "/api/mcp/v1/wishlist/follow/",
                data="[",
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.write_token}",
            )
        self.assertEqual(nonsense.status_code, 400)
        self.assertIn(
            "Bad Request: /api/mcp/v1/wishlist/follow/", nonsense_logs.output[0]
        )
        with self.assertLogs("django.request", "WARNING") as unknown_logs:
            unknown = _post(
                self.client,
                "/api/mcp/v1/wishlist/follow/",
                {"player_id": 999999},
                self.write_token,
            )
        self.assertEqual(unknown.status_code, 404)
        self.assertIn("Not Found: /api/mcp/v1/wishlist/follow/", unknown_logs.output[0])
        with self.assertLogs("django.request", "WARNING") as board_logs:
            bad_board = self.client.get(
                "/api/mcp/v1/draft-board/",
                {"draft_type": "balance"},
                HTTP_AUTHORIZATION=f"Bearer {self.write_token}",
            )
        self.assertEqual(bad_board.status_code, 400)
        self.assertIn("Bad Request: /api/mcp/v1/draft-board/", board_logs.output[0])


async def _site_login_redirect(scope, receive, send):
    await send(
        {
            "type": "http.response.start",
            "status": 302,
            "headers": [(b"location", b"/accounts/login/")],
        }
    )
    await send({"type": "http.response.body", "body": b""})


_MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def _tool_text(result):
    # FastMCP returns (content blocks, structured) when a tool declares a schema.
    content = result[0] if isinstance(result, tuple) else result
    block = content[0] if isinstance(content, list) else content
    return json.loads(block.text)


@override_settings(
    CURRENT_SEASON=2026,
    CURRENT_SEASON_TYPE="offseason",
    ALLOWED_HOSTS=["*"],
)
class WishlistMCPEndToEndTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="e2e_owner", email="e2e@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="E2E Owner", email="e2e@example.com"
        )
        self.player = _player("Tool Target", "A")
        self.read_raw, self.read_token = models.OwnerAPIToken.create_token(
            self.owner, label="read", scope=models.OwnerAPIToken.SCOPE_READ
        )
        self.write_raw, self.write_token = models.OwnerAPIToken.create_token(
            self.owner, label="write", scope=models.OwnerAPIToken.SCOPE_READ_WRITE
        )
        self.mcp = build_mcp(mode="local")
        self.app = create_site_asgi_application(_site_login_redirect)

    async def test_registered_tools_include_the_draft_prep_writes(self):
        names = {tool.name for tool in await self.mcp.list_tools()}
        self.assertTrue(
            {
                "list_draft_picks",
                "get_my_wishlist",
                "get_draft_board",
                "follow_player",
                "unfollow_player",
                "set_wishlist_tier",
                "set_wishlist_note",
            }
            <= names
        )

    async def test_call_tool_follows_and_a_read_key_does_not(self):
        owner_token = set_current_owner(self.owner)
        api_token = set_current_token(self.read_token)
        try:
            refused = _tool_text(
                await self.mcp.call_tool(
                    "follow_player", {"player_id": self.player.id}
                )
            )
        finally:
            reset_current_token(api_token)
            reset_current_owner(owner_token)
        self.assertEqual(refused["status"], 403)
        self.assertFalse(
            await sync_to_async(
                models.WishlistPlayer.objects.filter(player=self.player).exists
            )()
        )

        owner_token = set_current_owner(self.owner)
        api_token = set_current_token(self.write_token)
        try:
            followed = _tool_text(
                await self.mcp.call_tool(
                    "follow_player", {"player_id": self.player.id}
                )
            )
            board = _tool_text(
                await self.mcp.call_tool(
                    "get_draft_board", {"draft_type": "open", "list_type": "offseason"}
                )
            )
        finally:
            reset_current_token(api_token)
            reset_current_owner(owner_token)
        self.assertTrue(followed["created"])
        watched = {player["name"] for player in board["watched"]}
        self.assertIn("Tool Target", watched)

    async def test_https_mcp_tool_call_sets_a_tier(self):
        transport = ASGITransport(app=self.app)
        headers = {**_MCP_HEADERS, "Authorization": f"Bearer {self.write_raw}"}
        call = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "set_wishlist_tier",
                "arguments": {"player_id": self.player.id, "tier": 1, "rank": 1},
            },
        }
        with self.assertLogs("mcp.server", "INFO"), self.assertLogs("httpx", "INFO"):
            async with self.app.router.lifespan_context(self.app):
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    response = await client.post("/mcp", headers=headers, json=call)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertNotIn("error", body)
        text = body["result"]["content"][0]["text"]
        payload = json.loads(text)
        self.assertEqual(payload["player"]["tier"], 1)
        self.assertTrue(
            await sync_to_async(
                models.WishlistPlayer.objects.filter(
                    player=self.player, tier=1, wishlist__owner=self.owner
                ).exists
            )()
        )
