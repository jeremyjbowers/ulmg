# ABOUTME: Draws and stores a ULMG season schedule of 44 series slots and 162 games per team.
# ABOUTME: Also answers schedule questions: a team's games, played seasons, and the next road game.

import random
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q

from ulmg import models
from ulmg.constants import CONFERENCE_BY_DIVISION

OTHER_CONFERENCE = models.ScheduleSlot.OTHER_CONFERENCE
OTHER_DIVISION = models.ScheduleSlot.OTHER_DIVISION
DIVISION = models.ScheduleSlot.DIVISION

SERIES_LENGTH = {OTHER_CONFERENCE: 4, OTHER_DIVISION: 3, DIVISION: 4}
LONG_SERIES_LENGTH = 5

# Each half runs in the constitution's order: (slot type, slots in the run).
HALF_RUNS = [
    (OTHER_CONFERENCE, 8),
    (OTHER_DIVISION, 4),
    (DIVISION, 3),
    (OTHER_DIVISION, 4),
    (DIVISION, 3),
]

# Division rounds for teams A, B, C, D (0-3) in one division, as (road, home)
# pairs. Each half is two runs of three rounds; in each half every pair of
# rivals meets once at each park and every team is home once or twice per run.
# The first round of each half's first run is the long slot: A at B and C at D
# in the first half, B at C and D at A in the second.
A, B, C, D = 0, 1, 2, 3
DIVISION_ROUNDS = {
    1: (
        [[(A, B), (C, D)], [(C, A), (B, D)], [(D, A), (B, C)]],
        [[(B, A), (D, C)], [(A, C), (D, B)], [(A, D), (C, B)]],
    ),
    2: (
        [[(B, C), (D, A)], [(A, B), (C, D)], [(C, A), (B, D)]],
        [[(C, B), (A, D)], [(B, A), (D, C)], [(A, C), (D, B)]],
    ),
}


class ScheduleError(Exception):
    pass


@dataclass
class PlannedSeries:
    home: object
    road: object


@dataclass
class PlannedSlot:
    half: int
    number: int
    slot_type: str
    length: int
    first_day: int
    series: list = field(default_factory=list)

    @property
    def days(self):
        return list(range(self.first_day, self.first_day + self.length))


def league_alignment(teams):
    """
    Group teams as {conference: [division teams, division teams]}, each list
    of four sorted by abbreviation. Raises ScheduleError unless the league is
    two conferences of two divisions of four.
    """
    divisions = {}
    for team in teams:
        if team.division not in CONFERENCE_BY_DIVISION:
            raise ScheduleError(
                f"{team.abbreviation} has division {team.division!r}, which is not in a conference."
            )
        divisions.setdefault(team.division, []).append(team)

    alignment = {}
    for division in sorted(CONFERENCE_BY_DIVISION):
        division_teams = sorted(divisions.get(division, []), key=lambda t: t.abbreviation)
        if len(division_teams) != 4:
            raise ScheduleError(
                f"The {division} division has {len(division_teams)} teams; a schedule needs four."
            )
        alignment.setdefault(CONFERENCE_BY_DIVISION[division], []).append(division_teams)

    if sorted(len(d) for d in alignment.values()) != [2, 2]:
        raise ScheduleError("A schedule needs two conferences of two divisions.")
    return alignment


def _matching_rounds(first, second, offsets, first_home_on_even):
    """
    Rounds of a perfect matching between two equal groups: in the round for
    offset k, first[i] plays second[(i + k) % n]. first[i] is home when the
    parity of k matches first_home_on_even, so each team is home in half of
    any set of offsets that holds as many even values as odd ones.
    """
    size = len(first)
    rounds = []
    for k in offsets:
        first_home = (k % 2 == 0) == first_home_on_even
        matchups = []
        for i, team in enumerate(first):
            opponent = second[(i + k) % size]
            if first_home:
                matchups.append(PlannedSeries(home=team, road=opponent))
            else:
                matchups.append(PlannedSeries(home=opponent, road=team))
        rounds.append(matchups)
    return rounds


def _other_conference_rounds(rng, east, west, flip):
    """
    Eight rounds for each half. Every East team plays every West team once per
    half, at one park in the first half and at the other in the second.
    """
    by_half = {}
    for half in (1, 2):
        offsets = list(range(8))
        rng.shuffle(offsets)
        by_half[half] = _matching_rounds(east, west, offsets, flip == (half == 1))
    return by_half


def _other_division_rounds(rng, first, second):
    """
    Two runs of four rounds for each half. Each pair meets once per run, at
    one park in the first run and at the other in the second.
    """
    by_half = {}
    for half in (1, 2):
        first_home_on_even = rng.random() < 0.5
        runs = []
        for run_index in range(2):
            offsets = list(range(4))
            rng.shuffle(offsets)
            runs.append(
                _matching_rounds(first, second, offsets, first_home_on_even == (run_index == 0))
            )
        by_half[half] = runs
    return by_half


def _division_rounds(division_teams, half, order):
    """
    The six rounds of one division for a half, in the given order of
    (run, round) template positions, as lists of PlannedSeries.
    """
    labels = division_teams
    rounds = []
    for run_index, round_index in order:
        pairs = DIVISION_ROUNDS[half][run_index][round_index]
        rounds.append(
            [PlannedSeries(home=labels[home], road=labels[road]) for road, home in pairs]
        )
    return rounds


def build_season_plan(teams, seed):
    """
    Draw a season of 44 slots (22 per half) for the sixteen teams. The same
    teams and seed always draw the same schedule.
    """
    alignment = league_alignment(list(teams))
    rng = random.Random(seed)

    # Draw each division's A, B, C, D and each conference's order.
    for conference_divisions in alignment.values():
        for division_teams in conference_divisions:
            rng.shuffle(division_teams)
        rng.shuffle(conference_divisions)
    east_divisions, west_divisions = alignment["East"], alignment["West"]
    east = east_divisions[0] + east_divisions[1]
    west = west_divisions[0] + west_divisions[1]
    rng.shuffle(east)
    rng.shuffle(west)

    other_conference = _other_conference_rounds(rng, east, west, rng.random() < 0.5)
    other_division = [
        _other_division_rounds(rng, *east_divisions),
        _other_division_rounds(rng, *west_divisions),
    ]
    all_divisions = east_divisions + west_divisions

    plan = []
    number = 1
    day = 1
    for half in (1, 2):
        # The long round sits at a drawn position in one of the half's two
        # division runs; the other run holds the reversed rounds.
        division_runs = [[(0, 0), (0, 1), (0, 2)], [(1, 0), (1, 1), (1, 2)]]
        for run in division_runs:
            rng.shuffle(run)
        rng.shuffle(division_runs)
        division_order = division_runs[0] + division_runs[1]
        division_rounds = [_division_rounds(d, half, division_order) for d in all_divisions]

        other_conference_index = 0
        other_division_run = 0
        division_index = 0
        for slot_type, run_length in HALF_RUNS:
            for run_position in range(run_length):
                if slot_type == OTHER_CONFERENCE:
                    series = other_conference[half][other_conference_index]
                    other_conference_index += 1
                    length = SERIES_LENGTH[slot_type]
                elif slot_type == OTHER_DIVISION:
                    series = []
                    for conference_rounds in other_division:
                        series += conference_rounds[half][other_division_run][run_position]
                    length = SERIES_LENGTH[slot_type]
                else:
                    series = []
                    for rounds in division_rounds:
                        series += rounds[division_index]
                    if division_order[division_index] == (0, 0):
                        length = LONG_SERIES_LENGTH
                    else:
                        length = SERIES_LENGTH[slot_type]
                    division_index += 1
                plan.append(
                    PlannedSlot(
                        half=half,
                        number=number,
                        slot_type=slot_type,
                        length=length,
                        first_day=day,
                        series=series,
                    )
                )
                number += 1
                day += length
            if slot_type == OTHER_DIVISION:
                other_division_run += 1
    return plan


def season_games(season):
    return models.ScheduleGame.objects.filter(series__slot__season=season)


def season_has_played_games(season):
    return season_games(season).filter(
        home_score__isnull=False, road_score__isnull=False
    ).exists()


@transaction.atomic
def save_season_plan(season, plan):
    """
    Replace the season's schedule with the plan. Returns the counts of saved
    slots, series and games. Raises ScheduleError once a game is played.
    """
    if season_has_played_games(season):
        raise ScheduleError(f"{season} has played games; its schedule can no longer be regenerated.")
    models.ScheduleSlot.objects.filter(season=season).delete()

    slot_count = series_count = game_count = 0
    for planned in plan:
        slot = models.ScheduleSlot.objects.create(
            season=season,
            half=planned.half,
            number=planned.number,
            slot_type=planned.slot_type,
            length=planned.length,
            first_day=planned.first_day,
        )
        slot_count += 1
        for planned_series in planned.series:
            series = models.ScheduleSeries.objects.create(
                slot=slot,
                home_team=planned_series.home,
                road_team=planned_series.road,
            )
            series_count += 1
            games = [models.ScheduleGame(series=series, day=day) for day in planned.days]
            models.ScheduleGame.objects.bulk_create(games)
            game_count += len(games)
    return slot_count, series_count, game_count


def team_games(team, season):
    """All of a team's games for the season, home and road, in day order."""
    return list(
        season_games(season)
        .filter(Q(series__home_team=team) | Q(series__road_team=team))
        .select_related("series__slot", "series__home_team", "series__road_team")
        .order_by("day")
    )


def next_unplayed_road_game(team, season):
    """The visitor's next unplayed road game in day order, or None."""
    return (
        season_games(season)
        .filter(series__road_team=team)
        .filter(Q(home_score__isnull=True) | Q(road_score__isnull=True))
        .select_related("series__slot", "series__home_team", "series__road_team")
        .order_by("day")
        .first()
    )
