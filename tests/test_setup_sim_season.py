# ABOUTME: Tests for setup_sim_season and its test-setup plan defaults in ulmg.sim_setup.
# ABOUTME: Uses the real league teams, real rosters and cards, the real schedule draw and the plan rules.

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from ulmg import models, plans, roster_moves, schedule, sim_setup
from tests.plan_fixtures import CARD_SEASON, RELIEVER_STATS, SEASON, Roster, create_hitter, create_pitcher
from tests.schedule_fixtures import create_league_teams


def team(abbreviation):
    return models.Team.objects.get(abbreviation=abbreviation)


def set_wrc_plus(player, value):
    models.Card.objects.filter(player=player, season=CARD_SEASON).update(wrc_plus=value)


def set_pitch_stats(player, **stats):
    row = models.PlayerStatSeason.objects.get(player=player, season=CARD_SEASON, classification="1-mlb")
    row.pitch_stats.update(stats)
    row.save()


def run_setup(*args):
    out = StringIO()
    call_command("setup_sim_season", "--season", str(SEASON), "--seed", "21", *args, stdout=out)
    return out.getvalue()


def lineup_positions(entries):
    return {entry["player"]: entry["position"] for entry in entries}


class DefaultPlanTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_league_teams()
        cls.atl = team("ATL")
        cls.roster = Roster(cls.atl)

    def test_rotation_is_the_five_with_the_most_card_season_starts(self):
        sixth = create_pitcher(self.atl, "ATL Sixth", stats={"g": 30, "gs": 20, "ip": "120.0"})
        set_pitch_stats(self.roster.starters[2], gs=33)
        fields, problems = sim_setup.default_plan(self.atl, SEASON)
        s = self.roster.starters
        self.assertEqual(fields["rotation"], [s[2], s[0], s[1], s[3], s[4]])
        self.assertIn(sixth, fields["setup_l"] + fields["setup_r"] + fields["mirp"])
        self.assertEqual(problems, [])

    def test_closer_by_saves_setup_by_holds_and_everyone_else_in_middle_relief(self):
        third = create_pitcher(self.atl, "ATL Reliever 3", stats=RELIEVER_STATS)
        first, second = self.roster.relievers
        set_pitch_stats(second, sv=30, hld=2)
        set_pitch_stats(first, sv=1, hld=25)
        set_pitch_stats(self.roster.swingman, hld=5)
        fields, _ = sim_setup.default_plan(self.atl, SEASON)
        self.assertEqual(fields["closer"], second)
        self.assertEqual(fields["setup_l"], [])
        self.assertEqual(fields["setup_r"], [first, self.roster.swingman])
        self.assertEqual(fields["sirp"], [])
        self.assertEqual(fields["mirp"], [third])

    def test_lineup_is_the_best_bats_at_positions_they_can_play_with_the_best_remaining_at_dh(self):
        utility = create_hitter(self.atl, "ATL Utility", position="IF", defense={"2B": 1.0, "SS": 1.0})
        shortstop = next(p for p in self.roster.fielders if p.name.endswith("SS"))
        second_base = next(p for p in self.roster.fielders if p.name.endswith("2B"))
        bench_bat = self.roster.bench[0]
        for player in self.roster.hitters + self.roster.bench:
            set_wrc_plus(player, 100)
        set_wrc_plus(utility, 150)
        set_wrc_plus(shortstop, 140)
        set_wrc_plus(bench_bat, 130)
        set_wrc_plus(second_base, 60)
        set_wrc_plus(self.roster.hitters[-1], 50)

        fields, problems = sim_setup.default_plan(self.atl, SEASON)
        lineup = fields["lineup_vs_rhp"]
        positions = lineup_positions(lineup)
        self.assertEqual(problems, [])
        self.assertEqual(len(lineup), 9)
        # The utility man moves to 2B so the shortstop can play short.
        self.assertEqual(positions[utility], "2B")
        self.assertEqual(positions[shortstop], "SS")
        # A bat with no glove is the DH; the weaker second baseman sits.
        self.assertEqual(positions[bench_bat], "DH")
        self.assertNotIn(second_base, positions)
        self.assertEqual([e["order"] for e in lineup], list(range(1, 10)))
        self.assertEqual([e["player"] for e in lineup][:3], [utility, shortstop, bench_bat])
        self.assertEqual(fields["lineup_vs_lhp"], lineup)
        # The bench is everyone left, best bat first.
        self.assertEqual(fields["bench"], [self.roster.bench[1], second_base, self.roster.hitters[-1]])

    def test_a_player_without_a_card_is_reported_and_left_out(self):
        reliever = self.roster.relievers[0]
        models.Card.objects.filter(player=reliever).delete()
        fields, problems = sim_setup.default_plan(self.atl, SEASON)
        self.assertEqual(problems, ["No card for ATL Reliever 1; left out of the plan."])
        self.assertNotEqual(fields["closer"], reliever)
        self.assertNotIn(reliever, fields["setup_l"] + fields["setup_r"] + fields["sirp"] + fields["mirp"])

    def test_a_missing_catcher_card_leaves_nobody_to_catch(self):
        models.Card.objects.filter(player=self.roster.catcher).delete()
        fields, problems = sim_setup.default_plan(self.atl, SEASON)
        self.assertEqual(
            problems,
            ["No card for ATL Catcher; left out of the plan.", "No hitter with a card can play C."],
        )
        self.assertEqual(len(fields["lineup_vs_rhp"]), 8)


@override_settings(CURRENT_SEASON=SEASON, TEAM_SEASON_HALF="1h")
class SetupSimSeasonCommandTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rosters = {t.abbreviation: Roster(t) for t in create_league_teams()}

    def assert_complete_plan(self, team_obj, half):
        plan = plans.find_plan(team_obj, SEASON, half)
        self.assertIsNotNone(plan, msg=f"{team_obj.abbreviation} half {half}")
        self.assertEqual(len(plan.rotation), 5)
        self.assertIsNotNone(plan.closer_id)
        self.assertEqual(len(plan.setup_l) + len(plan.setup_r), 2)
        self.assertEqual(len(plan.bench), 2)
        self.assertEqual(len(plan.lineup_vs_lhp), 9)
        self.assertEqual(len(plan.lineup_vs_rhp), 9)
        self.assertEqual(plans.plan_errors(team_obj, SEASON, half, **plans._stored_fields(plan)), [])
        days = range(1, 82) if half == 1 else range(82, 163)
        starters = plans.starters(plan)
        self.assertEqual(sorted(starters), list(days))
        self.assertTrue(all(starters.values()), msg=f"{team_obj.abbreviation} half {half}")
        # Every day's starter is on that game's roster under the roster-move rules.
        rosters = roster_moves.HalfRosters(team_obj, SEASON, half)
        for day, game in plans.half_games(team_obj, SEASON, half).items():
            self.assertIsNone(rosters.problem(starters[day], game), msg=f"{team_obj.abbreviation} day {day}")

    def test_full_setup_gives_every_team_162_games_and_a_complete_first_half_plan(self):
        output = run_setup()
        for team_obj in models.Team.objects.all():
            self.assertEqual(len(schedule.team_games(team_obj, SEASON)), 162)
            self.assert_complete_plan(team_obj, 1)
        self.assertFalse(models.HalfPlan.objects.filter(half=2).exists())
        self.assertIn("Seed: 21", output)
        self.assertIn("Games created: 1296 (162 per team)", output)
        self.assertIn("Plans filled: 16 for half 1 (16 complete)", output)
        self.assertIn("Teams with problems: none", output)

    def test_both_halves_fills_the_second_half_too(self):
        output = run_setup("--both-halves")
        for team_obj in models.Team.objects.all():
            self.assert_complete_plan(team_obj, 1)
            self.assert_complete_plan(team_obj, 2)
        self.assertIn("Plans filled: 32 for halves 1 and 2 (32 complete)", output)
        # The second half stays locked on the normal editing path.
        self.assertFalse(plans.is_open(2))
        with self.assertRaises(plans.PlanError):
            self.rosters["ATL"].file(half=2)

    def test_a_team_with_a_missing_card_is_reported_and_the_others_still_fill(self):
        car_reliever = self.rosters["CAR"].relievers[0]
        models.Card.objects.filter(player=car_reliever).delete()
        models.Card.objects.filter(player=self.rosters["DET"].catcher).delete()
        output = run_setup()

        self.assertIn("Teams with problems: 2", output)
        self.assertIn("CAR: No card for CAR Reliever 1; left out of the plan.", output)
        self.assertIn("DET: No card for DET Catcher; left out of the plan.", output)
        self.assertIn("DET: No hitter with a card can play C.", output)
        self.assertIn("Plans filled: 16 for half 1 (14 complete)", output)
        for team_obj in models.Team.objects.exclude(abbreviation__in=["CAR", "DET"]):
            self.assert_complete_plan(team_obj, 1)

        car = plans.find_plan(team("CAR"), SEASON, 1)
        self.assertNotIn(car_reliever.id, car.setup_l + car.setup_r + car.sirp + car.mirp + [car.closer_id])
        self.assertTrue(all(plans.starters(car).values()))
        self.assertEqual(len(car.lineup_vs_rhp), 9)

        det = plans.find_plan(team("DET"), SEASON, 1)
        self.assertEqual(len(det.rotation), 5)
        self.assertTrue(all(plans.starters(det).values()))
        self.assertEqual(det.lineup_vs_lhp, [])
        self.assertEqual(det.lineup_vs_rhp, [])

    def snapshot(self):
        return {
            "slots": list(models.ScheduleSlot.objects.order_by("id").values_list("id", "first_day")),
            "series": list(
                models.ScheduleSeries.objects.order_by("id").values_list("id", "home_team", "road_team")
            ),
            "games": models.ScheduleGame.objects.count(),
            "plans": list(models.HalfPlan.objects.order_by("id").values()),
            "days": list(models.HalfPlanDay.objects.order_by("id").values()),
            "counters": list(models.UsageCounter.objects.order_by("id").values()),
        }

    def test_the_dry_run_changes_nothing(self):
        empty = self.snapshot()
        output = run_setup("--dry-run", "--both-halves")
        self.assertEqual(self.snapshot(), empty)
        self.assertEqual(models.ScheduleGame.objects.count(), 0)
        self.assertIn("Games created: 1296 (162 per team)", output)
        self.assertIn("Dry run: nothing saved", output)

        run_setup()
        before = self.snapshot()
        out = StringIO()
        call_command(
            "setup_sim_season", "--season", str(SEASON), "--seed", "99", "--dry-run", "--both-halves",
            stdout=out,
        )
        self.assertEqual(self.snapshot(), before)
        self.assertIn("Dry run: nothing saved", out.getvalue())

    def test_setup_refuses_once_games_are_played_and_succeeds_again_after_a_reset(self):
        run_setup()
        game = schedule.season_games(SEASON).first()
        game.home_score, game.road_score = 3, 2
        game.save()
        before = self.snapshot()
        with self.assertRaises(CommandError) as raised:
            run_setup()
        message = str(raised.exception)
        self.assertIn(f"{SEASON} has played games", message)
        self.assertIn(f"reset_sim_season --season {SEASON}", message)
        self.assertEqual(self.snapshot(), before)

        call_command(
            "reset_sim_season", "--season", str(SEASON), "--confirm", str(SEASON), "--include-schedule",
            stdout=StringIO(),
        )
        self.assertFalse(models.ScheduleGame.objects.exists())
        self.assertFalse(models.HalfPlan.objects.exists())

        output = run_setup()
        self.assertIn("Games created: 1296 (162 per team)", output)
        self.assertIn("Teams with problems: none", output)
        for team_obj in models.Team.objects.all():
            self.assertEqual(len(schedule.team_games(team_obj, SEASON)), 162)
            self.assert_complete_plan(team_obj, 1)
