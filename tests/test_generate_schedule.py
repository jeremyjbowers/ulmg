# ABOUTME: Integration tests for the generate_schedule management command.
# ABOUTME: Covers saved slots, series and games, seeding, dry runs, regeneration and refusal once play starts.

from collections import Counter
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ulmg import models, schedule
from tests.schedule_fixtures import create_league_teams


def run(*args):
    out = StringIO()
    call_command("generate_schedule", *args, stdout=out)
    return out.getvalue()


def saved_schedule(season):
    return [
        (g.day, g.series.home_team.abbreviation, g.series.road_team.abbreviation)
        for g in models.ScheduleGame.objects.filter(series__slot__season=season)
        .select_related("series__home_team", "series__road_team")
        .order_by("day", "series__home_team__abbreviation")
    ]


class GenerateScheduleCommandTestCase(TestCase):
    def setUp(self):
        self.teams = create_league_teams()

    def test_saves_the_whole_season(self):
        output = run("--season", "2027", "--seed", "11")
        self.assertIn("Saved 46 slots, 368 series and 1296 games for 2027", output)
        self.assertEqual(models.ScheduleSlot.objects.filter(season=2027).count(), 46)
        self.assertEqual(models.ScheduleSeries.objects.filter(slot__season=2027).count(), 368)
        games = models.ScheduleGame.objects.filter(series__slot__season=2027)
        self.assertEqual(games.count(), 1296)
        self.assertFalse(games.filter(home_score__isnull=False).exists())

    def test_every_team_has_games_one_through_162(self):
        run("--season", "2027", "--seed", "11")
        for team in self.teams:
            games = schedule.team_games(team, 2027)
            self.assertEqual([g.day for g in games], list(range(1, 163)))
            home = [g for g in games if g.series.home_team_id == team.id]
            road = [g for g in games if g.series.road_team_id == team.id]
            self.assertEqual(len(home), 81)
            self.assertEqual(len(road), 81)

    def test_saved_schedule_matches_the_seeded_plan(self):
        run("--season", "2027", "--seed", "11")
        plan = schedule.build_season_plan(models.Team.objects.all(), 11)
        expected = sorted(
            (day, s.home.abbreviation, s.road.abbreviation)
            for slot in plan
            for s in slot.series
            for day in slot.days
        )
        self.assertEqual(saved_schedule(2027), expected)
        slot = models.ScheduleSlot.objects.get(season=2027, number=1)
        self.assertEqual(
            (slot.half, slot.slot_type, slot.length, slot.first_day),
            (1, "other_conference", 4, 1),
        )

    def test_same_seed_saves_the_same_schedule(self):
        run("--season", "2027", "--seed", "5")
        first = saved_schedule(2027)
        run("--season", "2027", "--seed", "5")
        self.assertEqual(saved_schedule(2027), first)
        run("--season", "2027", "--seed", "6")
        self.assertNotEqual(saved_schedule(2027), first)

    def test_regenerating_replaces_the_season(self):
        run("--season", "2027", "--seed", "5")
        output = run("--season", "2027", "--seed", "6")
        self.assertIn("Replacing the existing 2027 schedule", output)
        self.assertEqual(models.ScheduleSlot.objects.filter(season=2027).count(), 46)
        self.assertEqual(models.ScheduleGame.objects.filter(series__slot__season=2027).count(), 1296)

    def test_other_seasons_are_left_alone(self):
        run("--season", "2026", "--seed", "1")
        run("--season", "2027", "--seed", "2")
        self.assertEqual(models.ScheduleSlot.objects.filter(season=2026).count(), 46)
        self.assertEqual(models.ScheduleSlot.objects.filter(season=2027).count(), 46)

    def test_seed_is_reported_when_drawn(self):
        output = run("--season", "2027")
        self.assertRegex(output, r"Seed: \d+")

    def test_progress_output_names_each_slot(self):
        output = run("--season", "2027", "--seed", "3")
        self.assertIn("Slot 1/46: half 1, other conference, 4 games, days 1-4", output)
        self.assertIn("Slot 23/46: half 1, division, 1 game, day 81", output)
        self.assertIn("Slot 46/46:", output)

    def test_dry_run_writes_nothing(self):
        output = run("--season", "2027", "--seed", "3", "--dry-run")
        self.assertIn("Dry run: nothing saved", output)
        self.assertIn("Slot 46/46:", output)
        self.assertEqual(models.ScheduleSlot.objects.count(), 0)

    def test_refuses_after_a_game_is_played(self):
        run("--season", "2027", "--seed", "3")
        before = saved_schedule(2027)
        game = models.ScheduleGame.objects.filter(series__slot__season=2027).order_by("day").first()
        game.home_score = 4
        game.road_score = 2
        game.save()
        with self.assertRaisesMessage(CommandError, "2027 has played games"):
            run("--season", "2027", "--seed", "4")
        with self.assertRaisesMessage(CommandError, "2027 has played games"):
            run("--season", "2027", "--seed", "4", "--dry-run")
        self.assertEqual(saved_schedule(2027), before)

    def test_refuses_a_league_that_is_not_four_divisions_of_four(self):
        self.teams[0].division = None
        self.teams[0].save()
        with self.assertRaises(CommandError):
            run("--season", "2027", "--seed", "3")
        self.assertEqual(models.ScheduleSlot.objects.count(), 0)


class NextRoadGameTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teams = create_league_teams()
        run("--season", "2027", "--seed", "9")

    def test_next_unplayed_road_game_in_day_order(self):
        team = self.teams[0]
        road = [g for g in schedule.team_games(team, 2027) if g.series.road_team_id == team.id]
        self.assertEqual(schedule.next_unplayed_road_game(team, 2027), road[0])
        road[0].home_score = 1
        road[0].road_score = 0
        road[0].save()
        self.assertEqual(schedule.next_unplayed_road_game(team, 2027), road[1])

    def test_no_road_game_when_all_are_played(self):
        team = self.teams[0]
        models.ScheduleGame.objects.filter(series__road_team=team).update(home_score=1, road_score=0)
        self.assertIsNone(schedule.next_unplayed_road_game(team, 2027))

    def test_game_is_played_once_it_has_a_result(self):
        game = models.ScheduleGame.objects.first()
        self.assertFalse(game.is_played)
        game.home_score = 3
        game.road_score = 5
        self.assertTrue(game.is_played)
        counts = Counter(g.day for g in models.ScheduleGame.objects.filter(series__slot__season=2027))
        self.assertEqual(set(counts.values()), {8})
