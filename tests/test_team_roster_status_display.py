# ABOUTME: Tests for roster UI on team pages: stat columns, org/roster display, and MLB/AAA buttons.
# ABOUTME: Owners set those rosters from their own team page while TEAM_ROSTER_TAB is on.

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from tests.usage_fixtures import create_hitter, create_pitcher
from ulmg import models


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
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

    @override_settings(TEAM_ROSTER_TAB=False)
    def test_team_page_hides_mlb_roster_badge_when_roster_tab_off(self):
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "MLB Roster")
        self.assertNotContains(response, 'id="roster-mlb-count"')

    def test_owner_sets_mlb_and_aaa_rosters_from_the_team_page(self):
        hitter = create_hitter("Roster Hitter", team=self.team, pa=100, g=30)
        pitcher = create_pitcher("Roster Pitcher", team=self.team, g=30, ip="60.0")
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("MLB Roster", content)
        self.assertIn('id="roster-mlb-count"', content)
        for name in ("Roster Hitter", "Roster Pitcher"):
            player_idx = content.find(name)
            self.assertNotEqual(player_idx, -1)
            row = content[player_idx : player_idx + 2500]
            self.assertIn('data-action="to_mlb"', row)
            self.assertIn('data-action="to_aaa"', row)

        other = User.objects.create_user(username="other", password="secret")
        other_owner = models.Owner.objects.create(user=other, name="Other")
        models.Team.objects.create(
            city="Other City",
            abbreviation="OTH",
            nickname="Others",
            owner_obj=other_owner,
        )
        other_client = Client()
        other_client.login(username="other", password="secret")
        other_page = other_client.get("/teams/tst/")
        self.assertEqual(other_page.status_code, 200)
        self.assertNotContains(other_page, 'data-action="to_mlb"')
        self.assertNotContains(other_page, 'data-action="to_aaa"')

        mlb = self.client.get(f"/api/v1/player/{hitter.id}/to_mlb/")
        self.assertEqual(mlb.content, b"ok")
        aaa = self.client.get(f"/api/v1/player/{pitcher.id}/to_aaa/")
        self.assertEqual(aaa.content, b"ok")
        hitter.refresh_from_db()
        pitcher.refresh_from_db()
        self.assertTrue(hitter.is_ulmg_mlb_roster)
        self.assertFalse(hitter.is_ulmg_aaa_roster)
        self.assertTrue(pitcher.is_ulmg_aaa_roster)
        self.assertFalse(pitcher.is_ulmg_mlb_roster)

        again = self.client.get("/teams/tst/").content.decode()
        hitter_idx = again.find("Roster Hitter")
        pitcher_idx = again.find("Roster Pitcher")
        hitter_row = again[hitter_idx : hitter_idx + 2500]
        pitcher_row = again[pitcher_idx : pitcher_idx + 2500]
        self.assertIn('data-roster="mlb" data-action="off_roster">MLB</a>', hitter_row)
        self.assertIn('data-roster="aaa" data-action="to_aaa">AAA</a>', hitter_row)
        self.assertIn('data-roster="mlb" data-action="to_mlb">MLB</a>', pitcher_row)
        self.assertIn('data-roster="aaa" data-action="off_roster">AAA</a>', pitcher_row)

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

    @override_settings(TEAM_ROSTER_TAB=False)
    def test_team_page_hides_removed_metadata_columns(self):
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
        self.assertNotContains(
            response, 'title="League / org level from stat season (e.g. MLB, AAA)"'
        )
        self.assertNotContains(
            response, 'title="Roster resource status: role, IL, bench, starter, etc."'
        )
        self.assertNotContains(response, ">MLB</th>")
        self.assertNotContains(response, ">Role</th>")
        self.assertNotContains(response, ">Stats</th>")
        content = response.content.decode()
        player_idx = content.find("Big Leaguer")
        self.assertNotEqual(player_idx, -1)
        row_chunk = content[player_idx : player_idx + 2500]
        self.assertIn(">A<", row_chunk)
        self.assertNotIn(">NYY<", row_chunk)
        self.assertNotIn("10-Day IL", row_chunk)
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


class RosterCardYearTestCase(TestCase):
    """Roster buttons follow the card year in settings, not whichever stat line is on screen."""

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

    def _row(self, content, name):
        idx = content.find(name)
        self.assertNotEqual(idx, -1, name)
        return content[idx : idx + 2500]

    def test_a_2026_debut_gets_roster_buttons_and_a_2025_only_card_does_not(self):
        debut = models.Player.objects.create(
            name="Joshua Baez", position="OF", level="B", team=self.team, is_owned=True,
        )
        models.PlayerStatSeason.objects.create(
            player=debut, season=2026, classification="1-mlb",
            hit_stats={"pa": 188, "g": 29, "k_pct": 0.23, "bb_pct": 0.10}, is_career=False,
        )
        older = models.Player.objects.create(
            name="Older Card", position="OF", level="A", team=self.team, is_owned=True,
        )
        models.PlayerStatSeason.objects.create(
            player=older, season=2025, classification="1-mlb",
            hit_stats={"pa": 500, "g": 140, "k_pct": 0.20, "bb_pct": 0.08}, is_career=False,
        )
        minor = models.Player.objects.create(
            name="Eric Booth Jr.", position="OF", level="B", team=self.team, is_owned=True,
        )
        models.PlayerStatSeason.objects.create(
            player=minor, season=2026, classification="2-milb", level="A",
            hit_stats={"pa": 82, "g": 20, "k_pct": 0.22, "bb_pct": 0.09}, is_career=False,
        )
        self.client.login(username="mgr", password="secret")
        content = self.client.get("/teams/tst/").content.decode()

        debut_row = self._row(content, "Joshua Baez")
        self.assertIn('data-roster="mlb" data-action="to_mlb"', debut_row)
        self.assertIn('data-roster="aaa" data-action="to_aaa"', debut_row)
        placed = self.client.get(f"/api/v1/player/{debut.id}/to_mlb/")
        self.assertEqual(placed.content, b"ok")
        debut.refresh_from_db()
        self.assertTrue(debut.is_ulmg_mlb_roster)

        older_row = self._row(content, "Older Card")
        self.assertNotIn('data-action="to_mlb"', older_row)
        self.assertNotIn('data-action="to_aaa"', older_row)
        self.assertIn("drop-button", older_row)
        refused = self.client.get(f"/api/v1/player/{older.id}/to_mlb/")
        self.assertEqual(refused.status_code, 400)

        minor_row = self._row(content, "Eric Booth Jr.")
        self.assertNotIn('data-action="to_mlb"', minor_row)
        self.assertNotIn('data-action="to_aaa"', minor_row)
        self.assertIn("drop-button", minor_row)
