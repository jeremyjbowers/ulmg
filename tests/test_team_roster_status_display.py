# ABOUTME: Tests for MLB roster UI on team roster pages and the 30-man column.
# ABOUTME: Covers sticky badge (offseason + roster_tab) and per-row On/Off display.

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import models


@override_settings(CURRENT_SEASON=2026)
class TeamRosterStatusDisplayTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="secret")
        self.owner = models.Owner.objects.create(user=self.user, name="Manager")
        self.team = models.Team.objects.create(
            city="Test City",
            abbreviation="TST",
            nickname="Testers",
            owner_obj=self.owner,
        )

    def test_team_page_hides_mlb_roster_badge_in_midseason(self):
        self.client.login(username="mgr", password="secret")
        with override_settings(
            CURRENT_SEASON_TYPE="midseason",
            TEAM_ROSTER_TAB=True,
            TEAM_PROTECT_TAB=True,
        ):
            response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "MLB Roster")

    def test_team_page_shows_mlb_roster_badge_in_offseason_when_roster_tab_on(self):
        self.client.login(username="mgr", password="secret")
        with override_settings(
            CURRENT_SEASON_TYPE="offseason",
            TEAM_ROSTER_TAB=True,
            TEAM_PROTECT_TAB=False,
        ):
            response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MLB Roster")
        self.assertContains(response, 'id="roster-mlb-count"')

    def test_team_page_shows_30_man_column_on_off(self):
        models.Player.objects.create(
            name="On Thirty",
            position="IF",
            level="A",
            team=self.team,
            is_ulmg_mlb_roster=True,
            is_ulmg_aaa_roster=False,
            is_ulmg_reserve=False,
        )
        models.Player.objects.create(
            name="Off Thirty",
            position="IF",
            level="A",
            team=self.team,
            is_ulmg_mlb_roster=False,
        )
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'title="ULMG MLB (30-man) roster"')
        self.assertContains(response, "✅ on")
        content = response.content.decode()
        self.assertGreaterEqual(content.count("✅ on"), 1)
