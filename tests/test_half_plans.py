# ABOUTME: Tests for half plans in ulmg.plans: starter auto-fill, spot starts, lineups and opened games.
# ABOUTME: Uses a real generated schedule, real rosters and cards, and the usage ledger in the test database.

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ulmg import models, plans, schedule, usage
from tests.plan_fixtures import (
    SEASON,
    Roster,
    create_hitter,
    create_pitcher,
    create_season,
)


def team(abbreviation):
    return models.Team.objects.get(abbreviation=abbreviation)


def game_on(team_obj, day):
    return next(g for g in schedule.team_games(team_obj, SEASON) if g.day == day)


def opponent_on(team_obj, day):
    game = game_on(team_obj, day)
    if game.series.home_team_id == team_obj.id:
        return game.series.road_team
    return game.series.home_team


def side(game, team_obj):
    sheet = plans.game_sheet(game)
    return sheet["home"] if game.series.home_team_id == team_obj.id else sheet["road"]


def slot_of(day):
    for slot in models.ScheduleSlot.objects.filter(season=SEASON):
        if slot.first_day <= day <= slot.last_day:
            return slot
    raise AssertionError(f"No slot holds day {day}")


@override_settings(CURRENT_SEASON=SEASON, TEAM_SEASON_HALF="1h")
class PlanTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_season()
        cls.atl = team("ATL")
        cls.roster = Roster(cls.atl)


class RotationAutoFillTestCase(PlanTestCase):
    def test_five_man_rotation_gives_the_first_starter_games_1_6_11(self):
        plan = self.roster.file()
        starters = plans.starters(plan)
        self.assertEqual(sorted(starters), list(range(1, 82)))
        first = self.roster.starters[0]
        self.assertEqual([d for d, p in sorted(starters.items()) if p == first][:3], [1, 6, 11])
        for day, pitcher in starters.items():
            self.assertEqual(pitcher, self.roster.starters[(day - 1) % 5], msg=f"day {day}")

    def test_second_half_days_are_82_through_162(self):
        with self.settings(TEAM_SEASON_HALF="2h"):
            plan = self.roster.file(half=2)
        starters = plans.starters(plan)
        self.assertEqual(sorted(starters), list(range(82, 163)))
        self.assertEqual(starters[82], self.roster.starters[0])
        self.assertEqual(starters[87], self.roster.starters[0])

    def test_auto_fill_skips_a_capped_starter_and_continues_the_cycle(self):
        # Two card-season starts and ten innings: a starts cap of two.
        capped = create_pitcher(self.atl, "ATL Capped", stats={"g": 2, "gs": 2, "ip": "10.0"})
        rotation = list(self.roster.starters[:4])
        rotation.insert(1, capped)
        plan = self.roster.file(rotation=rotation)
        starters = plans.starters(plan)
        self.assertEqual(starters[2], capped)
        self.assertEqual(starters[7], capped)
        # Day 12 is his slot; the next legal pitcher in rotation order takes it.
        self.assertEqual(starters[12], rotation[2])
        # The cycle continues as if day 12 had been rotation[2]'s.
        self.assertEqual(starters[13], rotation[3])
        self.assertEqual(starters[14], rotation[4])
        self.assertEqual(starters[15], rotation[0])
        self.assertEqual(starters[16], rotation[2])
        self.assertEqual(list(starters.values()).count(capped), 2)

    def test_save_rejected_when_a_day_has_no_legal_starter(self):
        # Three starters cannot cover a four-game series inside series rest.
        with self.assertRaises(plans.PlanError) as raised:
            self.roster.file(rotation=self.roster.starters[:3])
        message = str(raised.exception)
        self.assertIn("No legal starter", message)
        self.assertIn(4, raised.exception.days)
        self.assertFalse(models.HalfPlanDay.objects.filter(auto_starter__isnull=False).exists())

    def test_saving_sets_swingman_designations(self):
        self.roster.file()
        swingman = usage.counter_for(self.roster.swingman, SEASON)
        self.assertTrue(swingman.confined_to_relief)
        starter = usage.counter_for(self.roster.starters[0], SEASON)
        self.assertFalse(starter.confined_to_relief)

        rotation = self.roster.starters[:4] + [self.roster.swingman]
        self.roster.file(rotation=rotation)
        swingman.refresh_from_db()
        self.assertFalse(swingman.confined_to_relief)

    def test_saves_when_a_card_is_missing(self):
        uncarded = create_hitter(self.atl, "ATL Uncarded", card=False)
        hitters = self.roster.hitters[:-1] + [uncarded]
        plan = self.roster.file(lineup_vs_rhp=self.roster.lineup(hitters))
        self.assertEqual(plan.lineup_vs_rhp[-1], {"player": uncarded.id, "position": "DH"})


class SpotStartTestCase(PlanTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.plan = cls.roster.file()
        cls.first = cls.roster.starters[0]

    def test_spot_start_accepted_and_marked(self):
        spot = create_pitcher(self.atl, "ATL Spot Starter")
        plans.save_day(self.plan, 20, starter=spot)
        row = self.plan.days.get(day=20)
        self.assertEqual(row.manual_starter, spot)
        self.assertIsNotNone(row.auto_starter)
        self.assertEqual(plans.starters(self.plan)[20], spot)

    def test_a_pure_reliever_cannot_spot_start(self):
        with self.assertRaises(plans.PlanError) as raised:
            plans.save_day(self.plan, 20, starter=self.roster.relievers[1])
        self.assertIn("cap is 0 starts", str(raised.exception))

    def test_spot_start_rejected_for_in_series_rest(self):
        slot = slot_of(1)
        self.assertGreaterEqual(slot.length, 3)
        with self.assertRaises(plans.PlanError) as raised:
            plans.save_day(self.plan, 3, starter=self.first)
        self.assertIn("rest", str(raised.exception))
        self.assertIsNone(self.plan.days.get(day=3).manual_starter)

    def test_spot_start_allowed_the_day_after_a_series_ends(self):
        last_day = slot_of(1).last_day
        closer_of_series = plans.starters(self.plan)[last_day]
        plans.save_day(self.plan, last_day + 1, starter=closer_of_series)
        starters = plans.starters(self.plan)
        self.assertEqual(starters[last_day], closer_of_series)
        self.assertEqual(starters[last_day + 1], closer_of_series)

    def test_spot_start_rejected_for_the_start_cap(self):
        capped = create_pitcher(self.atl, "ATL Capped", stats={"g": 2, "gs": 2, "ip": "10.0"})
        plans.save_day(self.plan, 20, starter=capped)
        plans.save_day(self.plan, 40, starter=capped)
        with self.assertRaises(plans.PlanError) as raised:
            plans.save_day(self.plan, 60, starter=capped)
        self.assertIn("cap is 2 starts", str(raised.exception))

    def test_spot_start_rejected_for_a_pitcher_off_the_30_man(self):
        minor = create_pitcher(self.atl, "ATL Minor Leaguer", roster=False)
        with self.assertRaises(plans.PlanError) as raised:
            plans.save_day(self.plan, 20, starter=minor)
        self.assertIn("30-man", str(raised.exception))

    def test_spot_start_for_a_bullpen_only_swingman_ends_his_relief_designation(self):
        swingman = self.roster.swingman
        self.assertTrue(usage.counter_for(swingman, SEASON).confined_to_relief)
        warnings = plans.save_day(self.plan, 20, starter=swingman)
        self.assertEqual(len(warnings), 1)
        self.assertIn("ends his relief-only designation", warnings[0])
        self.assertFalse(usage.counter_for(swingman, SEASON).confined_to_relief)

    def test_manual_edits_survive_a_refill(self):
        # starters[3] has no auto start in days 25-28; day 26 is legal for him.
        spot = self.roster.starters[3]
        day = 26
        self.assertEqual(slot_of(day).first_day, 25)
        plans.save_day(self.plan, day, starter=spot)
        reordered = list(reversed(self.roster.starters))
        self.roster.file(rotation=reordered)
        self.plan.refresh_from_db()
        starters = plans.starters(self.plan)
        self.assertEqual(starters[day], spot)
        self.assertTrue(self.plan.days.get(day=day).manual_starter_id)
        # Auto days follow the new order and move around the manual start.
        self.assertEqual(starters[1], reordered[0])
        self.assertEqual(starters[2], reordered[1])
        self.assertEqual(reordered[1], spot)
        self.assertNotEqual(starters[27], spot)

    def test_clearing_a_spot_start_returns_the_day_to_auto_fill(self):
        plans.save_day(self.plan, 20, starter=create_pitcher(self.atl, "ATL Spot Starter"))
        plans.save_day(self.plan, 20, starter=None)
        self.assertEqual(plans.starters(self.plan)[20], self.roster.starters[(20 - 1) % 5])


class LineupTestCase(PlanTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.day = 1
        cls.opponent = opponent_on(cls.atl, cls.day)
        cls.opponent_roster = Roster(cls.opponent, throws=("L", "R", "R", "R", "R"))
        cls.opponent_plan = cls.opponent_roster.file()
        bench = cls.roster.bench[0]
        cls.vs_lhp = cls.roster.lineup(cls.roster.hitters[:-1] + [bench])
        cls.vs_rhp = cls.roster.lineup()
        cls.plan = cls.roster.file(lineup_vs_lhp=cls.vs_lhp, lineup_vs_rhp=cls.vs_rhp)
        cls.game = game_on(cls.atl, cls.day)

    def lineup_ids(self, entries):
        return [(e["player"].id, e["position"]) for e in entries]

    def sheet_ids(self):
        return [(p.id, position) for p, position in side(self.game, self.atl)["lineup"]]

    def test_lineup_follows_the_opponent_starters_hand_and_flips(self):
        self.assertEqual(side(self.game, self.opponent)["starter"].throws, "L")
        self.assertEqual(side(self.game, self.atl)["vs"], "L")
        self.assertEqual(self.sheet_ids(), self.lineup_ids(self.vs_lhp))

        # The opponent re-orders his rotation; day 1 now goes to a right-hander.
        starters = self.opponent_roster.starters
        self.opponent_roster.file(rotation=starters[1:] + starters[:1])
        self.assertEqual(side(self.game, self.opponent)["starter"].throws, "R")
        self.assertEqual(side(self.game, self.atl)["vs"], "R")
        self.assertEqual(self.sheet_ids(), self.lineup_ids(self.vs_rhp))

    def test_lineup_override_kept_through_a_flip(self):
        custom = self.roster.lineup()
        custom[8] = {"order": 9, "player": self.roster.bench[1], "position": "DH"}
        plans.save_day(self.plan, self.day, lineup=custom)
        self.assertEqual(self.sheet_ids(), self.lineup_ids(custom))
        self.assertTrue(side(self.game, self.atl)["lineup_manual"])

        starters = self.opponent_roster.starters
        self.opponent_roster.file(rotation=starters[1:] + starters[:1])
        self.assertEqual(side(self.game, self.atl)["vs"], "R")
        self.assertEqual(self.sheet_ids(), self.lineup_ids(custom))

    def test_lineup_against_a_team_without_a_plan_uses_the_vs_rhp_card(self):
        other_day = next(
            d for d in range(2, 82) if opponent_on(self.atl, d) != self.opponent
        )
        sheet = side(game_on(self.atl, other_day), self.atl)
        self.assertEqual(sheet["vs"], "R")
        self.assertIsNone(sheet["opponent_starter"])


class LineupValidationTestCase(PlanTestCase):
    def assertRejected(self, lineup, text):
        with self.assertRaises(plans.PlanError) as raised:
            self.roster.file(lineup_vs_rhp=lineup)
        self.assertIn(text, str(raised.exception))
        self.assertFalse(models.HalfPlan.objects.filter(team=self.atl).exclude(lineup_vs_rhp=[]).exists())

    def test_duplicate_batting_order_slot_rejected(self):
        lineup = self.roster.lineup()
        lineup[4]["order"] = 3
        self.assertRejected(lineup, "Batting order 3 is used twice")

    def test_pitcher_in_the_order_rejected(self):
        lineup = self.roster.lineup()
        lineup[8]["player"] = self.roster.starters[0]
        self.assertRejected(lineup, "is a pitcher; pitchers do not hit")

    def test_player_not_on_the_30_man_rejected(self):
        minor = create_hitter(self.atl, "ATL Minor Leaguer", roster=False)
        lineup = self.roster.lineup()
        lineup[8]["player"] = minor
        self.assertRejected(lineup, "ATL Minor Leaguer is not on ATL's 30-man")

    def test_another_teams_player_rejected(self):
        stranger = create_hitter(team("CAR"), "CAR Hitter")
        lineup = self.roster.lineup()
        lineup[8]["player"] = stranger
        self.assertRejected(lineup, "CAR Hitter is not on ATL's 30-man")

    def test_non_catcher_at_c_rejected(self):
        lineup = self.roster.lineup()
        lineup[0]["player"], lineup[1]["player"] = lineup[1]["player"], lineup[0]["player"]
        self.assertRejected(lineup, "has no catcher rating")

    def test_duplicate_position_and_short_lineup_rejected(self):
        lineup = self.roster.lineup()
        lineup[8]["position"] = "LF"
        self.assertRejected(lineup, "LF is filed twice")
        self.assertRejected(self.roster.lineup()[:8], "nine batters")

    def test_lineup_override_follows_the_same_rules(self):
        plan = self.roster.file()
        lineup = self.roster.lineup()
        lineup[8]["player"] = self.roster.relievers[0]
        with self.assertRaises(plans.PlanError) as raised:
            plans.save_day(plan, 10, lineup=lineup)
        self.assertIn("pitchers do not hit", str(raised.exception))
        self.assertIsNone(plan.days.get(day=10).manual_lineup)

    def test_bench_and_bullpen_rules(self):
        with self.assertRaises(plans.PlanError) as raised:
            self.roster.file(bench=[self.roster.relievers[0]], setup=[self.roster.relievers[0]])
        message = str(raised.exception)
        self.assertIn("The bench is for non-pitchers", message)
        self.assertIn("is in the bullpen twice", message)


class SecondHalfTestCase(PlanTestCase):
    def test_second_half_plan_locked_until_2h(self):
        with self.assertRaises(plans.PlanError) as raised:
            self.roster.file(half=2)
        self.assertIn("opens after the trade break", str(raised.exception))
        self.assertFalse(models.HalfPlanDay.objects.exists())
        self.assertFalse(plans.is_open(2))
        with self.settings(TEAM_SEASON_HALF="2h"):
            self.assertTrue(plans.is_open(2))
            self.roster.file(half=2)
        self.assertEqual(models.HalfPlanDay.objects.filter(plan__half=2).count(), 81)


class OpenedGameTestCase(PlanTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.plan = cls.roster.file()
        cls.game = game_on(cls.atl, 1)

    def test_an_opened_game_ignores_later_plan_edits(self):
        opened = plans.open_game(self.game)
        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.opened_at)
        before = side(self.game, self.atl)
        self.assertEqual(before["starter"], self.roster.starters[0])

        reordered = list(reversed(self.roster.starters))
        new_lineup = self.roster.lineup(self.roster.hitters[:-1] + [self.roster.bench[0]])
        self.roster.file(rotation=reordered, lineup_vs_rhp=new_lineup, lineup_vs_lhp=new_lineup)

        after = side(self.game, self.atl)
        self.assertEqual(after["starter"], self.roster.starters[0])
        self.assertEqual(after["lineup"], before["lineup"])
        self.assertEqual(plans.open_game(self.game), opened)
        self.assertEqual(plans.starters(self.plan)[1], self.roster.starters[0])
        # The cycle continues from the opened day.
        self.assertEqual(plans.starters(self.plan)[2], reordered[0])

        with self.assertRaises(plans.PlanError) as raised:
            plans.save_day(self.plan, 1, starter=self.roster.starters[1])
        self.assertIn("has opened", str(raised.exception))

    def test_a_played_game_cannot_be_edited(self):
        self.game.home_score, self.game.road_score = 3, 2
        self.game.save()
        with self.assertRaises(plans.PlanError):
            plans.save_day(self.plan, 1, starter=self.roster.relievers[0])

    def test_the_opened_sheet_carries_starter_lineup_bench_and_bullpen(self):
        opened = plans.open_game(self.game)
        key = "home" if self.game.series.home_team_id == self.atl.id else "road"
        sheet = opened[key]
        self.assertEqual(sheet["team"], "ATL")
        self.assertEqual(sheet["starter"], self.roster.starters[0].id)
        self.assertEqual(len(sheet["lineup"]), 9)
        self.assertEqual(sheet["bench"], [p.id for p in self.roster.bench])
        self.assertEqual(sheet["closer"], self.roster.relievers[0].id)
        self.assertEqual(sheet["setup"], [self.roster.relievers[1].id])
        self.assertEqual(sheet["middle_long"], [self.roster.swingman.id])


class SeasonStartersTestCase(PlanTestCase):
    def test_season_starters_by_team_and_day(self):
        self.roster.file()
        starters = plans.season_starters(SEASON)
        self.assertEqual(starters[(self.atl.id, 1)], self.roster.starters[0])
        self.assertEqual(starters[(self.atl.id, 81)], self.roster.starters[0])
        self.assertNotIn((self.atl.id, 82), starters)


class EditPermissionTestCase(PlanTestCase):
    def test_owner_and_commissioner_can_edit_others_cannot(self):
        owner_user = User.objects.create_user("atl", "atl@example.com", "x")
        owner = models.Owner.objects.create(user=owner_user, name="ATL Owner")
        self.atl.owner_obj = owner
        self.atl.save()
        other_user = User.objects.create_user("car", "car@example.com", "x")
        other = models.Owner.objects.create(user=other_user, name="CAR Owner")
        car = team("CAR")
        car.owner_obj = other
        car.save()
        commissioner = User.objects.create_superuser("commish", "c@example.com", "x")

        self.assertTrue(plans.can_edit(owner_user, self.atl))
        self.assertFalse(plans.can_edit(other_user, self.atl))
        self.assertTrue(plans.can_edit(commissioner, self.atl))


class FillPlanTestCase(PlanTestCase):
    """plans.fill_plan saves what is legal and reports the rest, for building test seasons."""

    def fields(self, **kwargs):
        fields = {
            "rotation": self.roster.starters,
            "closer": self.roster.relievers[0],
            "setup": [self.roster.relievers[1]],
            "middle_long": [self.roster.swingman],
            "bench": self.roster.bench,
            "lineup_vs_lhp": self.roster.lineup(),
            "lineup_vs_rhp": self.roster.lineup(),
        }
        fields.update(kwargs)
        return fields

    def test_a_legal_plan_fills_like_save_plan(self):
        plan = plans.plan_for(self.atl, SEASON, 1)
        self.assertEqual(plans.fill_plan(plan, **self.fields()), [])
        plan.refresh_from_db()
        self.assertEqual(plan.rotation, [p.id for p in self.roster.starters])
        self.assertEqual(plan.closer, self.roster.relievers[0])
        self.assertEqual(len(plan.lineup_vs_lhp), 9)
        starters = plans.starters(plan)
        self.assertEqual(sorted(starters), list(range(1, 82)))
        self.assertEqual(starters[6], self.roster.starters[0])
        self.assertTrue(usage.counter_for(self.roster.swingman, SEASON).confined_to_relief)

    def test_a_broken_section_is_left_empty_and_the_rest_is_saved(self):
        plan = plans.plan_for(self.atl, SEASON, 1)
        short = self.roster.lineup()[:8]
        problems = plans.fill_plan(
            plan, **self.fields(lineup_vs_lhp=short, bench=[self.roster.starters[0]])
        )
        self.assertIn("Lineup vs LHP: a lineup needs nine batters; this one has 8.", problems)
        self.assertTrue(any("The bench is for non-pitchers" in p for p in problems))
        plan.refresh_from_db()
        self.assertEqual(plan.lineup_vs_lhp, [])
        self.assertEqual(plan.bench, [])
        self.assertEqual(len(plan.lineup_vs_rhp), 9)
        self.assertEqual(plan.rotation, [p.id for p in self.roster.starters])
        self.assertTrue(all(plans.starters(plan).values()))

    def test_days_without_a_legal_starter_are_reported_and_the_others_filled(self):
        # Three starters cannot cover a four-game series inside series rest.
        plan = plans.plan_for(self.atl, SEASON, 1)
        problems = plans.fill_plan(plan, **self.fields(rotation=self.roster.starters[:3]))
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("No legal starter for days "))
        starters = plans.starters(plan)
        self.assertEqual(starters[1], self.roster.starters[0])
        self.assertIsNone(starters[4])

    def test_the_second_half_stays_locked_unless_the_caller_ignores_the_lock(self):
        plan = plans.plan_for(self.atl, SEASON, 2)
        with self.assertRaises(plans.PlanError):
            plans.fill_plan(plan, **self.fields())
        self.assertFalse(models.HalfPlanDay.objects.exists())

        self.assertEqual(plans.fill_plan(plan, ignore_half_lock=True, **self.fields()), [])
        self.assertEqual(sorted(plans.starters(plan)), list(range(82, 163)))
        # The lock itself is unchanged for the normal editing path.
        self.assertFalse(plans.is_open(2))
        with self.assertRaises(plans.PlanError):
            self.roster.file(half=2)
