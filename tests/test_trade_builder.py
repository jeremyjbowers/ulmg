# ABOUTME: Tests for the trade builder: club order, the roster index, and the submit page.
# ABOUTME: Covers the asset query, the staff page, and a trade that moves a player and a pick.
import json
import re

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ulmg import models
from ulmg.trade_builder import trade_builder_assets


@override_settings(CURRENT_SEASON=2027)
class TradeBuilderAssetsTestCase(TestCase):
    """The index the page hands the browser, without printing every roster twice."""

    def setUp(self):
        self.albany = models.Team.objects.create(
            city="Albany", abbreviation="ALB", nickname="Aces", division="West"
        )
        self.ants = models.Team.objects.create(
            city="Boston", abbreviation="ZZZ", nickname="Ants", division="East"
        )
        self.zebras = models.Team.objects.create(
            city="Boston", abbreviation="AAA", nickname="Zebras", division="East"
        )
        self.cincinnati = models.Team.objects.create(
            city="Cincinnati", abbreviation="CIN", nickname="Cubs", division="East"
        )
        self.catcher = models.Player.objects.create(
            name="Carl Catcher", position="C", level="V", team=self.albany
        )
        self.infielder = models.Player.objects.create(
            name="Ada Infielder",
            position="IF",
            level="V",
            team=self.albany,
            is_ulmg_trade_block=True,
        )
        self.two_way = models.Player.objects.create(
            name="Ada Two", position="OF-P", level="B", team=self.albany
        )
        self.abe = models.Player.objects.create(
            name="Abe Pitcher", position="P", level="A", team=self.zebras
        )
        self.zack = models.Player.objects.create(
            name="Zack Pitcher", position="P", level="A", team=self.zebras
        )
        models.Player.objects.create(name="Una Owned", position="OF", level="B")
        self.open_pick = self.pick(self.cincinnati, "2027", "offseason", "open", 1)
        self.later_round = self.pick(self.cincinnati, "2027", "offseason", "open", 3)
        self.future_pick = self.pick(self.cincinnati, "2028", "midseason", "aa", 1)
        taken = models.Player.objects.create(
            name="Already Drafted", position="OF", level="B", team=self.cincinnati
        )
        self.used_pick = self.pick(
            self.cincinnati, "2027", "offseason", "open", 2, player=taken
        )
        self.old_pick = self.pick(self.cincinnati, "2026", "offseason", "open", 1)
        self.pick(None, "2027", "midseason", "open", 1)

    def pick(self, team, year, season, draft_type, draft_round, player=None):
        return models.DraftPick.objects.create(
            team=team,
            year=year,
            season=season,
            draft_type=draft_type,
            draft_round=draft_round,
            player=player,
        )

    def test_clubs_are_alphabetical_by_city_then_nickname(self):
        with self.assertNumQueries(3):
            assets = trade_builder_assets()

        self.assertEqual(
            [(team["abbr"], team["label"]) for team in assets["teams"]],
            [
                ("alb", "Albany Aces (ALB)"),
                ("zzz", "Boston Ants (ZZZ)"),
                ("aaa", "Boston Zebras (AAA)"),
                ("cin", "Cincinnati Cubs (CIN)"),
            ],
        )

    def test_rosters_keep_hitters_pitchers_and_open_picks(self):
        assets = trade_builder_assets()
        albany = assets["rosters"]["alb"]
        self.assertEqual(
            [asset["label"] for asset in albany["hitters"]],
            [
                "C Carl Catcher · V",
                "IF Ada Infielder · V · block",
                "OF-P Ada Two · B",
            ],
        )
        self.assertEqual(
            [asset["id"] for asset in albany["hitters"]],
            [
                f"player-{self.catcher.id}",
                f"player-{self.infielder.id}",
                f"player-{self.two_way.id}",
            ],
        )
        self.assertEqual(albany["pitchers"], [])
        self.assertEqual(albany["picks"], [])

        zebras = assets["rosters"]["aaa"]
        self.assertEqual(zebras["hitters"], [])
        self.assertEqual(
            [asset["label"] for asset in zebras["pitchers"]],
            ["P Abe Pitcher · A", "P Zack Pitcher · A"],
        )
        self.assertEqual(assets["rosters"]["zzz"], {"hitters": [], "pitchers": [], "picks": []})

        encoded = json.dumps(assets["rosters"])
        self.assertNotIn("Una Owned", encoded)
        self.assertNotIn(f"pick-{self.used_pick.id}", encoded)
        self.assertNotIn(f"pick-{self.old_pick.id}", encoded)
        self.assertEqual(
            [asset["id"] for asset in assets["rosters"]["cin"]["picks"]],
            [
                f"pick-{self.open_pick.id}",
                f"pick-{self.later_round.id}",
                f"pick-{self.future_pick.id}",
            ],
        )
        self.assertEqual(
            [asset["label"] for asset in assets["rosters"]["cin"]["picks"]],
            [
                "2027 offseason CIN OP1",
                "2027 offseason CIN OP3",
                "2028 midseason CIN AA1",
            ],
        )


@override_settings(CURRENT_SEASON=2027)
class TradeBuilderPageTestCase(TradeBuilderAssetsTestCase):
    """The staff page lists clubs in order and does not print every player up front."""

    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user("commish", password="secret", is_staff=True)
        self.client.force_login(self.staff)

    def test_the_page_lists_clubs_and_keeps_players_in_the_roster_index(self):
        response = self.client.get("/special/trades/")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()

        options = []
        for select_id in ("team-1-select", "team-2-select"):
            block = re.search(
                rf'<select id="{select_id}".*?</select>', body, re.DOTALL
            )
            self.assertIsNotNone(block)
            options.extend(re.findall(r'<option value="([^"]*)">([^<]*)</option>', block.group(0)))
        values = [value for value, _label in options if value]
        labels = [label for value, label in options if value]
        self.assertEqual(
            values,
            ["alb", "zzz", "aaa", "cin", "alb", "zzz", "aaa", "cin"],
        )
        self.assertEqual(labels[0], "Albany Aces (ALB)")
        self.assertEqual(labels[1], "Boston Ants (ZZZ)")
        self.assertIn('aria-label="Club 1"', body)
        self.assertIn('aria-label="Club 2"', body)
        self.assertIn("Pick two clubs", body)
        self.assertIn('id="trade-assets"', body)
        self.assertIn("/api/v1/trade/bulk/", body)
        self.assertNotIn('class="player-option"', body)

        match = re.search(
            r'<script id="trade-assets" type="application/json">(.*?)</script>',
            body,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        rosters = json.loads(match.group(1))
        self.assertEqual(body.count("Ada Infielder"), 1)
        self.assertIn("Ada Infielder", match.group(1))
        self.assertNotIn("Una Owned", body)
        self.assertEqual(
            rosters["cin"]["picks"][0]["id"],
            f"pick-{self.open_pick.id}",
        )

    def test_a_visitor_and_a_manager_are_sent_to_log_in(self):
        self.client.logout()
        visitor = self.client.get("/special/trades/")
        self.assertEqual(visitor.status_code, 302)
        self.assertIn("/accounts/login/", visitor.url)

        manager = User.objects.create_user("mgr", password="secret")
        self.client.force_login(manager)
        refused = self.client.get("/special/trades/")
        self.assertEqual(refused.status_code, 302)
        self.assertIn("/admin/login/", refused.url)


@override_settings(CURRENT_SEASON=2027)
class TradeBuilderSubmitTestCase(TradeBuilderAssetsTestCase):
    """A name clicked on a club is what that club sends, which is what the bulk API expects."""

    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_user("commish", password="secret"))

    def post_trade(self, payload):
        return self.client.post(
            "/api/v1/trade/bulk/",
            data=json.dumps(payload),
            content_type="application/x-www-form-urlencoded",
        )

    def test_the_clicked_player_and_pick_change_clubs(self):
        response = self.post_trade(
            [
                {"team": "alb", "receipt": [f"player-{self.infielder.id}"]},
                {
                    "team": "cin",
                    "receipt": [f"pick-{self.open_pick.id}"],
                },
            ]
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.infielder.refresh_from_db()
        self.open_pick.refresh_from_db()
        self.assertEqual(self.infielder.team, self.cincinnati)
        self.assertEqual(self.open_pick.team, self.albany)
