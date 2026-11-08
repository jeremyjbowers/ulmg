# ABOUTME: Unit tests for the season schedule draw in ulmg.schedule.
# ABOUTME: Proves the slot structure, home/road balance, pair totals and long-slot cycle for many seeds.

from collections import Counter, defaultdict

from django.test import TestCase

from ulmg import schedule
from ulmg.constants import CONFERENCE_BY_DIVISION
from tests.schedule_fixtures import create_league_teams

SEEDS = range(25)

EXPECTED_HALF_SEQUENCE = (
    ["other_conference"] * 8
    + ["other_division"] * 4
    + ["division"] * 3
    + ["other_division"] * 4
    + ["division"] * 3
)

# The runs of slots within a half: (first index, last index + 1).
HALF_RUNS = [(0, 8), (8, 12), (12, 15), (15, 19), (19, 22)]


def conference(team):
    return CONFERENCE_BY_DIVISION[team.division]


def pair_key(a, b):
    return tuple(sorted([a.abbreviation, b.abbreviation]))


class ConferenceMapTestCase(TestCase):
    def test_every_division_maps_to_a_conference(self):
        self.assertEqual(
            CONFERENCE_BY_DIVISION,
            {
                "Rickey": "East",
                "Fernandez": "East",
                "Ringen": "West",
                "Orzol": "West",
            },
        )


class SchedulePlanTestCase(TestCase):
    def setUp(self):
        self.teams = create_league_teams()
        self.plans = {seed: schedule.build_season_plan(self.teams, seed) for seed in SEEDS}

    def test_forty_four_slots_with_season_numbers(self):
        for plan in self.plans.values():
            self.assertEqual([s.number for s in plan], list(range(1, 45)))
            self.assertEqual([s.half for s in plan], [1] * 22 + [2] * 22)

    def test_slot_structure_and_order_in_both_halves(self):
        for plan in self.plans.values():
            for half in (1, 2):
                slots = [s for s in plan if s.half == half]
                self.assertEqual([s.slot_type for s in slots], EXPECTED_HALF_SEQUENCE)
                lengths = [s.length for s in slots]
                self.assertEqual(lengths[:8], [4] * 8)
                self.assertEqual(lengths[8:12], [3] * 4)
                self.assertEqual(lengths[15:19], [3] * 4)
                division_lengths = lengths[12:15] + lengths[19:22]
                self.assertEqual(sorted(division_lengths), [4, 4, 4, 4, 4, 5])
                self.assertEqual(sum(lengths), 81)

    def test_days_run_one_through_162_without_gaps(self):
        for plan in self.plans.values():
            day = 1
            for slot in plan:
                self.assertEqual(slot.first_day, day)
                self.assertEqual(slot.days, list(range(day, day + slot.length)))
                day += slot.length
            self.assertEqual(day, 163)

    def test_every_team_plays_exactly_once_in_every_slot(self):
        abbreviations = sorted(t.abbreviation for t in self.teams)
        for plan in self.plans.values():
            for slot in plan:
                self.assertEqual(len(slot.series), 8)
                playing = [s.home.abbreviation for s in slot.series] + [
                    s.road.abbreviation for s in slot.series
                ]
                self.assertEqual(sorted(playing), abbreviations)

    def test_matchups_fit_the_slot_type(self):
        for plan in self.plans.values():
            for slot in plan:
                for series in slot.series:
                    same_division = series.home.division == series.road.division
                    same_conference = conference(series.home) == conference(series.road)
                    if slot.slot_type == "other_conference":
                        self.assertFalse(same_conference)
                    elif slot.slot_type == "other_division":
                        self.assertTrue(same_conference)
                        self.assertFalse(same_division)
                    else:
                        self.assertTrue(same_division)

    def test_162_games_81_home_81_away_for_every_team(self):
        for plan in self.plans.values():
            home = Counter()
            road = Counter()
            for slot in plan:
                for series in slot.series:
                    home[series.home.abbreviation] += slot.length
                    road[series.road.abbreviation] += slot.length
            for team in self.teams:
                self.assertEqual(home[team.abbreviation], 81)
                self.assertEqual(road[team.abbreviation], 81)

    def test_40_or_41_road_games_per_team_per_half(self):
        for plan in self.plans.values():
            for half in (1, 2):
                road = Counter()
                total = Counter()
                for slot in plan:
                    if slot.half != half:
                        continue
                    for series in slot.series:
                        road[series.road.abbreviation] += slot.length
                        total[series.road.abbreviation] += slot.length
                        total[series.home.abbreviation] += slot.length
                for team in self.teams:
                    self.assertIn(road[team.abbreviation], (40, 41))
                    self.assertEqual(total[team.abbreviation], 81)

    def test_home_counts_per_slot_type_per_half(self):
        expected = {"other_conference": 4, "other_division": 4, "division": 3}
        for plan in self.plans.values():
            for half in (1, 2):
                home = defaultdict(Counter)
                for slot in plan:
                    if slot.half != half:
                        continue
                    for series in slot.series:
                        home[series.home.abbreviation][slot.slot_type] += 1
                for team in self.teams:
                    self.assertEqual(dict(home[team.abbreviation]), expected)

    def test_home_in_half_of_each_run(self):
        for plan in self.plans.values():
            for half in (1, 2):
                slots = [s for s in plan if s.half == half]
                for start, end in HALF_RUNS:
                    run = slots[start:end]
                    home = Counter()
                    for slot in run:
                        for series in slot.series:
                            home[series.home.abbreviation] += 1
                    for team in self.teams:
                        count = home[team.abbreviation]
                        # An odd run of three slots splits as one and two.
                        self.assertIn(count, (len(run) // 2, (len(run) + 1) // 2))

    def test_every_pair_home_and_away_totals(self):
        for plan in self.plans.values():
            # (home, road) -> list of (half, length)
            meetings = defaultdict(list)
            for slot in plan:
                for series in slot.series:
                    meetings[(series.home.abbreviation, series.road.abbreviation)].append(
                        (slot.half, slot.length)
                    )
            for a in self.teams:
                for b in self.teams:
                    if a.abbreviation >= b.abbreviation:
                        continue
                    a_home = meetings[(a.abbreviation, b.abbreviation)]
                    b_home = meetings[(b.abbreviation, a.abbreviation)]
                    games = sum(length for _, length in a_home + b_home)
                    if conference(a) != conference(b):
                        # Once per half, one park each half.
                        self.assertEqual(len(a_home), 1)
                        self.assertEqual(len(b_home), 1)
                        self.assertNotEqual(a_home[0][0], b_home[0][0])
                        self.assertEqual(games, 8)
                    elif a.division != b.division:
                        # Two home and two away, one of each per half.
                        self.assertEqual(sorted(h for h, _ in a_home), [1, 2])
                        self.assertEqual(sorted(h for h, _ in b_home), [1, 2])
                        self.assertEqual(games, 12)
                    else:
                        # Rivals meet twice per half, once at each park.
                        self.assertEqual(sorted(h for h, _ in a_home), [1, 2])
                        self.assertEqual(sorted(h for h, _ in b_home), [1, 2])
                        self.assertIn(games, (16, 17))

    def test_each_team_plays_its_division_rivals_50_games(self):
        for plan in self.plans.values():
            games = Counter()
            for slot in plan:
                if slot.slot_type != "division":
                    continue
                for series in slot.series:
                    games[series.home.abbreviation] += slot.length
                    games[series.road.abbreviation] += slot.length
            for team in self.teams:
                self.assertEqual(games[team.abbreviation], 50)

    def test_long_slots_form_a_cycle_in_every_division(self):
        for plan in self.plans.values():
            long_slots = [s for s in plan if s.length == 5]
            self.assertEqual([s.half for s in long_slots], [1, 2])
            self.assertTrue(all(s.slot_type == "division" for s in long_slots))
            for division in CONFERENCE_BY_DIVISION:
                # Each team's visit in the first long slot, then in the second.
                visits = []
                for slot in long_slots:
                    visits.append(
                        {
                            s.road.abbreviation: s.home.abbreviation
                            for s in slot.series
                            if s.home.division == division
                        }
                    )
                first, second = visits
                self.assertEqual(len(first), 2)
                self.assertEqual(len(second), 2)
                # A at B and C at D, then B at C and D at A.
                (a, b), (c, d) = sorted(first.items())
                if second.get(b) != c:
                    (c, d), (a, b) = (a, b), (c, d)
                self.assertEqual(second, {b: c, d: a})
                # Every team visits one rival for five and hosts one for five.
                visitors = list(first) + list(second)
                hosts = list(first.values()) + list(second.values())
                self.assertEqual(sorted(visitors), sorted({a, b, c, d}))
                self.assertEqual(sorted(hosts), sorted({a, b, c, d}))

    def test_same_seed_draws_the_same_schedule(self):
        def flatten(plan):
            return [
                (s.number, s.length, [(x.home.abbreviation, x.road.abbreviation) for x in s.series])
                for s in plan
            ]

        again = schedule.build_season_plan(self.teams, 7)
        self.assertEqual(flatten(again), flatten(self.plans[7]))
        self.assertNotEqual(flatten(self.plans[7]), flatten(self.plans[8]))

    def test_rejects_a_league_without_four_divisions_of_four(self):
        with self.assertRaises(schedule.ScheduleError):
            schedule.build_season_plan(self.teams[:15], 1)
