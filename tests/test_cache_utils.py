# ABOUTME: Tests for bounded Valkey cache keys and team roster query caching.
# ABOUTME: Ensures filter params are whitelisted and junk query strings cannot explode cache.

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from ulmg import models, utils
from ulmg.cache_utils import team_roster_cache_key


class TeamRosterCacheKeyTestCase(TestCase):
    def test_key_includes_team_season_and_classification(self):
        key = team_roster_cache_key("tst", 2024, "2-milb")
        self.assertEqual(key, "ulmg:team:TST:roster:2024:2-milb")

    def test_key_uses_all_when_classification_missing(self):
        key = team_roster_cache_key("abc", 2026, None)
        self.assertEqual(key, "ulmg:team:ABC:roster:2026:all")

    def test_distinct_keys_for_distinct_filter_combinations(self):
        keys = {
            team_roster_cache_key("TST", 2026, None),
            team_roster_cache_key("TST", 2025, None),
            team_roster_cache_key("TST", 2026, "1-mlb"),
            team_roster_cache_key("TST", 2026, "2-milb"),
            team_roster_cache_key("NYM", 2026, None),
        }
        self.assertEqual(len(keys), 5)


@override_settings(
    CURRENT_SEASON=2026,
    CURRENT_SEASON_TYPE="midseason",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
)
class TeamRosterQueryCacheTestCase(TestCase):
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
        self.player = models.Player.objects.create(
            name="Cached Guy",
            position="IF",
            level="A",
            team=self.team,
        )
        models.PlayerStatSeason.objects.create(
            player=self.player,
            season=2025,
            classification="1-mlb",
            hit_stats={"pa": 400, "avg": 0.270, "k_pct": 0.20, "bb_pct": 0.10},
            is_career=False,
        )

    def test_junk_query_params_do_not_create_extra_cache_entries(self):
        self.client.login(username="mgr", password="secret")
        self.client.get("/teams/tst/?season=2025&foo=bar&baz=qux")
        self.client.get("/teams/tst/?season=2025&other=junk")

        key = team_roster_cache_key("TST", 2025, None)
        self.assertIsNotNone(cache.get(key))
        self.assertIsNone(cache.get(team_roster_cache_key("TST", 2025, "foo")))

    def test_invalid_season_reuses_current_season_cache_key(self):
        self.client.login(username="mgr", password="secret")
        self.client.get("/teams/tst/?season=1999")
        self.client.get("/teams/tst/")

        current_key = team_roster_cache_key("TST", 2026, None)
        self.assertIsNotNone(cache.get(current_key))
        self.assertIsNone(cache.get(team_roster_cache_key("TST", 1999, None)))

    def test_explicit_season_uses_separate_cache_entry(self):
        self.client.login(username="mgr", password="secret")
        self.client.get("/teams/tst/")
        self.client.get("/teams/tst/?season=2025")

        self.assertIsNotNone(cache.get(team_roster_cache_key("TST", 2026, None)))
        self.assertIsNotNone(cache.get(team_roster_cache_key("TST", 2025, None)))


class ParseTeamRosterStatFiltersCacheSafetyTestCase(TestCase):
    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_rejects_season_outside_picker_choices(self):
        request = type("Req", (), {"GET": {"season": "1999"}})()
        season, classification = utils.parse_team_roster_stat_filters(request)
        self.assertEqual(season, 2026)
        self.assertIsNone(classification)

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_ignores_unrelated_query_params(self):
        request = type("Req", (), {"GET": {"season": "2024", "foo": "bar"}})()
        season, classification = utils.parse_team_roster_stat_filters(request)
        self.assertEqual(season, 2024)
        self.assertIsNone(classification)
