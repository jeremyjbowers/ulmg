# ABOUTME: Tests for Phase 1 read-only MCP JSON API endpoints.
# ABOUTME: Covers roster, search, drafts, trades, wishlist, and draft pools.
import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import models


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="offseason", MLB_ROSTER_SIZE=30)
class MCPReadAPITestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="mcp_owner", email="mcp@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="MCP Owner", email="mcp@example.com"
        )
        self.team = models.Team.objects.create(
            city="Boston", abbreviation="BOS", nickname="Beans", owner_obj=self.owner
        )
        self.other = models.Team.objects.create(
            city="New York", abbreviation="NYK", nickname="Knights"
        )
        self.mlb_player = models.Player.objects.create(
            name="Ace Pitcher",
            position="P",
            level="V",
            team=self.team,
            is_owned=True,
            is_ulmg_mlb_roster=True,
            is_ulmg_35man_roster=True,
        )
        self.aaa_player = models.Player.objects.create(
            name="Callup Guy",
            position="OF",
            level="A",
            team=self.team,
            is_owned=True,
            is_ulmg_aaa_roster=True,
            is_ulmg_35man_roster=True,
        )
        self.prospect = models.Player.objects.create(
            name="Kid Prospect",
            position="IF",
            level="B",
            team=self.team,
            is_owned=True,
        )
        for _ in range(19):
            models.Player.objects.create(
                name=f"B Filler {_}",
                position="OF",
                level="B",
                team=self.team,
                is_owned=True,
            )
        self.pick = models.DraftPick.objects.create(
            year="2026",
            season="offseason",
            draft_type="open",
            draft_round=1,
            pick_number=3,
            team=self.team,
            original_team=self.team,
        )
        # Avoid m2m trade signals relocating roster players used in other assertions.
        trade_out = models.Player.objects.create(
            name="Trade Out", position="P", level="V", team=self.team, is_owned=True
        )
        trade_in = models.Player.objects.create(
            name="Trade In", position="OF", level="A", team=self.other, is_owned=True
        )
        self.trade = models.Trade.objects.create(date=datetime.date(2025, 7, 1))
        import os

        os.environ["ULMG_FIXTURES"] = "1"
        try:
            r1 = models.TradeReceipt.objects.create(trade=self.trade, team=self.team)
            r1.players.add(trade_in)
            r2 = models.TradeReceipt.objects.create(trade=self.trade, team=self.other)
            r2.players.add(trade_out)
            self.trade.set_teams()
            self.trade.save()
        finally:
            os.environ.pop("ULMG_FIXTURES", None)

        wishlist = models.Wishlist.objects.create(owner=self.owner)
        models.WishlistPlayer.objects.create(
            wishlist=wishlist,
            player=self.prospect,
            tier=2,
            rank=5,
            note="like the bat",
        )

        self.raw, _ = models.OwnerAPIToken.create_token(self.owner, label="tests")

    def _get(self, path, **params):
        return self.client.get(
            path,
            data=params,
            HTTP_AUTHORIZATION=f"Bearer {self.raw}",
        )

    def test_list_teams(self):
        resp = self._get("/api/mcp/v1/teams/")
        self.assertEqual(resp.status_code, 200)
        abbrs = {t["abbreviation"] for t in resp.json()["teams"]}
        self.assertEqual(abbrs, {"BOS", "NYK"})

    def test_team_roster(self):
        resp = self._get("/api/mcp/v1/teams/BOS/roster/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["team"]["abbreviation"], "BOS")
        self.assertEqual(data["counts"]["total"], 23)
        mlb_names = {p["name"] for p in data["mlb"]}
        self.assertIn("Ace Pitcher", mlb_names)
        aaa_names = {p["name"] for p in data["aaa"]}
        self.assertIn("Callup Guy", aaa_names)
        aa_names = {p["name"] for p in data["aa"]}
        self.assertIn("Kid Prospect", aa_names)

    def test_team_roster_defaults_to_my_team(self):
        resp = self._get("/api/mcp/v1/roster/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["team"]["abbreviation"], "BOS")

    def test_roster_compliance(self):
        resp = self._get("/api/mcp/v1/teams/BOS/compliance/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["counts"]["mlb_30man"], 1)
        self.assertEqual(data["counts"]["protect_40man"], 2)
        self.assertEqual(data["counts"]["total"], 23)
        self.assertEqual(data["counts"]["b_level"], 20)
        self.assertTrue(data["limits"]["b_level_ok"])
        self.assertTrue(data["limits"]["total_ok"])

    def test_search_players(self):
        resp = self._get("/api/mcp/v1/players/search/", level="B", owned="true", position="IF")
        self.assertEqual(resp.status_code, 200)
        names = {p["name"] for p in resp.json()["players"]}
        self.assertIn("Kid Prospect", names)

    def test_list_draft_picks_for_team(self):
        resp = self._get(
            "/api/mcp/v1/draft-picks/",
            team="BOS",
            year="2026",
            season="offseason",
            draft_type="open",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["picks"]), 1)
        self.assertEqual(resp.json()["picks"][0]["draft_round"], 1)

    def test_list_trades(self):
        resp = self._get("/api/mcp/v1/trades/", team="BOS")
        self.assertEqual(resp.status_code, 200)
        trades = resp.json()["trades"]
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["trade_id"], self.trade.id)
        self.assertIn("team_1", trades[0])
        self.assertIn("team_1_receives", trades[0])

    def test_trade_block(self):
        self.mlb_player.is_ulmg_trade_block = True
        self.mlb_player.save()
        resp = self._get("/api/mcp/v1/trade-block/")
        self.assertEqual(resp.status_code, 200)
        names = {p["name"] for p in resp.json()["players"]}
        self.assertIn("Ace Pitcher", names)

    def test_available_for_draft_offseason(self):
        exposed = models.Player.objects.create(
            name="Unprotected Vet",
            position="OF",
            level="V",
            team=self.other,
            is_owned=True,
        )
        resp = self._get("/api/mcp/v1/draft-pool/", pool="unprotected")
        self.assertEqual(resp.status_code, 200)
        names = {p["name"] for p in resp.json()["players"]}
        self.assertIn("Unprotected Vet", names)
        self.assertNotIn("Ace Pitcher", names)  # on 40-man

    def test_my_wishlist(self):
        resp = self._get("/api/mcp/v1/wishlist/")
        self.assertEqual(resp.status_code, 200)
        players = resp.json()["players"]
        self.assertEqual(len(players), 1)
        self.assertEqual(players[0]["tier"], 2)
        self.assertEqual(players[0]["rank"], 5)
        self.assertEqual(players[0]["note"], "like the bat")
