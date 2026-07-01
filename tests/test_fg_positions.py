# ABOUTME: Tests for FanGraphs position1 storage, display, and qualified-at filtering.
# ABOUTME: Ensures Strat defense remains primary when present.
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from ulmg import models, utils
from ulmg.management.commands.live_update_status_from_fg_rosters import Command


class ParseFgPosition1TestCase(TestCase):
    def test_parses_multi_position_hitter_profile(self):
        self.assertEqual(utils.parse_fg_position1("2B/3B/SS"), ["2B", "3B", "SS"])

    def test_ignores_pitcher_tokens(self):
        self.assertEqual(utils.parse_fg_position1("SP/RP"), [])
        self.assertEqual(utils.parse_fg_position1("SP"), [])

    def test_keeps_hitter_positions_when_mixed_with_pitcher_tokens(self):
        self.assertEqual(utils.parse_fg_position1("1B/SP"), ["1B"])

    def test_formats_display_in_standard_order(self):
        self.assertEqual(
            utils.format_fg_positions_display(["RF", "2B", "C"]),
            "C, 2B, RF",
        )


class PlayerStatSeasonPositionDisplayTestCase(TestCase):
    def setUp(self):
        self.player = models.Player.objects.create(name="Casey Schmitt", position="IF")
        self.pss = models.PlayerStatSeason.objects.create(
            player=self.player,
            season=2026,
            classification="1-mlb",
            fg_positions=["2B", "3B", "SS"],
        )

    def test_position_display_uses_strat_defense_when_present(self):
        self.pss.defense = ["SS-6-4", "3B-5-3"]
        self.pss.save()
        self.assertEqual(self.pss.position_display(), "3B3, SS4")

    def test_position_display_falls_back_to_fg_positions(self):
        self.assertEqual(self.pss.position_display(), "2B, 3B, SS")

    def test_position_display_skips_fg_positions_for_pitchers(self):
        pitcher = models.Player.objects.create(name="Logan Webb", position="P")
        pss = models.PlayerStatSeason.objects.create(
            player=pitcher,
            season=2026,
            classification="1-mlb",
            fg_positions=["SP"],
        )
        self.assertIsNone(pss.position_display())


class LiveUpdateFgPositionsTestCase(TestCase):
    @patch(
        "ulmg.management.commands.live_update_status_from_fg_rosters.settings.ROSTER_TEAM_IDS",
        [(30, "SFG", "San Francisco Giants")],
    )
    @patch("ulmg.management.commands.live_update_status_from_fg_rosters.utils.get_current_season", return_value=2026)
    @patch("ulmg.management.commands.live_update_status_from_fg_rosters.utils.s3_manager")
    def test_stores_fg_positions_from_position1(self, mock_s3, _mock_season):
        player = models.Player.objects.create(
            name="Luis Arraez",
            position="IF",
            fg_id="12345",
        )
        mock_s3.get_file_content.return_value = [
            {
                "player": "Luis Arraez",
                "position": "2B",
                "position1": "1B/2B",
                "oPlayerId": "12345",
                "role": "1",
                "mlevel": "MLB",
                "type": "mlb-sl",
                "dbTeam": "SFG",
            }
        ]

        Command().handle()

        pss = models.PlayerStatSeason.objects.get(player=player, season=2026)
        self.assertEqual(pss.fg_positions, ["1B", "2B"])

    @patch(
        "ulmg.management.commands.live_update_status_from_fg_rosters.settings.ROSTER_TEAM_IDS",
        [(30, "SFG", "San Francisco Giants")],
    )
    @patch("ulmg.management.commands.live_update_status_from_fg_rosters.utils.get_current_season", return_value=2026)
    @patch("ulmg.management.commands.live_update_status_from_fg_rosters.utils.s3_manager")
    def test_does_not_store_fg_positions_for_pitchers(self, mock_s3, _mock_season):
        player = models.Player.objects.create(
            name="Logan Webb",
            position="P",
            fg_id="99999",
        )
        mock_s3.get_file_content.return_value = [
            {
                "player": "Logan Webb",
                "position": "SP",
                "position1": "SP/RP",
                "oPlayerId": "99999",
                "role": "SP1",
                "mlevel": "MLB",
                "type": "mlb-sp",
                "dbTeam": "SFG",
            }
        ]

        Command().handle()

        pss = models.PlayerStatSeason.objects.get(player=player, season=2026)
        self.assertIsNone(pss.fg_positions)


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class FilterPlayersByQualifiedAtTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="secret")
        owner = models.Owner.objects.create(user=self.user, name="Manager")
        models.Team.objects.create(
            city="Test City",
            abbreviation="TST",
            nickname="Testers",
            owner_obj=owner,
        )
        self.client.login(username="mgr", password="secret")
        self.ss_player = models.Player.objects.create(name="Shortstop Guy", position="IF")
        self.of_player = models.Player.objects.create(name="Outfield Guy", position="OF")
        models.PlayerStatSeason.objects.create(
            player=self.ss_player,
            season=2026,
            classification="1-mlb",
            fg_positions=["SS", "2B"],
        )
        models.PlayerStatSeason.objects.create(
            player=self.of_player,
            season=2026,
            classification="1-mlb",
            fg_positions=["LF", "CF", "RF"],
        )

    def test_filter_players_by_qualified_at(self):
        response = self.client.get("/search/filter/", {"qualified_at": "SS", "season": "2026"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Shortstop Guy", content)
        self.assertNotIn("Outfield Guy", content)


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class FilterPlayersByCardedYearTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="secret")
        owner = models.Owner.objects.create(user=self.user, name="Manager")
        models.Team.objects.create(
            city="Test City",
            abbreviation="TST",
            nickname="Testers",
            owner_obj=owner,
        )
        self.client.login(username="mgr", password="secret")
        self.player = models.Player.objects.create(
            name="Carded Hitter",
            position="IF",
            carded_seasons=[2024],
        )
        models.PlayerStatSeason.objects.create(
            player=self.player,
            season=2024,
            classification="1-mlb",
            hit_stats={"pa": 512, "avg": 0.285, "k_pct": 0.18, "bb_pct": 0.09},
        )
        models.PlayerStatSeason.objects.create(
            player=self.player,
            season=2026,
            classification="1-mlb",
            hit_stats={"pa": 42, "avg": 0.190, "k_pct": 0.25, "bb_pct": 0.05},
        )

    def test_carded_year_filter_shows_that_years_stats(self):
        response = self.client.get("/search/filter/", {"carded": "2024"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Carded Hitter", content)
        self.assertIn("512", content)
        self.assertNotIn(">42<", content)

    def test_carded_year_filter_excludes_players_without_appearances(self):
        ghost = models.Player.objects.create(
            name="Ghost Card",
            position="IF",
            carded_seasons=[2025],
        )
        models.PlayerStatSeason.objects.create(
            player=ghost,
            season=2025,
            classification="1-mlb",
            carded=True,
            hit_stats={"pa": 0, "g": 0, "k_pct": 0, "bb_pct": 0},
        )
        models.PlayerStatSeason.objects.create(
            player=ghost,
            season=2025,
            classification="2-milb",
            hit_stats={"pa": 0, "g": 0, "k_pct": 0, "bb_pct": 0},
        )

        response = self.client.get("/search/filter/", {"carded": "2025"})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("Ghost Card", content)


class PlayerStatSeasonCardedTestCase(TestCase):
    def test_has_mlb_appearances_requires_pa_ip_or_g(self):
        with_stats = models.PlayerStatSeason(
            classification="1-mlb",
            hit_stats={"pa": 10},
        )
        without_stats = models.PlayerStatSeason(
            classification="1-mlb",
            hit_stats={"pa": 0, "g": 0},
            pitch_stats={"ip": 0, "g": 0},
        )
        self.assertTrue(with_stats.has_mlb_appearances())
        self.assertFalse(without_stats.has_mlb_appearances())

    def test_save_sets_carded_from_appearances(self):
        player = models.Player.objects.create(name="Auto Card", position="IF")
        pss = models.PlayerStatSeason.objects.create(
            player=player,
            season=2025,
            classification="1-mlb",
            hit_stats={"pa": 25, "g": 8},
        )
        self.assertTrue(pss.carded)
        pss.hit_stats = {"pa": 0, "g": 0}
        pss.save()
        self.assertFalse(pss.carded)

    @override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
    def test_set_carded_seasons_uses_appearances_not_carded_flag(self):
        player = models.Player.objects.create(name="Seasons Guy", position="IF")
        models.PlayerStatSeason.objects.create(
            player=player,
            season=2025,
            classification="1-mlb",
            carded=True,
            hit_stats={"pa": 0, "g": 0},
        )
        models.PlayerStatSeason.objects.create(
            player=player,
            season=2024,
            classification="1-mlb",
            hit_stats={"pa": 100, "g": 30},
        )
        player.save()
        self.assertEqual(player.carded_seasons, [2024])
