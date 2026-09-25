# ABOUTME: Tests that MCP player/roster JSON includes stats, xstats, WAR, and positions.
# ABOUTME: Covers hitter and pitcher PlayerStatSeason fields agents need for analysis.
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import models


HITTER_STATS = {
    "pa": 512,
    "avg": 0.285,
    "obp": 0.360,
    "slg": 0.480,
    "ops": 0.840,
    "hr": 24,
    "sb": 12,
    "k_pct": 0.18,
    "bb_pct": 0.09,
    "woba": 0.355,
    "wrc_plus": 125,
    "xavg": 0.275,
    "xwoba": 0.340,
    "xslg": 0.460,
    "obp_plus": 110,
    "slg_plus": 115,
    "war": 3.7,
}

PITCHER_STATS = {
    "g": 30,
    "gs": 30,
    "ip": 180.1,
    "era": 3.25,
    "whip": 1.05,
    "k_9": 9.5,
    "bb_9": 2.1,
    "hr_9": 1.0,
    "fip": 3.10,
    "xfip": 3.20,
    "siera": 3.15,
    "war": 4.2,
}


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class MCPPlayerStatsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="stats_owner", email="stats@example.com", password="x"
        )
        self.owner = models.Owner.objects.create(
            user=self.user, name="Stats Owner", email="stats@example.com"
        )
        self.team = models.Team.objects.create(
            city="Boston",
            abbreviation="BOS",
            nickname="Beans",
            owner_obj=self.owner,
        )
        self.hitter = models.Player.objects.create(
            name="Stat Hitter",
            position="OF",
            level="V",
            team=self.team,
            is_owned=True,
            is_ulmg_mlb_roster=True,
            bats="L",
            throws="R",
            current_mlb_org="BOS",
        )
        self.pitcher = models.Player.objects.create(
            name="Stat Pitcher",
            position="P",
            level="V",
            team=self.team,
            is_owned=True,
            is_ulmg_mlb_roster=True,
            bats="R",
            throws="R",
            current_mlb_org="BOS",
        )
        models.PlayerStatSeason.objects.create(
            player=self.hitter,
            season=2026,
            classification="1-mlb",
            level="MLB",
            hit_stats=HITTER_STATS,
            defense=["OF-8-4"],
            fg_positions=["LF", "CF"],
            is_career=False,
        )
        models.PlayerStatSeason.objects.create(
            player=self.pitcher,
            season=2026,
            classification="1-mlb",
            level="MLB",
            pitch_stats=PITCHER_STATS,
            is_career=False,
        )
        self.raw, _ = models.OwnerAPIToken.create_token(self.owner, label="stats")

    def _get(self, path, **params):
        return self.client.get(
            path, data=params, HTTP_AUTHORIZATION=f"Bearer {self.raw}"
        )

    def test_roster_hitter_includes_war_and_xstats(self):
        resp = self._get("/api/mcp/v1/teams/BOS/roster/")
        self.assertEqual(resp.status_code, 200)
        hitter = next(p for p in resp.json()["mlb"] if p["name"] == "Stat Hitter")
        self.assertEqual(hitter["position"], "OF")
        self.assertEqual(hitter["bats"], "L")
        self.assertEqual(hitter["throws"], "R")
        stats = hitter["stats"]
        self.assertEqual(stats["season"], 2026)
        self.assertEqual(stats["classification"], "1-mlb")
        self.assertIn("OF", stats["position_display"] or "")
        self.assertEqual(stats["war"], 3.7)
        self.assertEqual(stats["hit"]["wrc_plus"], 125)
        self.assertEqual(stats["hit"]["xwoba"], 0.340)
        self.assertEqual(stats["hit"]["xavg"], 0.275)
        self.assertEqual(stats["hit"]["xslg"], 0.460)
        self.assertEqual(stats["xstats"]["xwoba"], 0.340)

    def test_roster_pitcher_includes_war_and_expected_pitching(self):
        resp = self._get("/api/mcp/v1/roster/")
        self.assertEqual(resp.status_code, 200)
        pitcher = next(p for p in resp.json()["mlb"] if p["name"] == "Stat Pitcher")
        stats = pitcher["stats"]
        self.assertEqual(stats["war"], 4.2)
        self.assertEqual(stats["pitch"]["era"], 3.25)
        self.assertEqual(stats["pitch"]["xfip"], 3.20)
        self.assertEqual(stats["pitch"]["siera"], 3.15)
        self.assertEqual(stats["xstats"]["xfip"], 3.20)

    def test_search_includes_stats(self):
        resp = self._get(
            "/api/mcp/v1/players/search/", name="Stat Hitter", owned="true"
        )
        self.assertEqual(resp.status_code, 200)
        players = resp.json()["players"]
        self.assertEqual(len(players), 1)
        self.assertEqual(players[0]["stats"]["hit"]["war"], 3.7)
        self.assertEqual(players[0]["stats"]["xstats"]["xwoba"], 0.340)

    def test_wishlist_includes_stats(self):
        wishlist = models.Wishlist.objects.create(owner=self.owner)
        models.WishlistPlayer.objects.create(
            wishlist=wishlist, player=self.hitter, tier=1, rank=1
        )
        resp = self._get("/api/mcp/v1/wishlist/")
        self.assertEqual(resp.status_code, 200)
        player = resp.json()["players"][0]
        self.assertEqual(player["stats"]["war"], 3.7)
        self.assertEqual(player["stats"]["hit"]["hr"], 24)
