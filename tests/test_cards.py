# ABOUTME: Tests for engine cards: hitter/pitcher rates, running, fatigue, defense, fielding load, generation, display.
# ABOUTME: Stats are FanGraphs-shaped rows run through the real loader key processing; no HTTP is mocked.
import json
import os
import tempfile
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings

from ulmg import cards, models
from ulmg.management.commands.live_update_stats_from_fg_stats import Command as FgStatsCommand

FIXTURE_FLD = os.path.join(os.path.dirname(__file__), "fixtures", "fg_mlb_fld_sample.json")

# FanGraphs major-league batting/pitching rows, using the payload's own column names.
FG_HITTER_ROW = {
    "playerid": 990001,
    "xMLBAMID": 880001,
    "PlayerName": "Utility Infielder",
    "Season": 2025,
    "Age": 28,
    "G": 150,
    "AB": 528,
    "PA": 600,
    "H": 147,
    "1B": 90,
    "2B": 30,
    "3B": 3,
    "HR": 24,
    "BB": 60,
    "IBB": 3,
    "SO": 120,
    "HBP": 6,
    "SF": 4,
    "SH": 2,
    "SB": 20,
    "CS": 5,
    "Spd": 6.2,
    "AVG": 0.278,
    "OBP": 0.355,
    "SLG": 0.481,
    "K%": 0.2,
    "BB%": 0.1,
    "wRC+": 128,
    "TeamNameAbb": "SFG",
}

FG_PITCHER_ROW = {
    "playerid": 990002,
    "xMLBAMID": 880002,
    "PlayerName": "Starting Pitcher",
    "Season": 2025,
    "Age": 30,
    "G": 32,
    "GS": 32,
    "IP": 190.0,
    "TBF": 800,
    "H": 160,
    "HR": 24,
    "BB": 56,
    "IBB": 2,
    "HBP": 8,
    "SO": 200,
    "Pitches": 3040,
    "Start-IP": 190.0,
    "K%": 0.25,
    "TeamNameAbb": "SFG",
}


def processed(row, **overrides):
    """Run a FanGraphs row through the stats loader's key/value processing."""
    raw = dict(row, **overrides)
    command = FgStatsCommand()
    return {command._process_k(k): command._process_v(k, v) for k, v in raw.items()}


class HitterRatesTestCase(SimpleTestCase):
    def setUp(self):
        self.rates = cards.hitter_rates(processed(FG_HITTER_ROW))

    def test_each_rate_is_count_over_plate_appearances(self):
        self.assertAlmostEqual(self.rates["k"], 120 / 600)
        self.assertAlmostEqual(self.rates["bb"], 60 / 600)
        self.assertAlmostEqual(self.rates["hbp"], 6 / 600)
        self.assertAlmostEqual(self.rates["single"], 90 / 600)
        self.assertAlmostEqual(self.rates["double"], 30 / 600)
        self.assertAlmostEqual(self.rates["triple"], 3 / 600)
        self.assertAlmostEqual(self.rates["hr"], 24 / 600)

    def test_bip_out_is_the_remainder(self):
        self.assertAlmostEqual(self.rates["bip_out"], 1 - (120 + 60 + 6 + 90 + 30 + 3 + 24) / 600)

    def test_rates_sum_to_one(self):
        self.assertAlmostEqual(sum(self.rates.values()), 1.0)

    def test_keys_match_engine_hitter_rates(self):
        self.assertEqual(
            list(self.rates.keys()),
            ["k", "bb", "hbp", "single", "double", "triple", "hr", "bip_out"],
        )

    def test_no_plate_appearances_gives_no_rates(self):
        self.assertIsNone(cards.hitter_rates(processed(FG_HITTER_ROW, PA=0)))


class RunnerRatingsTestCase(SimpleTestCase):
    def setUp(self):
        self.stats = processed(FG_HITTER_ROW)

    def test_steal_prior_constants(self):
        self.assertEqual(cards.STEAL_PRIOR_ATTEMPTS, 10)
        self.assertEqual(cards.STEAL_PRIOR_SUCCESS_RATE, 0.72)

    def test_steal_success_is_regressed_toward_the_prior(self):
        self.assertAlmostEqual(cards.steal_success(self.stats), (20 + 10 * 0.72) / (20 + 5 + 10))

    def test_steal_success_with_zero_attempts_is_the_prior(self):
        stats = processed(FG_HITTER_ROW, SB=0, CS=0)
        self.assertAlmostEqual(cards.steal_success(stats), 0.72)

    def test_steal_success_with_a_missing_column_counts_it_as_zero(self):
        stats = processed(FG_HITTER_ROW)
        del stats["cs"]
        self.assertAlmostEqual(cards.steal_success(stats), (20 + 7.2) / 30)

    def test_steal_attempt_rate_is_attempts_per_time_reaching_first(self):
        self.assertAlmostEqual(cards.steal_attempt_rate(self.stats), (20 + 5) / (90 + 60 + 6))

    def test_steal_attempt_rate_without_reaching_first_is_none(self):
        stats = processed(FG_HITTER_ROW, **{"1B": 0, "BB": 0, "HBP": 0})
        self.assertIsNone(cards.steal_attempt_rate(stats))

    def test_speed_is_fangraphs_spd(self):
        self.assertEqual(cards.speed(self.stats), 6.2)

    def test_missing_speed_is_none(self):
        stats = processed(FG_HITTER_ROW)
        del stats["spd"]
        self.assertIsNone(cards.speed(stats))
        self.assertIsNone(cards.speed(processed(FG_HITTER_ROW, Spd=None)))

    def test_no_stats_give_no_ratings(self):
        self.assertIsNone(cards.steal_success(None))
        self.assertIsNone(cards.steal_attempt_rate(None))
        self.assertIsNone(cards.speed(None))


class PitcherRatesTestCase(SimpleTestCase):
    def setUp(self):
        self.rates = cards.pitcher_rates(processed(FG_PITCHER_ROW))

    def test_each_rate_is_count_over_batters_faced(self):
        self.assertAlmostEqual(self.rates["k"], 200 / 800)
        self.assertAlmostEqual(self.rates["bb"], 56 / 800)
        self.assertAlmostEqual(self.rates["hbp"], 8 / 800)
        self.assertAlmostEqual(self.rates["hr"], 24 / 800)

    def test_h_is_non_home_run_hits(self):
        self.assertAlmostEqual(self.rates["h"], (160 - 24) / 800)

    def test_keys_match_engine_pitcher_rates(self):
        self.assertEqual(list(self.rates.keys()), ["k", "bb", "hbp", "hr", "h"])

    def test_no_batters_faced_gives_no_rates(self):
        self.assertIsNone(cards.pitcher_rates(processed(FG_PITCHER_ROW, TBF=0)))


# FanGraphs batted-ball counts (GB, FB, LD) from the same payload; the values are constructed.
HITTER_BATTED_BALLS = {"GB": 180, "FB": 150, "LD": 90}
PITCHER_BATTED_BALLS = {"GB": 260, "FB": 220, "LD": 120}


class BattedBallRatesTestCase(SimpleTestCase):
    def test_hitter_shares_are_counts_over_batted_balls(self):
        rates = cards.batted_ball_rates(processed(FG_HITTER_ROW, **HITTER_BATTED_BALLS))
        self.assertAlmostEqual(rates["gb"], 180 / 420)
        self.assertAlmostEqual(rates["fb"], 150 / 420)
        self.assertAlmostEqual(rates["ld"], 90 / 420)

    def test_pitcher_shares_are_counts_over_batted_balls(self):
        rates = cards.batted_ball_rates(processed(FG_PITCHER_ROW, **PITCHER_BATTED_BALLS))
        self.assertAlmostEqual(rates["gb"], 260 / 600)
        self.assertAlmostEqual(rates["fb"], 220 / 600)
        self.assertAlmostEqual(rates["ld"], 120 / 600)

    def test_shares_sum_to_one_with_engine_keys(self):
        rates = cards.batted_ball_rates(processed(FG_HITTER_ROW, **HITTER_BATTED_BALLS))
        self.assertEqual(list(rates.keys()), ["gb", "fb", "ld"])
        self.assertAlmostEqual(sum(rates.values()), 1.0)

    def test_no_batted_balls_gives_no_rates(self):
        self.assertIsNone(cards.batted_ball_rates(processed(FG_HITTER_ROW)))
        self.assertIsNone(cards.batted_ball_rates(processed(FG_HITTER_ROW, GB=0, FB=0, LD=0)))
        self.assertIsNone(cards.batted_ball_rates(None))


class FatigueProfileTestCase(SimpleTestCase):
    def test_starter_profile_from_card_season(self):
        fatigue = cards.fatigue_profile(processed(FG_PITCHER_ROW))
        self.assertEqual(
            fatigue,
            {
                "role": "starter",
                "age": 30,
                "season_pitches_per_appearance": 95.0,
                "career_pitches_per_appearance": 95.0,
                "season_appearances": 32,
            },
        )

    def test_reliever_when_games_started_are_under_half_of_games(self):
        fatigue = cards.fatigue_profile(processed(FG_PITCHER_ROW, G=60, GS=2, Pitches=960))
        self.assertEqual(fatigue["role"], "reliever")
        self.assertEqual(fatigue["season_pitches_per_appearance"], 16.0)
        self.assertEqual(fatigue["season_appearances"], 60)

    def test_career_pitch_count_is_used_when_present(self):
        fatigue = cards.fatigue_profile(processed(FG_PITCHER_ROW), {"g": 100, "gs": 100, "pitches": 9000})
        self.assertEqual(fatigue["career_pitches_per_appearance"], 90.0)
        self.assertEqual(fatigue["season_pitches_per_appearance"], 95.0)

    def test_career_row_without_pitches_falls_back_to_card_season(self):
        fatigue = cards.fatigue_profile(processed(FG_PITCHER_ROW), {"g": 100, "gs": 100, "ip": 600})
        self.assertEqual(fatigue["career_pitches_per_appearance"], 95.0)


class PositionRatingTestCase(SimpleTestCase):
    def test_constants(self):
        self.assertEqual(cards.FULL_SEASON_INNINGS, 1300)
        self.assertEqual(cards.DEFENSE_REGRESSION_INNINGS, 600)

    def test_per_inning_formula(self):
        self.assertAlmostEqual(cards.position_rating(-5, 650), -5 * 1300 / (650 + 600))

    def test_full_season_plus_ten_prints_six_point_eight(self):
        ratings = cards.defense_ratings({"SS": (1300, 10)})
        self.assertEqual(ratings["SS"], 6.8)

    def test_hundred_innings_plus_three_prints_five_point_six(self):
        ratings = cards.defense_ratings({"CF": (100, 3)})
        self.assertEqual(ratings["CF"], 5.6)
        # Unregressed, the same 100 innings would scale to a +39 full season.
        self.assertAlmostEqual(3 * cards.FULL_SEASON_INNINGS / 100, 39)

    def test_shortstop_minus_twelve_slots_along_the_spectrum(self):
        # -12 runs over 700 innings regresses to exactly -12.0.
        ratings = cards.defense_ratings({"SS": (700, -12)})
        self.assertEqual(ratings["SS"], -12.0)
        self.assertEqual(ratings["2B"], 0.0)
        self.assertEqual(ratings["3B"], 3.0)
        self.assertEqual(ratings["CF"], 1.0)
        self.assertEqual(ratings["RF"], 4.0)
        self.assertEqual(ratings["LF"], 5.0)
        self.assertEqual(ratings["1B"], 6.0)

    def test_multi_position_player_regresses_toward_the_spectrum(self):
        fielding = {"SS": (900, -3), "2B": (300 + 1 / 3, 2), "3B": (100 + 2 / 3, 0)}
        ratings = cards.defense_ratings(fielding)
        primary = -3 * 1300 / 1500
        self.assertEqual(ratings["SS"], round(primary, 1))
        spectrum_2b = primary + 12
        expected_2b = (2 * 1300 + 600 * spectrum_2b) / (300 + 1 / 3 + 600)
        self.assertEqual(ratings["2B"], round(expected_2b, 1))
        spectrum_3b = primary + 15
        expected_3b = (0 * 1300 + 600 * spectrum_3b) / (100 + 2 / 3 + 600)
        self.assertEqual(ratings["3B"], round(expected_3b, 1))
        # A position he never played is the spectrum value.
        self.assertEqual(ratings["CF"], round(primary + 13, 1))

    def test_primary_position_is_most_innings(self):
        self.assertEqual(cards.primary_position({"SS": (900, -3), "2B": (300, 2)}), "SS")
        self.assertEqual(cards.primary_position({"SS": (200, -3), "2B": (300, 2)}), "2B")


class CatcherDefenseTestCase(SimpleTestCase):
    def test_catcher_rating_uses_per_inning_formula_at_catcher(self):
        ratings = cards.defense_ratings({"C": (1000, 8)})
        self.assertEqual(ratings["C"], round(8 * 1300 / 1600, 1))

    def test_primary_catcher_elsewhere_is_a_zero_first_baseman(self):
        ratings = cards.defense_ratings({"C": (1000, 8)})
        self.assertEqual(ratings["1B"], 0.0)
        self.assertEqual(ratings["LF"], -1.0)
        self.assertEqual(ratings["2B"], -6.0)
        self.assertEqual(ratings["SS"], -18.0)

    def test_primary_catcher_at_a_position_he_played_regresses_toward_zero_first_base(self):
        ratings = cards.defense_ratings({"C": (900, 5), "1B": (100, 2)})
        self.assertEqual(ratings["C"], round(5 * 1300 / 1500, 1))
        self.assertEqual(ratings["1B"], round((2 * 1300 + 600 * 0) / 700, 1))

    def test_player_without_catcher_innings_cannot_be_slotted_at_catcher(self):
        ratings = cards.defense_ratings({"SS": (700, -12)})
        self.assertIsNone(ratings["C"])

    def test_catcher_is_not_slotted_on_the_spectrum(self):
        ratings = cards.defense_ratings({"SS": (1300, 10), "C": (5, 0)})
        self.assertEqual(ratings["C"], 0.0)
        self.assertEqual(ratings["SS"], 6.8)


class NoFieldingRowTestCase(SimpleTestCase):
    def test_no_fielding_row_is_zero_at_first_base(self):
        ratings = cards.defense_ratings({})
        self.assertEqual(ratings["1B"], 0.0)
        self.assertEqual(ratings["LF"], -1.0)
        self.assertEqual(ratings["SS"], -18.0)
        self.assertIsNone(ratings["C"])

    def test_no_fielding_row_has_no_primary_position(self):
        self.assertIsNone(cards.primary_position({}))

    def test_pitcher_and_dh_rows_are_not_fielding_positions(self):
        fielding = cards.fielding_from_stats({"P": {"inn": 190.0, "frp": 1}, "DH": {"inn": 0, "frp": 0}})
        self.assertEqual(fielding, {})


class SimDefenseTestCase(SimpleTestCase):
    def test_sim_value_is_card_runs_over_ten(self):
        self.assertAlmostEqual(cards.sim_defense(-12.0), -1.2)
        self.assertAlmostEqual(cards.sim_defense(6.8), 0.68)

    def test_fangraphs_innings_thirds(self):
        self.assertAlmostEqual(cards.fg_innings(300.1), 300 + 1 / 3)
        self.assertAlmostEqual(cards.fg_innings(100.2), 100 + 2 / 3)
        self.assertAlmostEqual(cards.fg_innings(900.0), 900.0)
        self.assertAlmostEqual(cards.fg_innings(None), 0.0)

    def test_fielding_from_stored_rows(self):
        fielding = cards.fielding_from_stats({"2B": {"inn": 300.1, "frp": 2, "defense": 2.5}})
        self.assertEqual(list(fielding.keys()), ["2B"])
        innings, runs = fielding["2B"]
        self.assertAlmostEqual(innings, 300 + 1 / 3)
        self.assertEqual(runs, 2)


class LoadFieldingTestCase(TestCase):
    def setUp(self):
        self.fielder = models.Player.objects.create(name="Utility Infielder", position="IF", fg_id="990001")
        self.pitcher = models.Player.objects.create(name="Starting Pitcher", position="P", mlbam_id="880002")
        self.fielder_pss = models.PlayerStatSeason.objects.create(
            player=self.fielder, season=2025, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
        )
        self.pitcher_pss = models.PlayerStatSeason.objects.create(
            player=self.pitcher, season=2025, classification="1-mlb", pitch_stats=processed(FG_PITCHER_ROW)
        )

    def run_load(self, *args):
        out = StringIO()
        call_command("live_update_fielding_from_fg_fielding", "--season", "2025", "--file", FIXTURE_FLD, *args, stdout=out)
        return out.getvalue()

    def test_stores_innings_and_fielding_runs_per_position(self):
        self.run_load()
        self.fielder_pss.refresh_from_db()
        stats = self.fielder_pss.fielding_stats
        self.assertEqual(sorted(stats.keys()), ["2B", "3B", "SS"])
        self.assertEqual(stats["2B"]["inn"], 300.1)
        self.assertEqual(stats["2B"]["frp"], 2)
        self.assertEqual(stats["2B"]["defense"], 2.5)
        self.assertEqual(stats["SS"]["frp"], -3)

    def test_keys_use_the_stats_loader_processing(self):
        self.run_load()
        self.fielder_pss.refresh_from_db()
        self.assertIn("uzr_150", self.fielder_pss.fielding_stats["SS"])
        self.assertIn("mlb_org", self.fielder_pss.fielding_stats["SS"])

    def test_matches_on_mlbam_id_when_fg_id_missing(self):
        self.run_load()
        self.pitcher_pss.refresh_from_db()
        self.assertEqual(list(self.pitcher_pss.fielding_stats.keys()), ["P"])

    def test_reload_replaces_fielding(self):
        self.fielder_pss.fielding_stats = {"LF": {"inn": 50.0, "frp": 1}}
        self.fielder_pss.save()
        self.run_load()
        self.fielder_pss.refresh_from_db()
        self.assertNotIn("LF", self.fielder_pss.fielding_stats)

    def test_does_not_create_stat_seasons(self):
        models.Player.objects.create(name="Unmatched", position="IF", fg_id="555")
        before = models.PlayerStatSeason.objects.count()
        output = self.run_load()
        self.assertEqual(models.PlayerStatSeason.objects.count(), before)
        self.assertIn("Updated fielding for 2 players", output)

    def test_dry_run_writes_nothing(self):
        output = self.run_load("--dry-run")
        self.fielder_pss.refresh_from_db()
        self.assertIsNone(self.fielder_pss.fielding_stats)
        self.assertIn("DRY RUN", output)

    def test_warns_when_a_player_repeats_a_position(self):
        with open(FIXTURE_FLD) as f:
            rows = json.load(f)
        path = os.path.join(os.path.dirname(FIXTURE_FLD), "_dup_fld.json")
        try:
            with open(path, "w") as f:
                json.dump(rows + [rows[0]], f)
            out = StringIO()
            call_command("live_update_fielding_from_fg_fielding", "--season", "2025", "--file", path, stdout=out)
        finally:
            os.remove(path)
        self.assertIn("more than one SS row", out.getvalue())

    def _load_rows(self, rows, season, *args):
        out = StringIO()
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(rows, handle)
            path = handle.name
        try:
            call_command(
                "live_update_fielding_from_fg_fielding",
                "--season", str(season), "--file", path, *args, stdout=out,
            )
        finally:
            os.remove(path)
        return out.getvalue()

    def test_a_minor_league_fg_id_matches_by_name_and_gets_a_catcher_rating(self):
        catcher = models.Player.objects.create(name="Shea Langeliers", position="C", fg_id="sa3010329")
        pss = models.PlayerStatSeason.objects.create(
            player=catcher, season=2026, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
        )
        row = {
            "playerid": 25816,
            "xMLBAMID": 669127.0,
            "PlayerName": "Shea Langeliers",
            "Pos": "C",
            "Inn": 634.0,
            "FRP": -5.0,
        }
        self._load_rows([row], 2026, "--dry-run")
        catcher.refresh_from_db()
        self.assertEqual(catcher.fg_id, "sa3010329")

        self._load_rows([row], 2026)
        pss.refresh_from_db()
        catcher.refresh_from_db()
        self.assertEqual(pss.fielding_stats["C"]["inn"], 634.0)
        self.assertEqual(pss.fielding_stats["C"]["frp"], -5.0)
        self.assertEqual(catcher.fg_id, "25816")
        self.assertEqual(catcher.mlbam_id, "669127")

        call_command("generate_cards", "--season", "2026", stdout=StringIO())
        card = models.Card.objects.get(player=catcher, season=2026)
        self.assertEqual(card.primary_position, "C")
        self.assertAlmostEqual(card.defense["C"], -5.3)

    def test_a_float_mlbam_id_matches_the_stored_id(self):
        catcher = models.Player.objects.create(name="Other Catcher", position="C", mlbam_id="669127")
        pss = models.PlayerStatSeason.objects.create(
            player=catcher, season=2026, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
        )
        self._load_rows([{
            "playerid": 25816,
            "xMLBAMID": 669127.0,
            "PlayerName": "Shea Langeliers",
            "Pos": "C",
            "Inn": 634.0,
            "FRP": -5.0,
        }], 2026)
        pss.refresh_from_db()
        catcher.refresh_from_db()
        self.assertIn("C", pss.fielding_stats)
        self.assertEqual(catcher.fg_id, "25816")

    def test_the_same_name_on_a_stale_id_is_updated_with_the_id_match(self):
        shell = models.Player.objects.create(name="Shea Langeliers", position="C", fg_id="25816")
        real = models.Player.objects.create(name="Shea Langeliers", position="C", fg_id="sa3010329")
        shell_pss = models.PlayerStatSeason.objects.create(
            player=shell, season=2026, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
        )
        real_pss = models.PlayerStatSeason.objects.create(
            player=real, season=2026, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
        )
        self._load_rows([{
            "playerid": 25816,
            "PlayerName": "Shea Langeliers",
            "Pos": "C",
            "Inn": 634.0,
            "FRP": -5.0,
        }], 2026)
        shell_pss.refresh_from_db()
        real_pss.refresh_from_db()
        real.refresh_from_db()
        self.assertIn("C", shell_pss.fielding_stats)
        self.assertIn("C", real_pss.fielding_stats)
        self.assertEqual(real.fg_id, "25816")

    def test_two_stale_ids_with_the_same_name_are_not_guessed(self):
        players = [
            models.Player.objects.create(name="Shea Langeliers", position="C", fg_id=fg_id)
            for fg_id in ("sa3010329", "sa9999999")
        ]
        for player in players:
            models.PlayerStatSeason.objects.create(
                player=player, season=2026, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
            )
        self._load_rows([{
            "playerid": 25816,
            "PlayerName": "Shea Langeliers",
            "Pos": "C",
            "Inn": 634.0,
            "FRP": -5.0,
        }], 2026)
        for player in players:
            player.refresh_from_db()
            pss = player.playerstatseason_set.get(season=2026)
            self.assertIsNone(pss.fielding_stats)
            self.assertNotEqual(player.fg_id, "25816")


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class GenerateCardsTestCase(TestCase):
    def setUp(self):
        self.hitter = models.Player.objects.create(name="Utility Infielder", position="IF", fg_id="990001")
        self.pitcher = models.Player.objects.create(name="Starting Pitcher", position="P", fg_id="990002")
        self.hitter_pss = models.PlayerStatSeason.objects.create(
            player=self.hitter, season=2025, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
        )
        models.PlayerStatSeason.objects.create(
            player=self.pitcher, season=2025, classification="1-mlb", pitch_stats=processed(FG_PITCHER_ROW)
        )
        call_command("live_update_fielding_from_fg_fielding", "--season", "2025", "--file", FIXTURE_FLD, stdout=StringIO())

    def generate(self, *args):
        out = StringIO()
        call_command("generate_cards", *args, stdout=out)
        return out.getvalue()

    def test_hitter_card(self):
        self.generate("--season", "2025")
        card = models.Card.objects.get(player=self.hitter, season=2025)
        self.assertEqual(card.plate_appearances, 600)
        self.assertEqual(card.wrc_plus, 128)
        self.assertAlmostEqual(card.hitter_rates["k"], 0.2)
        self.assertAlmostEqual(sum(card.hitter_rates.values()), 1.0)
        self.assertEqual(card.primary_position, "SS")
        self.assertEqual(card.defense["SS"], -2.6)
        self.assertIsNone(card.defense["C"])
        self.assertIsNone(card.pitcher_rates)

    def test_hitter_card_running(self):
        self.generate("--season", "2025")
        card = models.Card.objects.get(player=self.hitter, season=2025)
        self.assertAlmostEqual(card.steal_success, 27.2 / 35)
        self.assertAlmostEqual(card.steal_attempt_rate, 25 / 156)
        self.assertEqual(card.spd, 6.2)

    def test_pitcher_card_has_no_running(self):
        self.generate("--season", "2025")
        card = models.Card.objects.get(player=self.pitcher, season=2025)
        self.assertIsNone(card.steal_success)
        self.assertIsNone(card.steal_attempt_rate)
        self.assertIsNone(card.spd)

    def test_runner_rating_shape(self):
        self.generate("--season", "2025")
        card = models.Card.objects.get(player=self.hitter, season=2025)
        self.assertEqual(
            card.runner_rating("away-9"),
            {"id": "away-9", "steal_success": card.steal_success, "spd": 6.2},
        )

    def test_reports_league_speed(self):
        output = self.generate("--season", "2025")
        self.assertIn("League Spd for 2025: 6.20", output)

    def test_sim_defense_rating_shape(self):
        self.generate("--season", "2025")
        card = models.Card.objects.get(player=self.hitter, season=2025)
        self.assertEqual(card.sim_defense_rating("SS"), {"rating": cards.sim_defense(-2.6), "measured_at": "SS"})
        self.assertIsNone(card.sim_defense_rating("C"))

    def test_pitcher_card(self):
        self.generate("--season", "2025")
        card = models.Card.objects.get(player=self.pitcher, season=2025)
        self.assertEqual(card.batters_faced, 800)
        self.assertAlmostEqual(card.pitcher_rates["h"], 136 / 800)
        self.assertEqual(card.fatigue["role"], "starter")
        self.assertIsNone(card.hitter_rates)

    def test_cards_store_batted_ball_rates(self):
        self.hitter_pss.hit_stats = processed(FG_HITTER_ROW, **HITTER_BATTED_BALLS)
        self.hitter_pss.save()
        pitcher_pss = models.PlayerStatSeason.objects.get(player=self.pitcher, season=2025)
        pitcher_pss.pitch_stats = processed(FG_PITCHER_ROW, **PITCHER_BATTED_BALLS)
        pitcher_pss.save()
        self.generate("--season", "2025")

        hitter = models.Card.objects.get(player=self.hitter, season=2025)
        self.assertAlmostEqual(hitter.hitter_batted_balls["gb"], 180 / 420)
        self.assertIsNone(hitter.pitcher_batted_balls)

        pitcher = models.Card.objects.get(player=self.pitcher, season=2025)
        self.assertAlmostEqual(pitcher.pitcher_batted_balls["ld"], 120 / 600)
        self.assertIsNone(pitcher.hitter_batted_balls)

    def test_a_card_without_batted_ball_counts_leaves_them_empty(self):
        self.generate("--season", "2025")
        card = models.Card.objects.get(player=self.hitter, season=2025)
        self.assertIsNone(card.hitter_batted_balls)

    def test_default_season_is_previous_mlb_season(self):
        self.generate()
        self.assertEqual(models.Card.objects.filter(season=2025).count(), 2)

    def test_regenerating_replaces_the_card(self):
        self.generate("--season", "2025")
        self.hitter_pss.hit_stats = processed(FG_HITTER_ROW, SO=60)
        self.hitter_pss.save()
        self.generate("--season", "2025")
        cards_for_player = models.Card.objects.filter(player=self.hitter, season=2025)
        self.assertEqual(cards_for_player.count(), 1)
        self.assertAlmostEqual(cards_for_player.get().hitter_rates["k"], 0.1)

    def test_player_without_mlb_row_gets_no_card(self):
        prospect = models.Player.objects.create(name="Minor Leaguer", position="IF")
        models.PlayerStatSeason.objects.create(
            player=prospect, season=2025, classification="2-milb", hit_stats=processed(FG_HITTER_ROW)
        )
        later = models.Player.objects.create(name="Next Year Debut", position="IF")
        models.PlayerStatSeason.objects.create(
            player=later, season=2026, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
        )
        self.generate("--season", "2025")
        self.assertFalse(models.Card.objects.filter(player=prospect).exists())
        self.assertFalse(models.Card.objects.filter(player=later).exists())

    def test_dry_run_saves_nothing(self):
        output = self.generate("--season", "2025", "--dry-run")
        self.assertEqual(models.Card.objects.count(), 0)
        self.assertIn("DRY RUN", output)
        self.assertIn("2 cards", output)

    def test_progress_count(self):
        output = self.generate("--season", "2025")
        self.assertIn("[1/2]", output)
        self.assertIn("[2/2]", output)


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class LeagueSpeedTestCase(TestCase):
    def card(self, name, season, pa, spd):
        player = models.Player.objects.create(name=name, position="IF")
        return models.Card.objects.create(player=player, season=season, plate_appearances=pa, spd=spd)

    def test_league_speed_is_weighted_by_plate_appearances(self):
        self.card("Burner", 2025, 600, 8.0)
        self.card("Catcher", 2025, 200, 2.0)
        self.assertAlmostEqual(models.Card.league_spd(2025), (600 * 8.0 + 200 * 2.0) / 800)

    def test_cards_without_speed_or_plate_appearances_do_not_count(self):
        self.card("Burner", 2025, 600, 8.0)
        self.card("Unknown", 2025, 400, None)
        self.card("Pitcher", 2025, None, None)
        self.card("Zero", 2025, 0, 3.0)
        self.assertAlmostEqual(models.Card.league_spd(2025), 8.0)

    def test_only_the_card_season_counts(self):
        self.card("Burner", 2025, 600, 8.0)
        self.card("Other Year", 2024, 600, 2.0)
        self.assertAlmostEqual(models.Card.league_spd(2025), 8.0)

    def test_a_season_without_speed_has_no_league_speed(self):
        self.assertIsNone(models.Card.league_spd(2025))


@override_settings(CURRENT_SEASON=2026, CURRENT_SEASON_TYPE="midseason")
class CardDisplayTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="mgr", password="secret")
        owner = models.Owner.objects.create(user=self.user, name="Manager")
        models.Team.objects.create(city="Test City", abbreviation="TST", nickname="Testers", owner_obj=owner)
        self.client.login(username="mgr", password="secret")
        self.hitter = models.Player.objects.create(name="Utility Infielder", position="IF", fg_id="990001")
        self.pitcher = models.Player.objects.create(name="Starting Pitcher", position="P", fg_id="990002")
        models.PlayerStatSeason.objects.create(
            player=self.hitter, season=2025, classification="1-mlb", hit_stats=processed(FG_HITTER_ROW)
        )
        models.PlayerStatSeason.objects.create(
            player=self.pitcher, season=2025, classification="1-mlb", pitch_stats=processed(FG_PITCHER_ROW)
        )
        call_command("live_update_fielding_from_fg_fielding", "--season", "2025", "--file", FIXTURE_FLD, stdout=StringIO())
        call_command("generate_cards", "--season", "2025", stdout=StringIO())

    def test_hitter_card_line(self):
        card = models.Card.objects.get(player=self.hitter)
        line = card.hitter_line()
        self.assertAlmostEqual(line["avg"], 0.245 / 0.89)
        self.assertAlmostEqual(line["obp"], 0.355)
        self.assertAlmostEqual(line["slg"], 0.425 / 0.89)
        self.assertAlmostEqual(line["k_pct"], 0.2)
        self.assertAlmostEqual(line["bb_pct"], 0.1)
        self.assertAlmostEqual(line["hr_pct"], 0.04)

    def test_pitcher_card_line(self):
        card = models.Card.objects.get(player=self.pitcher)
        line = card.pitcher_line()
        self.assertAlmostEqual(line["avg"], 0.2 / 0.92)
        self.assertAlmostEqual(line["obp"], 0.28)
        self.assertAlmostEqual(line["k_pct"], 0.25)
        self.assertAlmostEqual(line["bb_pct"], 0.07)
        self.assertAlmostEqual(line["hr_pct"], 0.03)

    def test_player_page_shows_hitter_card(self):
        response = self.client.get(f"/players/{self.hitter.id}/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("2025 Card", content)
        self.assertIn("600 PA", content)
        self.assertIn(".275", content)
        self.assertIn(".355", content)
        self.assertIn(".478", content)
        self.assertIn("SS -2.6", content)
        self.assertIn("2B", content)
        self.assertIn("Steal success 77.7%", content)
        self.assertIn("Attempts 16.0% of times on first", content)
        self.assertIn("Spd 6.2", content)

    def test_player_page_shows_a_card_generated_without_running(self):
        models.Card.objects.filter(player=self.hitter).update(steal_success=None, steal_attempt_rate=None, spd=None)
        response = self.client.get(f"/players/{self.hitter.id}/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Steal success -", content)
        self.assertIn("Attempts - of times on first", content)
        self.assertIn("Spd -", content)

    def test_player_page_shows_pitcher_card(self):
        response = self.client.get(f"/players/{self.pitcher.id}/")
        content = response.content.decode()
        self.assertIn("2025 Card", content)
        self.assertIn("800 BF", content)
        self.assertIn(".217", content)
        self.assertIn(".280", content)
        self.assertNotIn("Steal success", content)

    def test_player_without_card_shows_no_card(self):
        other = models.Player.objects.create(name="No Card Guy", position="IF")
        response = self.client.get(f"/players/{other.id}/")
        self.assertNotIn("2025 Card", response.content.decode())
