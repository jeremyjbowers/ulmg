# ABOUTME: Tests for year and stats-level filters on team roster pages.
# ABOUTME: Ensures default view uses current season only and honors explicit filters.

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import models, utils


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class TeamStatFiltersTestCase(TestCase):
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
        self.player = models.Player.objects.create(
            name="Stat Filter Guy",
            position="IF",
            level="A",
            team=self.team,
        )
        models.PlayerStatSeason.objects.create(
            player=self.player,
            season=2025,
            classification="1-mlb",
            level="MLB",
            hit_stats={"pa": 500, "avg": 0.300, "k_pct": 0.20, "bb_pct": 0.10},
            is_career=False,
        )
        models.PlayerStatSeason.objects.create(
            player=self.player,
            season=2025,
            classification="2-milb",
            level="AAA",
            hit_stats={"pa": 100, "avg": 0.250, "k_pct": 0.20, "bb_pct": 0.10},
            is_career=False,
        )
        models.PlayerStatSeason.objects.create(
            player=self.player,
            season=2024,
            classification="1-mlb",
            level="MLB",
            hit_stats={"pa": 600, "avg": 0.280, "k_pct": 0.20, "bb_pct": 0.10},
            is_career=False,
        )

    def test_default_shows_current_season_only_not_prior_year(self):
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stat Filter Guy")
        self.assertNotContains(response, 'data-value="500"')
        self.assertNotContains(response, 'data-value="600"')

    def test_explicit_season_shows_that_year_stats(self):
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/?season=2024")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-value="600"')

    def test_no_classification_prefers_higher_level(self):
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/?season=2025")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-value="500"')
        self.assertNotContains(response, 'data-value="100"')

    def test_classification_filter_limits_stats_level(self):
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/?season=2025&classification=2-milb")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-value="100"')
        self.assertNotContains(response, 'data-value="500"')

    def test_team_page_includes_stat_filter_form(self):
        self.client.login(username="mgr", password="secret")
        response = self.client.get("/teams/tst/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="season"')
        self.assertContains(response, 'name="classification"')
        self.assertContains(response, "Stats Level")


class ParseTeamRosterStatFiltersTestCase(TestCase):
    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_defaults_to_current_season_without_params(self):
        request = type("Req", (), {"GET": {}})()
        season, classification = utils.parse_team_roster_stat_filters(request)
        self.assertEqual(season, 2026)
        self.assertIsNone(classification)

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_parses_explicit_season_and_classification(self):
        request = type("Req", (), {"GET": {"season": "2024", "classification": "3-npb"}})()
        season, classification = utils.parse_team_roster_stat_filters(request)
        self.assertEqual(season, 2024)
        self.assertEqual(classification, "3-npb")

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_rejects_season_not_in_picker_choices(self):
        request = type("Req", (), {"GET": {"season": "1999"}})()
        season, classification = utils.parse_team_roster_stat_filters(request)
        self.assertEqual(season, 2026)
        self.assertIsNone(classification)

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_ignores_invalid_classification(self):
        request = type("Req", (), {"GET": {"classification": "invalid"}})()
        season, classification = utils.parse_team_roster_stat_filters(request)
        self.assertEqual(season, 2026)
        self.assertIsNone(classification)
