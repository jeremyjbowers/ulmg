# ABOUTME: Tests the run-environment report: the league's runs, hits and scoring spread from final games against the engine's.
# ABOUTME: Also checks the public run-environment page and the link to it from the standings.

import json
import math

from django.test import TestCase, override_settings

from tests.schedule_fixtures import create_league_teams
from tests.test_season_record_pages import final_game
from ulmg import models, run_environment, utils

SEASON = 2026
ULMG = models.PlayerStatSeason.ULMG


class ExpectedTestCase(TestCase):
    def test_expected_reads_the_engine_fixture(self):
        with open(run_environment.FIXTURE) as handle:
            fixture = json.load(handle)
        expected = run_environment.expected()
        self.assertEqual(expected["runs_per_team"], fixture["runs_per_team"])
        self.assertEqual(len(expected["team_runs_shares"]), len(run_environment.BUCKET_LABELS))
        self.assertAlmostEqual(sum(expected["team_runs_shares"]), 1.0, places=2)


@override_settings(CURRENT_SEASON=SEASON, CURRENT_SEASON_TYPE="midseason")
class ReportTestCase(TestCase):
    def setUp(self):
        self.teams = {t.abbreviation: t for t in create_league_teams()}
        atl, car = self.teams["ATL"], self.teams["CAR"]
        slot = models.ScheduleSlot.objects.create(
            season=SEASON, half=1, number=1, slot_type=models.ScheduleSlot.DIVISION, length=4, first_day=1
        )
        # Team-game runs: 7, 6 / 2, 12 / 0, 3. One game has both teams at six or more.
        final_game(slot, atl, car, 1, 7, 6)
        final_game(slot, atl, car, 2, 2, 12)
        final_game(slot, atl, car, 3, 0, 3)
        series = models.ScheduleSeries.objects.get(slot=slot)
        # Scored but never logged to a final: not counted, as in the standings.
        models.ScheduleGame.objects.create(series=series, day=4, home_score=20, road_score=20)
        models.TeamSeasonRecord.objects.create(
            team=atl, season=SEASON, wins=1, losses=2, runs_scored=9, runs_allowed=21
        )
        models.TeamSeasonRecord.objects.create(
            team=car, season=SEASON, wins=2, losses=1, runs_scored=21, runs_allowed=9
        )
        hitter = models.Player.objects.create(name="Hitter", position="OF", team=atl)
        other = models.Player.objects.create(name="Other", position="OF", team=car)
        models.PlayerStatSeason.objects.create(
            player=hitter, season=SEASON, classification=ULMG,
            hit_stats={"pa": 120, "h": 30, "hr": 6, "bb": 12, "so": 24},
        )
        models.PlayerStatSeason.objects.create(
            player=other, season=SEASON, classification=ULMG,
            hit_stats={"pa": 100, "h": 24, "hr": 3, "bb": 6, "so": 30},
        )
        # Real MLB lines are never counted.
        models.PlayerStatSeason.objects.create(
            player=other, season=SEASON, classification="1-mlb", hit_stats={"pa": 600, "h": 180}
        )
        self.report = run_environment.report(SEASON)

    def metric(self, key):
        return {m.key: m for m in self.report.metrics}[key]

    def test_it_counts_only_final_games(self):
        self.assertEqual(self.report.games, 3)
        self.assertEqual(self.report.team_games, 6)

    def test_runs_per_team_with_a_two_standard_error_band(self):
        runs = self.metric("runs")
        self.assertAlmostEqual(runs.actual, 30 / 6)
        expected = run_environment.expected()
        self.assertEqual(runs.expected, expected["runs_per_team"])
        margin = 2 * expected["runs_sd"] / math.sqrt(6)
        self.assertAlmostEqual(runs.low, expected["runs_per_team"] - margin)
        self.assertAlmostEqual(runs.high, expected["runs_per_team"] + margin)
        self.assertEqual(runs.verdict, run_environment.WITHIN)

    def test_counting_stats_come_from_the_ulmg_lines(self):
        self.assertAlmostEqual(self.metric("hits").actual, 54 / 6)
        self.assertAlmostEqual(self.metric("home_runs").actual, 9 / 6)
        self.assertAlmostEqual(self.metric("walks").actual, 18 / 6)
        self.assertAlmostEqual(self.metric("strikeouts").actual, 54 / 6)

    def test_six_run_shares(self):
        self.assertAlmostEqual(self.metric("team_six_plus").actual, 3 / 6)
        self.assertAlmostEqual(self.metric("both_six_plus").actual, 1 / 3)

    def test_a_metric_outside_its_band_says_which_way(self):
        metric = run_environment.Metric("x", "X", actual=9.0, expected=4.0, margin=1.0)
        self.assertEqual(metric.verdict, run_environment.ABOVE)
        metric = run_environment.Metric("x", "X", actual=1.0, expected=4.0, margin=1.0)
        self.assertEqual(metric.verdict, run_environment.BELOW)

    def test_the_distribution_buckets_team_games(self):
        rows = {row.label: row for row in self.report.distribution}
        self.assertEqual(list(rows), run_environment.BUCKET_LABELS)
        self.assertEqual(rows["0"].count, 1)
        self.assertEqual(rows["6"].count, 1)
        self.assertEqual(rows["11+"].count, 1)
        self.assertAlmostEqual(rows["11+"].actual, 1 / 6)
        shares = run_environment.expected()["team_runs_shares"]
        self.assertEqual(rows["0"].expected, shares[0])
        self.assertAlmostEqual(rows["0"].expected_count, shares[0] * 6)

    def test_team_rows_give_runs_scored_and_allowed_per_game(self):
        rows = {row.team.abbreviation: row for row in self.report.teams}
        self.assertEqual(rows["ATL"].games, 3)
        self.assertAlmostEqual(rows["ATL"].scored, 3.0)
        self.assertAlmostEqual(rows["ATL"].allowed, 7.0)
        self.assertNotIn("DET", rows)

    def test_the_page_is_public(self):
        response = self.client.get(f"/run-environment/{SEASON}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"{SEASON} run environment")
        self.assertContains(response, "5.00")
        self.assertContains(response, "4.47")

    def test_the_page_without_a_year_goes_to_the_league_season(self):
        response = self.client.get("/run-environment/")
        self.assertRedirects(
            response, f"/run-environment/{utils.league_season()}/", fetch_redirect_response=False
        )

    def test_the_standings_link_to_it(self):
        response = self.client.get(f"/standings/{SEASON}/")
        self.assertContains(response, f'href="/run-environment/{SEASON}/"')


@override_settings(CURRENT_SEASON=SEASON, CURRENT_SEASON_TYPE="midseason")
class EmptySeasonTestCase(TestCase):
    def test_a_season_with_no_final_games(self):
        report = run_environment.report(SEASON)
        self.assertEqual(report.games, 0)
        self.assertEqual(report.metrics, [])
        response = self.client.get(f"/run-environment/{SEASON}/")
        self.assertContains(response, "No final games yet")
