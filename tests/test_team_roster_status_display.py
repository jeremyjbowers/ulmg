# ABOUTME: Tests for roster UI on team pages: stat columns, org/roster display, no row actions by default.

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from ulmg import models


@override_settings(CURRENT_SEASON=2026)
class TeamRosterStatusDisplayTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="secret")
        self.owner = models.Owner.objects.create(user=self.user, name="Manager")
        self.team = models.Team.objects.create(
            city="Test City",
            abbreviation="TST",
            nickname="Testers",
            owner_obj=self.owner,
        )

    def test_team_page_hides_mlb_roster_badge_when_roster_tab_off(self):
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "MLB Roster")
        self.assertNotContains(response, 'id="roster-mlb-count"')

    def test_team_page_shows_mlb_roster_badge_only_when_roster_tab_on(self):
        self.client.login(username="mgr", password="secret")
        with override_settings(
            CURRENT_SEASON_TYPE="midseason",
            TEAM_ROSTER_TAB=True,
            TEAM_PROTECT_TAB=True,
        ):
            response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MLB Roster")
        self.assertContains(response, 'id="roster-mlb-count"')
        self.assertContains(response, "/30")

    def test_team_page_shows_org_and_roster_stat_columns(self):
        p = models.Player.objects.create(
            name="Big Leaguer",
            position="IF",
            level="A",
            team=self.team,
            is_ulmg_mlb_roster=True,
            carded_seasons=[2025],
        )
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2026,
            classification="1-mlb",
            level="MLB",
            role="10-Day IL",
            roster_status="IL-10",
            mlb_org="NYY",
            is_career=False,
        )
        cache.clear()
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'title="ULMG player level (V, A, or B)"')
        self.assertContains(
            response, 'title="League / org level from stat season (e.g. MLB, AAA)"'
        )
        self.assertContains(
            response, 'title="Roster resource status: role, IL, bench, starter, etc."'
        )
        content = response.content.decode()
        player_idx = content.find("Big Leaguer")
        self.assertNotEqual(player_idx, -1)
        row_chunk = content[player_idx : player_idx + 2500]
        self.assertIn(">A<", row_chunk)
        self.assertIn(">NYY<", row_chunk)
        self.assertNotIn('data-action="off_roster"', row_chunk)

    def test_team_page_shows_pitcher_g_and_fip_columns(self):
        p = models.Player.objects.create(
            name="Compact Ace",
            position="P",
            level="V",
            team=self.team,
        )
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2026,
            classification="1-mlb",
            pitch_stats={
                "g": 45,
                "gs": 32,
                "ip": 200,
                "era": 3.25,
                "whip": 1.05,
                "k_9": 9.5,
                "bb_9": 2.1,
                "hr_9": 1.0,
                "fip": 3.10,
                "xfip": 3.20,
                "siera": 3.15,
                "war": 4.2,
            },
            is_career=False,
        )
        cache.clear()
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        pitcher_idx = content.find("Compact Ace")
        self.assertNotEqual(pitcher_idx, -1)
        header_chunk = content[pitcher_idx - 1200 : pitcher_idx]
        self.assertIn(">G</th>", header_chunk)
        self.assertIn(">FIP</th>", header_chunk)
        self.assertIn(">WAR</th>", header_chunk)
        self.assertIn(">GS</th>", header_chunk)
        self.assertIn(">xFIP</th>", header_chunk)
        row_chunk = content[pitcher_idx : pitcher_idx + 1200]
        self.assertIn(">45<", row_chunk)
        self.assertIn(">32<", row_chunk)
        self.assertIn(">3.10<", row_chunk)
        self.assertIn(">4.2<", row_chunk)

    def test_team_page_collapses_hitter_stats_into_actual_and_expected_columns(self):
        p = models.Player.objects.create(
            name="Slash Line",
            position="IF",
            level="A",
            team=self.team,
        )
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2026,
            classification="1-mlb",
            level="MLB",
            hit_stats={
                "pa": 500,
                "avg": 0.268,
                "obp": 0.350,
                "slg": 0.425,
                "k_pct": 0.20,
                "bb_pct": 0.10,
                "xavg": 0.275,
                "xwoba": 0.340,
                "xslg": 0.430,
                "obp_plus": 120,
                "slg_plus": 130,
                "war": 3.7,
            },
            is_career=False,
        )
        cache.clear()
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ">Actual<")
        self.assertContains(response, ">Expected<")
        self.assertContains(response, ">OPS+<")
        self.assertContains(response, ">WAR<")
        self.assertNotContains(response, ">AVG<")
        self.assertNotContains(response, ">xA<")
        self.assertContains(response, ".268/.350/.425")
        self.assertContains(response, ".275/.340/.430")
        content = response.content.decode()
        player_idx = content.find("Slash Line")
        row_chunk = content[player_idx : player_idx + 2000]
        self.assertIn("150", row_chunk)
        self.assertIn("3.7", row_chunk)

    def test_traded_player_does_not_get_mlb_button_when_roster_tab_off(self):
        traded = models.Player.objects.create(
            name="Traded Vet",
            position="OF",
            level="V",
            team=self.team,
            is_owned=True,
            carded_seasons=None,
        )
        models.PlayerStatSeason.objects.create(
            player=traded,
            season=2025,
            classification="1-mlb",
            hit_stats={"pa": 100, "g": 30},
            is_career=False,
        )
        cache.clear()
        self.client.login(username="mgr", password="secret")
        with override_settings(
            CURRENT_SEASON_TYPE="midseason",
            TEAM_ROSTER_TAB=False,
            TEAM_PROTECT_TAB=False,
            TEAM_SEASON_HALF="2h",
        ):
            response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        player_idx = content.find("Traded Vet")
        self.assertNotEqual(player_idx, -1)
        row_chunk = content[player_idx : player_idx + 2500]
        self.assertNotIn('data-action="to_mlb"', row_chunk)
