# ABOUTME: The computer manager following the depth chart: position starts paced to each hitter's PA share, planned starts in the rotation, and planned bullpen innings.
# ABOUTME: Pacing runs on whole seasons of lineups; the plan, rotation and reliever tests use a real generated schedule.

from collections import Counter

from django.test import SimpleTestCase, TestCase

from tests.plan_fixtures import SEASON, Roster, create_season
from ulmg import computer_manager, depth, depth_pacing, models, plans, sim_game


def card(**positions):
    """A lineup card as stored entries, in the order given."""
    return [{"player": player, "position": position} for position, player in positions.items()]


def full_card(**changes):
    positions = {position: f"{position}-regular" for position in plans.LINEUP_POSITIONS}
    positions.update(changes)
    return [{"player": positions[position], "position": position} for position in plans.LINEUP_POSITIONS]


def play_season(pacer, cards, available=lambda player, position: True):
    """Set a lineup each day from the day's card, as the computer does. Returns the starts by (player, position)."""
    starts = Counter()
    for stored in cards:
        lineup = pacer.choose(stored, available)
        players = [entry["player"] for entry in lineup]
        assert len(set(players)) == len(players), lineup
        assert [entry["position"] for entry in lineup] == [entry["position"] for entry in stored]
        pacer.record(lineup)
        for entry in lineup:
            starts[(entry["player"], entry["position"])] += 1
    return starts


class LineupPacerTest(SimpleTestCase):
    def test_a_position_split_by_plate_appearances_splits_its_starts_the_same_way(self):
        pacer = depth_pacing.LineupPacer({"SS": depth.Allotment(shares={"seager": 236, "griffin": 441}, rest=0)})
        starts = play_season(pacer, [full_card(SS="griffin")] * 162)
        # 236 of 677 plate appearances is 56.5 of 162 starts.
        self.assertIn(starts[("seager", "SS")], (56, 57))
        self.assertEqual(starts[("seager", "SS")] + starts[("griffin", "SS")], 162)

    def test_seager_splits_his_plate_appearances_between_second_and_short(self):
        pacer = depth_pacing.LineupPacer(
            {
                "2B": depth.Allotment(shares={"seager": 200}, rest=477),
                "SS": depth.Allotment(shares={"seager": 236}, rest=441),
            }
        )
        starts = play_season(pacer, [full_card(**{"2B": "wetherholt", "SS": "griffin"})] * 162)
        # 200 and 236 of 677: 47.9 and 56.5 starts. The cards' starters take the rest.
        self.assertIn(starts[("seager", "2B")], (47, 48, 49))
        self.assertIn(starts[("seager", "SS")], (56, 57))
        self.assertEqual(starts[("wetherholt", "2B")], 162 - starts[("seager", "2B")])
        self.assertEqual(starts[("griffin", "SS")], 162 - starts[("seager", "SS")])

    def test_the_days_lineup_card_decides_which_days_a_platoon_shares(self):
        pacer = depth_pacing.LineupPacer({"LF": depth.Allotment(shares={"lefty": 340, "righty": 337}, rest=0)})
        days = []
        for day in range(162):
            vs_left = day % 3 == 0
            days.append(full_card(LF="righty" if vs_left else "lefty"))
        starts = Counter()
        left_days_for_righty = 0
        for stored in days:
            lineup = pacer.choose(stored, lambda player, position: True)
            pacer.record(lineup)
            left_field = lineup[plans.LINEUP_POSITIONS.index("LF")]["player"]
            starts[left_field] += 1
            if stored[plans.LINEUP_POSITIONS.index("LF")]["player"] == "righty" and left_field == "righty":
                left_days_for_righty += 1
        self.assertIn(starts["lefty"], (80, 81, 82))
        # A left-hander starts 54 days. The right-handed bat gets every one of them.
        self.assertEqual(left_days_for_righty, 54)

    def test_a_player_who_cannot_start_today_gives_way_to_the_next_one_filed(self):
        pacer = depth_pacing.LineupPacer({"SS": depth.Allotment(shares={"seager": 600, "griffin": 77}, rest=0)})
        lineup = pacer.choose(full_card(SS="seager"), lambda player, position: player != "seager")
        self.assertEqual(lineup[plans.LINEUP_POSITIONS.index("SS")]["player"], "griffin")

    def test_a_card_starter_moved_to_another_position_leaves_his_spot_to_the_player_he_displaced(self):
        pacer = depth_pacing.LineupPacer({"SS": depth.Allotment(shares={"seager": 677}, rest=0)})
        lineup = pacer.choose(full_card(SS="griffin", DH="seager"), lambda player, position: True)
        by_position = {entry["position"]: entry["player"] for entry in lineup}
        self.assertEqual(by_position["SS"], "seager")
        self.assertEqual(by_position["DH"], "griffin")

    def test_with_nothing_filed_the_card_plays(self):
        pacer = depth_pacing.LineupPacer({})
        stored = full_card()
        self.assertFalse(pacer)
        self.assertEqual(pacer.choose(stored, lambda player, position: True), stored)

    def test_starts_already_made_count_toward_the_split(self):
        pacer = depth_pacing.LineupPacer(
            {"SS": depth.Allotment(shares={"seager": 338, "griffin": 339}, rest=0)},
            counts={("seager", "SS"): 10},
        )
        lineup = pacer.choose(full_card(SS="seager"), lambda player, position: True)
        self.assertEqual(lineup[plans.LINEUP_POSITIONS.index("SS")]["player"], "griffin")


class PlanPacingTest(TestCase):
    """The plan's game sheets read the depth chart, and a played game's lineup counts."""

    @classmethod
    def setUpTestData(cls):
        create_season()
        cls.atl = models.Team.objects.get(abbreviation="ATL")
        cls.roster = Roster(cls.atl)

    def test_the_schedule_shows_a_bench_player_starting_his_share_at_short(self):
        self.roster.file()
        shortstop = self.roster.fielders[plans.LINEUP_POSITIONS.index("SS") - 1]
        utility = self.roster.bench[0]
        chart = depth.ensure(self.atl, SEASON)
        depth.add_player(chart, utility, "SS", 226, False)
        depth.add_player(chart, shortstop, "SS", 451, False)
        rows = plans.plan_rows(plans.find_plan(self.atl, SEASON, 1))
        at_short = Counter()
        for row in rows:
            for player, position in row["side"]["lineup"]:
                if position == "SS":
                    at_short[player.id] += 1
        games = len(rows)
        self.assertAlmostEqual(at_short[utility.id], games * 226 / 677, delta=1)
        self.assertEqual(at_short[utility.id] + at_short[shortstop.id], games)
        paced = [row for row in rows if row["side"]["lineup_paced"]]
        self.assertEqual(len(paced), at_short[utility.id])

    def test_a_played_games_lineup_counts_toward_the_split(self):
        game = plans.half_games(self.atl, SEASON, 1)[1]
        log = models.GameLog.objects.create(game=game)
        side = models.GameEvent.HOME if game.series.home_team_id == self.atl.id else models.GameEvent.AWAY
        utility = self.roster.bench[0]
        models.GameEvent.objects.create(
            log=log,
            sequence=1,
            kind=models.GameEvent.START,
            payload={"lineups": {side: [{"player": utility.id, "position": "SS"}]}},
        )
        self.assertEqual(depth_pacing.position_starts(self.atl, SEASON), Counter({(utility.id, "SS"): 1}))


class PlannedStartsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_season()
        cls.atl = models.Team.objects.get(abbreviation="ATL")
        cls.roster = Roster(cls.atl)

    def test_a_starter_with_planned_starts_passes_his_turn_once_he_has_them(self):
        ace, fifth = self.roster.starters[0], self.roster.starters[4]
        depth.add_player(depth.ensure(self.atl, SEASON), fifth, depth.STARTS, 3, False)
        plan = self.roster.file()
        starts = Counter(starter.id for starter in plans.starters(plan).values() if starter is not None)
        self.assertEqual(starts[fifth.id], 3)
        self.assertGreater(starts[ace.id], 3)
        games = len(plans.half_games(self.atl, SEASON, 1))
        self.assertEqual(sum(starts.values()), games)


class StubPlay:
    def __init__(self, relief_plan):
        self.plan = relief_plan

    def relief_plan(self, side):
        return self.plan


class PlannedBullpenInningsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_season()
        cls.atl = models.Team.objects.get(abbreviation="ATL")
        cls.roster = Roster(cls.atl)

    def throw(self, pitcher, outs, day=1, started=False):
        game = plans.half_games(self.atl, SEASON, 1)[day]
        models.UsageAppearance.objects.create(player=pitcher, game=game, outs=outs, started=started)

    def test_a_reliever_past_his_planned_innings_is_passed_over_while_another_arm_is_free(self):
        setup, middle = self.roster.relievers
        depth.add_player(depth.ensure(self.atl, SEASON), setup, depth.BULLPEN, 2, False)
        self.throw(setup, 6)
        self.throw(setup, 9, day=2, started=True)
        relief = depth_pacing.ReliefPlan(self.atl, SEASON)
        self.assertEqual(relief.thrown[setup.id], 6)
        self.assertEqual(relief.problem(setup), f"{setup.name} has thrown his 2 planned bullpen innings.")
        self.assertIsNone(relief.problem(middle))

        groups = {computer_manager.SIRP: [setup, middle], computer_manager.MIRP: []}
        choice = sim_game.planned_reliever(
            StubPlay(relief), "home", computer_manager.reliever, computer_manager.SIRP, groups, lambda p: None
        )
        self.assertEqual(choice.player, middle)
        self.assertEqual(choice.skipped, [(setup, relief.problem(setup))])

    def test_with_no_other_arm_he_still_pitches(self):
        setup = self.roster.relievers[0]
        depth.add_player(depth.ensure(self.atl, SEASON), setup, depth.BULLPEN, 1, False)
        self.throw(setup, 3)
        relief = depth_pacing.ReliefPlan(self.atl, SEASON)
        groups = {computer_manager.SIRP: [setup]}
        choice = sim_game.planned_reliever(
            StubPlay(relief), "home", computer_manager.reliever, computer_manager.SIRP, groups, lambda p: None
        )
        self.assertEqual(choice.player, setup)
