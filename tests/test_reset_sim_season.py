# ABOUTME: End-to-end tests for resetting a season's sim data: the reset_sim_season command and its admin page.
# ABOUTME: Covers dry runs, confirmation, --include-schedule then generate_schedule, and superuser-only access.

from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse

from ulmg import models, sim_data
from tests.schedule_fixtures import create_league_teams
from tests.sim_fixtures import create_kept_rows, create_played_season
from tests.usage_fixtures import create_pitcher, create_teams

SEASON = 2026
OTHER_SEASON = 2027


def run(*args):
    out = StringIO()
    call_command("reset_sim_season", *args, stdout=out)
    return out.getvalue()


def sim_counts():
    return {entry.model: entry.model.objects.count() for entry in sim_data.SIM_MODELS}


def kept_counts():
    return {model: model.objects.count() for model in sim_data.KEPT_MODELS}


def played_games(season):
    return models.ScheduleGame.objects.filter(
        series__slot__season=season, home_score__isnull=False, road_score__isnull=False
    ).count()


class ResetSimSeasonCommandTestCase(TestCase):
    def setUp(self):
        self.home, self.road = create_teams()
        self.pitcher = create_pitcher("Sim Pitcher", team=self.home, ip=180, gs=30)
        create_played_season(SEASON, self.home, self.road, self.pitcher)
        create_played_season(OTHER_SEASON, self.home, self.road, self.pitcher)
        create_kept_rows(SEASON, self.home, self.pitcher)

    def test_dry_run_changes_nothing(self):
        sim_before, kept_before = sim_counts(), kept_counts()
        output = run("--season", str(SEASON))
        self.assertIn("Dry run", output)
        self.assertIn("UsageAppearance: would delete 3", output)
        self.assertIn("UsageCounter: would delete 1", output)
        self.assertIn("PlayerStatSeason: would delete 1", output)
        self.assertIn("ScheduleGame: would clear home_score, road_score, opened_at, opening_sheet on 3", output)
        self.assertIn("ScheduleSlot: keep 1", output)
        self.assertIn("HalfPlan: keep 1", output)
        self.assertIn("--confirm 2026", output)
        self.assertEqual(sim_counts(), sim_before)
        self.assertEqual(kept_counts(), kept_before)
        self.assertEqual(played_games(SEASON), 3)

    def test_confirmed_reset_removes_only_that_seasons_sim_rows(self):
        kept_before = kept_counts()
        output = run("--season", str(SEASON), "--confirm", str(SEASON))
        self.assertIn("3/14 UsageAppearance: deleted 3", output)
        self.assertIn("ScheduleGame: cleared home_score, road_score, opened_at, opening_sheet on 3", output)
        self.assertIn("Reset 2026: deleted 13 rows and cleared 3; the schedule is kept", output)
        self.assertFalse(models.UsageCounter.objects.filter(season=SEASON).exists())
        self.assertEqual(played_games(SEASON), 0)
        self.assertEqual(models.ScheduleGame.objects.filter(series__slot__season=SEASON).count(), 3)
        self.assertEqual(played_games(OTHER_SEASON), 3)
        self.assertEqual(models.UsageCounter.objects.filter(season=OTHER_SEASON).count(), 1)
        self.assertEqual(kept_counts(), kept_before)

    def test_mismatched_confirm_is_refused(self):
        sim_before = sim_counts()
        with self.assertRaisesMessage(CommandError, "--confirm 2027 does not match --season 2026"):
            run("--season", str(SEASON), "--confirm", str(OTHER_SEASON))
        self.assertEqual(sim_counts(), sim_before)
        self.assertEqual(played_games(SEASON), 3)

    def test_include_schedule_dry_run_lists_the_schedule(self):
        output = run("--season", str(SEASON), "--include-schedule")
        self.assertIn("ScheduleGame: would delete 3", output)
        self.assertIn("ScheduleSlot: would delete 1", output)
        self.assertIn("HalfPlan: would delete 1", output)


class ResetThenRegenerateTestCase(TestCase):
    def setUp(self):
        self.teams = create_league_teams()
        call_command("generate_schedule", "--season", str(SEASON), "--seed", "7", stdout=StringIO())
        pitcher = create_pitcher("Sim Pitcher", team=self.teams[0], ip=180, gs=30)
        for game in models.ScheduleGame.objects.filter(series__slot__season=SEASON, day__lte=3):
            game.home_score, game.road_score = 4, 2
            game.save()
        game = models.ScheduleGame.objects.filter(series__slot__season=SEASON, day=1).first()
        models.UsageAppearance.objects.create(player=pitcher, game=game, outs=18)
        models.UsageCounter.objects.create(player=pitcher, season=SEASON, outs=18)

    def test_include_schedule_lets_generate_schedule_run_again(self):
        with self.assertRaises(CommandError):
            call_command("generate_schedule", "--season", str(SEASON), "--seed", "8", stdout=StringIO())

        output = run("--season", str(SEASON), "--confirm", str(SEASON), "--include-schedule")
        self.assertIn("ScheduleSlot: deleted 46", output)
        self.assertIn("the schedule is deleted", output)
        self.assertFalse(models.ScheduleSlot.objects.filter(season=SEASON).exists())

        out = StringIO()
        call_command("generate_schedule", "--season", str(SEASON), "--seed", "8", stdout=out)
        self.assertIn("Saved 46 slots, 368 series and 1296 games for 2026", out.getvalue())
        self.assertEqual(played_games(SEASON), 0)
        self.assertEqual(models.Team.objects.count(), 16)


class ResetSimSeasonAdminTestCase(TestCase):
    def setUp(self):
        self.home, self.road = create_teams()
        self.pitcher = create_pitcher("Sim Pitcher", team=self.home, ip=180, gs=30)
        create_played_season(SEASON, self.home, self.road, self.pitcher)
        create_played_season(OTHER_SEASON, self.home, self.road, self.pitcher)
        self.url = reverse("admin:ulmg_usagecounter_reset_sim_season")
        self.client = Client()

    def login_commissioner(self):
        self.client.force_login(
            User.objects.create_superuser(username="commish", email="c@example.com", password="x")
        )

    def test_non_superusers_get_a_403(self):
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(User.objects.create_user(username="owner"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(User.objects.create_user(username="staff", is_staff=True))
        self.assertEqual(self.client.get(self.url, {"season": SEASON}).status_code, 403)
        response = self.client.post(self.url, {"season": SEASON, "confirm": SEASON})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(played_games(SEASON), 3)

    def test_commissioner_sees_the_dry_run(self):
        self.login_commissioner()
        sim_before = sim_counts()
        response = self.client.get(self.url, {"season": SEASON})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UsageAppearance: would delete 3")
        self.assertContains(response, "ScheduleGame: would clear home_score, road_score, opened_at, opening_sheet on 3")
        self.assertEqual(sim_counts(), sim_before)

    def test_commissioner_resets_with_a_typed_confirmation(self):
        self.login_commissioner()
        response = self.client.post(self.url, {"season": SEASON, "confirm": SEASON})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "UsageAppearance: deleted 3")
        self.assertContains(response, "Reset 2026")
        self.assertEqual(played_games(SEASON), 0)
        self.assertFalse(models.UsageCounter.objects.filter(season=SEASON).exists())
        self.assertEqual(played_games(OTHER_SEASON), 3)

    def test_a_mismatched_confirmation_changes_nothing(self):
        self.login_commissioner()
        sim_before = sim_counts()
        response = self.client.post(self.url, {"season": SEASON, "confirm": OTHER_SEASON})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not match")
        self.assertContains(response, "UsageAppearance: would delete 3")
        self.assertEqual(sim_counts(), sim_before)
        self.assertEqual(played_games(SEASON), 3)

    def test_include_schedule_from_the_admin(self):
        self.login_commissioner()
        self.client.post(self.url, {"season": SEASON, "confirm": SEASON, "include_schedule": "on"})
        self.assertFalse(models.ScheduleSlot.objects.filter(season=SEASON).exists())
        self.assertTrue(models.ScheduleSlot.objects.filter(season=OTHER_SEASON).exists())

    def test_usage_counter_list_links_to_the_reset_page(self):
        self.login_commissioner()
        response = self.client.get(reverse("admin:ulmg_usagecounter_changelist"))
        self.assertContains(response, self.url)
