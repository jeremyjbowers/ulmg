# ABOUTME: Tests that a sim reset keeping the schedule puts plan swingman designations back on fresh usage counters.
# ABOUTME: With --include-schedule the plans are gone, so no counters are recreated.
from django.test import TestCase, override_settings

from ulmg import models, sim_data, usage
from tests.plan_fixtures import SEASON, Roster, create_season


@override_settings(CURRENT_SEASON=SEASON, TEAM_SEASON_HALF="1h")
class ResetKeepsPlanDesignationsTestCase(TestCase):
    def setUp(self):
        create_season()
        self.roster = Roster(models.Team.objects.get(abbreviation="ATL"))
        self.roster.file()

    def test_a_kept_plan_reapplies_its_designations(self):
        self.assertTrue(usage.counter_for(self.roster.swingman, SEASON).confined_to_relief)

        steps = sim_data.reset_season(SEASON)

        counter = models.UsageCounter.objects.get(player=self.roster.swingman, season=SEASON)
        self.assertTrue(counter.confined_to_relief)
        self.assertIn("designations", sim_data.summarize(SEASON, steps, False, done=True))

    def test_include_schedule_leaves_no_counters(self):
        sim_data.reset_season(SEASON, include_schedule=True)

        self.assertFalse(models.UsageCounter.objects.filter(season=SEASON).exists())
        self.assertFalse(models.HalfPlan.objects.filter(season=SEASON).exists())

    def test_a_dry_run_mentions_the_designations(self):
        steps = sim_data.plan_reset(SEASON)
        self.assertIn("designations", sim_data.summarize(SEASON, steps, False, done=False))
