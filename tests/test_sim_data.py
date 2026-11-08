# ABOUTME: Unit and integration tests for the sim-data registry and the season reset in ulmg.sim_data.
# ABOUTME: Covers registry coverage, safe cascades, dry-run plans, what a reset deletes and keeps, restore hooks and rollback.

from django.apps import apps
from django.db import models as django_models
from django.test import TestCase

from ulmg import models, plans, sim_data
from tests.sim_fixtures import STAT_CLASSIFICATIONS, create_kept_rows, create_played_season
from tests.usage_fixtures import create_pitcher, create_teams

SEASON = 2026
OTHER_SEASON = 2027


def row_counts(model_list):
    return {model: model.objects.count() for model in model_list}


class RegistryCoverageTestCase(TestCase):
    def test_every_ulmg_model_is_classified(self):
        self.assertEqual(sim_data.unclassified_models(), [])

    def test_an_unclassified_model_is_reported(self):
        registry = [entry for entry in sim_data.SIM_MODELS if entry.model is not models.UsagePause]
        self.assertEqual(sim_data.unclassified_models(sim_models=registry), [models.UsagePause])

    def test_a_model_missing_from_the_kept_list_is_reported(self):
        kept = [model for model in sim_data.KEPT_MODELS if model is not models.Card]
        self.assertEqual(sim_data.unclassified_models(kept_models=kept), [models.Card])

    def test_no_model_is_both_sim_and_kept(self):
        sim = {entry.model for entry in sim_data.SIM_MODELS}
        self.assertEqual(sim & set(sim_data.KEPT_MODELS), set())

    def test_the_lists_hold_only_ulmg_models(self):
        ulmg_models = set(apps.get_app_config("ulmg").get_models())
        for entry in sim_data.SIM_MODELS:
            self.assertIn(entry.model, ulmg_models)
        for model in sim_data.KEPT_MODELS:
            self.assertIn(model, ulmg_models)

    def test_deleting_sim_rows_reaches_only_sim_models_deleted_earlier(self):
        """
        Every row that points at a deletable sim model belongs to a sim model
        the reset deletes first, so a delete never cascades into, or nulls a
        field on, a kept row, and each model's count is its own rows.
        """
        registry = sim_data.SIM_MODELS
        for index, entry in enumerate(registry):
            earlier = {e.model for e in registry[:index]}
            for relation in entry.model._meta.related_objects:
                self.assertIn(
                    relation.related_model,
                    earlier,
                    f"{relation.related_model.__name__} points at {entry.model.__name__} "
                    "but is not a sim model deleted before it",
                )

    def test_season_lookups_resolve(self):
        for entry in sim_data.SIM_MODELS:
            # Building the query raises FieldError for a bad lookup.
            str(entry.rows(SEASON).query)

    def test_schedule_game_clears_every_field_that_marks_it_played(self):
        entry = sim_data.entry_for(models.ScheduleGame)
        self.assertEqual(
            entry.clear_fields,
            {"home_score": None, "road_score": None, "opened_at": None, "opening_sheet": None},
        )
        self.assertTrue(entry.schedule)


class ResetTestCase(TestCase):
    def setUp(self):
        self.home, self.road = create_teams()
        self.pitcher = create_pitcher("Sim Pitcher", team=self.home, ip=180, gs=30)
        self.games = create_played_season(SEASON, self.home, self.road, self.pitcher)
        self.other_games = create_played_season(OTHER_SEASON, self.home, self.road, self.pitcher)
        create_kept_rows(SEASON, self.home, self.pitcher)
        self.kept_before = row_counts(sim_data.KEPT_MODELS)

    def assert_kept_rows_survive(self):
        self.assertEqual(row_counts(sim_data.KEPT_MODELS), self.kept_before)
        for classification in STAT_CLASSIFICATIONS:
            self.assertTrue(
                models.PlayerStatSeason.objects.filter(
                    player=self.pitcher, season=SEASON, classification=classification
                ).exists(),
                classification,
            )
        # The card season's 1-mlb line from the usage fixtures.
        self.assertTrue(
            models.PlayerStatSeason.objects.filter(
                player=self.pitcher, season=SEASON - 1, classification="1-mlb"
            ).exists()
        )
        self.assertTrue(models.Card.objects.filter(player=self.pitcher, season=SEASON).exists())

    def assert_other_season_survives(self):
        self.assertEqual(models.ScheduleSlot.objects.filter(season=OTHER_SEASON).count(), 1)
        self.assertEqual(models.ScheduleSeries.objects.filter(slot__season=OTHER_SEASON).count(), 1)
        other = models.ScheduleGame.objects.filter(series__slot__season=OTHER_SEASON)
        self.assertEqual(other.count(), 3)
        self.assertEqual(other.filter(home_score__isnull=False, road_score__isnull=False).count(), 3)
        self.assertEqual(other.filter(opened_at__isnull=False, opening_sheet__isnull=False).count(), 3)
        self.assertEqual(models.HalfPlan.objects.filter(season=OTHER_SEASON).count(), 1)
        self.assertEqual(models.HalfPlanDay.objects.filter(plan__season=OTHER_SEASON).count(), 3)
        self.assertEqual(models.UsageCounter.objects.filter(season=OTHER_SEASON).count(), 1)
        self.assertEqual(
            models.UsageAppearance.objects.filter(game__series__slot__season=OTHER_SEASON).count(), 3
        )
        self.assertEqual(
            models.UsageOverride.objects.filter(game__series__slot__season=OTHER_SEASON).count(), 1
        )
        self.assertEqual(
            models.UsagePause.objects.filter(game__series__slot__season=OTHER_SEASON).count(), 1
        )
        self.assertTrue(
            models.PlayerStatSeason.objects.filter(season=OTHER_SEASON, classification="6-ulmg").exists()
        )

    def test_fixture_holds_rows_of_every_kept_model(self):
        # Otherwise the survival checks below would pass for an empty table.
        for model, count in self.kept_before.items():
            self.assertGreater(count, 0, model.__name__)

    def plan_by_model(self, steps):
        return {step.entry.model: (step.action, step.count) for step in steps}

    def test_plan_counts_rows_and_changes_nothing(self):
        steps = sim_data.plan_reset(SEASON)
        self.assertEqual(
            self.plan_by_model(steps),
            {
                models.UsageAppearance: ("delete", 3),
                models.UsageOverride: ("delete", 1),
                models.UsagePause: ("delete", 1),
                models.UsageCounter: ("delete", 1),
                models.PlayerStatSeason: ("delete", 1),
                models.HalfPlanDay: ("keep", 3),
                models.HalfPlan: ("keep", 1),
                models.ScheduleGame: ("clear", 3),
                models.ScheduleSeries: ("keep", 1),
                models.ScheduleSlot: ("keep", 1),
            },
        )
        self.assertEqual(models.UsageAppearance.objects.count(), 6)
        self.assertEqual(models.ScheduleGame.objects.filter(home_score__isnull=False).count(), 6)
        self.assert_kept_rows_survive()

    def test_plan_with_schedule_deletes_the_schedule(self):
        plan = self.plan_by_model(sim_data.plan_reset(SEASON, include_schedule=True))
        self.assertEqual(plan[models.HalfPlanDay], ("delete", 3))
        self.assertEqual(plan[models.HalfPlan], ("delete", 1))
        self.assertEqual(plan[models.ScheduleGame], ("delete", 3))
        self.assertEqual(plan[models.ScheduleSeries], ("delete", 1))
        self.assertEqual(plan[models.ScheduleSlot], ("delete", 1))

    def test_clear_counts_only_games_with_a_result_or_an_opening(self):
        unopened = self.games[0]
        unopened.home_score = unopened.road_score = unopened.opened_at = unopened.opening_sheet = None
        unopened.save()
        opened_only = self.games[1]
        opened_only.home_score = opened_only.road_score = None
        opened_only.save()
        half_scored = self.games[2]
        half_scored.road_score = half_scored.opened_at = half_scored.opening_sheet = None
        half_scored.save()
        plan = self.plan_by_model(sim_data.plan_reset(SEASON))
        self.assertEqual(plan[models.ScheduleGame], ("clear", 2))

    def test_clear_counts_a_game_with_only_an_opening_sheet(self):
        for game in self.games:
            game.home_score = game.road_score = game.opened_at = None
            game.save()
        plan = self.plan_by_model(sim_data.plan_reset(SEASON))
        self.assertEqual(plan[models.ScheduleGame], ("clear", 3))
        sim_data.reset_season(SEASON)
        games = models.ScheduleGame.objects.filter(series__slot__season=SEASON)
        self.assertFalse(games.filter(opening_sheet__isnull=False).exists())

    def test_reset_removes_only_the_seasons_sim_rows(self):
        steps = sim_data.reset_season(SEASON)

        self.assertEqual(self.plan_by_model(steps)[models.UsageAppearance], ("delete", 3))
        self.assertFalse(models.UsageCounter.objects.filter(season=SEASON).exists())
        self.assertFalse(models.UsageAppearance.objects.filter(game__series__slot__season=SEASON).exists())
        self.assertFalse(models.UsageOverride.objects.filter(game__series__slot__season=SEASON).exists())
        self.assertFalse(models.UsagePause.objects.filter(game__series__slot__season=SEASON).exists())
        self.assertFalse(
            models.PlayerStatSeason.objects.filter(season=SEASON, classification="6-ulmg").exists()
        )

        # The schedule stays, and every game goes back to unplayed.
        self.assertEqual(models.ScheduleSlot.objects.filter(season=SEASON).count(), 1)
        self.assertEqual(models.ScheduleSeries.objects.filter(slot__season=SEASON).count(), 1)
        games = models.ScheduleGame.objects.filter(series__slot__season=SEASON)
        self.assertEqual(sorted(g.pk for g in games), sorted(g.pk for g in self.games))
        self.assertFalse(any(g.is_played for g in games))
        self.assertFalse(games.filter(home_score__isnull=False).exists())
        self.assertFalse(games.filter(road_score__isnull=False).exists())
        # Opened games go back to unopened, so they can be opened again.
        self.assertFalse(games.filter(opened_at__isnull=False).exists())
        self.assertFalse(games.filter(opening_sheet__isnull=False).exists())
        self.assertFalse(any(plans.is_locked(g) for g in games))
        # Half plans are kept with the schedule.
        self.assertEqual(models.HalfPlan.objects.filter(season=SEASON).count(), 1)
        self.assertEqual(models.HalfPlanDay.objects.filter(plan__season=SEASON).count(), 3)

        self.assert_other_season_survives()
        self.assert_kept_rows_survive()
        self.assertTrue(models.Player.objects.filter(pk=self.pitcher.pk).exists())
        self.assertEqual(models.Team.objects.count(), 2)

    def test_reset_with_schedule_deletes_the_schedule(self):
        sim_data.reset_season(SEASON, include_schedule=True)
        self.assertFalse(models.ScheduleSlot.objects.filter(season=SEASON).exists())
        self.assertFalse(models.ScheduleSeries.objects.filter(slot__season=SEASON).exists())
        self.assertFalse(models.ScheduleGame.objects.filter(series__slot__season=SEASON).exists())
        self.assertFalse(models.HalfPlan.objects.filter(season=SEASON).exists())
        self.assertFalse(models.HalfPlanDay.objects.filter(plan__season=SEASON).exists())
        self.assertFalse(models.UsageCounter.objects.filter(season=SEASON).exists())
        self.assert_other_season_survives()
        self.assert_kept_rows_survive()

    def test_a_second_reset_finds_nothing(self):
        sim_data.reset_season(SEASON)
        steps = sim_data.plan_reset(SEASON)
        for step in steps:
            if step.action != "keep":
                self.assertEqual(step.count, 0, step.entry.model.__name__)

    def test_progress_reports_each_model(self):
        lines = []
        sim_data.reset_season(SEASON, progress=lines.append)
        # One line per model, then one for reapplying the kept plans' swingman designations.
        self.assertEqual(len(lines), len(sim_data.SIM_MODELS) + 1)
        self.assertIn("UsageAppearance", lines[0])
        self.assertIn("swingman designations", lines[-1])

    def test_restore_runs_after_its_models_delete(self):
        seen = []

        def restore_counters(season):
            seen.append((season, models.UsageCounter.objects.filter(season=season).count()))
            return "put the test flags back"

        registry = list(sim_data.SIM_MODELS)
        index = registry.index(sim_data.entry_for(models.UsageCounter))
        registry[index] = sim_data.SimModel(models.UsageCounter, "season", restore=restore_counters)

        lines = []
        sim_data.reset_season(SEASON, registry=registry, progress=lines.append)
        self.assertEqual(seen, [(SEASON, 0)])
        self.assertTrue(any("put the test flags back" in line for line in lines))

    def test_restore_does_not_run_in_a_plan(self):
        seen = []
        registry = [sim_data.SimModel(models.UsageCounter, "season", restore=seen.append)]
        steps = sim_data.plan_reset(SEASON, registry=registry)
        self.assertEqual(seen, [])
        self.assertTrue(steps[0].has_restore)

    def test_a_failure_partway_rolls_everything_back(self):
        def fail(season):
            raise RuntimeError("restore failed")

        registry = list(sim_data.SIM_MODELS)
        # Fail after the usage ledger is deleted and the games are cleared.
        index = registry.index(sim_data.entry_for(models.ScheduleGame))
        registry.insert(
            index + 1, sim_data.SimModel(models.UsageCounter, "season", restore=fail)
        )

        sim_before = row_counts([entry.model for entry in sim_data.SIM_MODELS])
        with self.assertRaisesMessage(RuntimeError, "restore failed"):
            sim_data.reset_season(SEASON, registry=registry)

        self.assertEqual(row_counts([entry.model for entry in sim_data.SIM_MODELS]), sim_before)
        played = models.ScheduleGame.objects.filter(
            series__slot__season=SEASON, home_score__isnull=False, road_score__isnull=False
        )
        self.assertEqual(played.count(), 3)
        self.assert_kept_rows_survive()

    def test_a_delete_that_cascades_is_refused(self):
        # ScheduleSlot listed before its series, games and usage would cascade into them.
        registry = [sim_data.SimModel(models.ScheduleSlot, "season", schedule=True)]
        with self.assertRaises(sim_data.SimResetError):
            sim_data.reset_season(SEASON, include_schedule=True, registry=registry)
        self.assertEqual(models.ScheduleSlot.objects.filter(season=SEASON).count(), 1)
        self.assertEqual(models.UsageAppearance.objects.count(), 6)
