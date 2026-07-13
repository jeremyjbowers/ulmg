# ABOUTME: Tests for roster UI on team pages: sticky badges when tabs are on, MLB status column.

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

    def test_team_page_hides_mlb_roster_badge_in_midseason(self):
        self.client.login(username="mgr", password="secret")
        with override_settings(
            CURRENT_SEASON_TYPE="midseason",
            TEAM_ROSTER_TAB=True,
            TEAM_PROTECT_TAB=True,
        ):
            response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "MLB Roster:")

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

    def test_team_page_shows_level_and_roster_resource_from_stat_season(self):
        p = models.Player.objects.create(
            name="Big Leaguer",
            position="IF",
            level="A",
            team=self.team,
        )
        models.PlayerStatSeason.objects.create(
            player=p,
            season=2026,
            classification="1-mlb",
            level="MLB",
            role="10-Day IL",
            roster_status="IL-10",
            is_career=False,
        )
        cache.clear()
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'title="Roster resource status: role, IL, bench, starter, etc."'
        )
        self.assertContains(response, "10-Day IL")
        self.assertContains(response, "MLB")
        self.assertNotContains(response, "✅ on")
        self.assertNotContains(response, "ULMG MLB (30-man)")
