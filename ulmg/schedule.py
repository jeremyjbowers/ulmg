# ABOUTME: Draws and stores a ULMG season schedule of 46 slots and 162 games per team.
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
EXTRA_GAME_LENGTH = 1

# Each half runs in the constitution's order: (slot type, slots in the run).
# One extra division game follows the runs.
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
# The first round of each half's first run is also the extra game, played on
# its own after the half's series: A at B and C at D in the first half, B at C
# and D at A in the second. Each team thereby hosts one rival for one extra
# game and visits a different rival for one.
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


def _extra_division_series(all_divisions, half):
    """The half's extra game in every division: the (0, 0) round, one game."""
    series = []
    for division_teams in all_divisions:
        pairs = DIVISION_ROUNDS[half][0][0]
        series += [
            PlannedSeries(home=division_teams[home], road=division_teams[road])
            for road, home in pairs
        ]
    return series


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
    Draw a season of 46 slots (23 per half) for the sixteen teams. Each half
    is the constitution's 22 series, then one extra division game. The same
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
        # The order of the six four-game division rounds is drawn. The extra
        # game keeps the fixed pairs and sits after the half's series.
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
        plan.append(
            PlannedSlot(
                half=half,
                number=number,
                slot_type=DIVISION,
                length=EXTRA_GAME_LENGTH,
                first_day=day,
                series=_extra_division_series(all_divisions, half),
            )
        )
        number += 1
        day += EXTRA_GAME_LENGTH
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


# How many road series the game page lists. The current one counts.
UPCOMING_ROAD_SERIES = 3


def half_game_counts(team, season, half):
    """Played and remaining games in one half, split into home and away."""
    games = [game for game in team_games(team, season) if game.series.slot.half == half]

    def side(home):
        chosen = [game for game in games if (game.series.home_team_id == team.id) == home]
        played = sum(1 for game in chosen if game.is_played)
        return {"played": played, "left": len(chosen) - played}

    return {"home": side(True), "away": side(False)}


def upcoming_road_series(team, season, half, limit=UPCOMING_ROAD_SERIES):
    """
    The next road series in this half that still have an unplayed game, up to
    limit, in day order. Each series lists only its unplayed games. Home
    series are left out: the manager plays the road.
    """
    road = [
        game
        for game in team_games(team, season)
        if game.series.slot.half == half and game.series.road_team_id == team.id
    ]
    grouped = []
    current = None
    for game in road:
        if current is None or current["id"] != game.series_id:
            current = {"id": game.series_id, "opponent": game.series.home_team, "games": []}
            grouped.append(current)
        current["games"].append(game)
    upcoming = []
    for series in grouped:
        left = [game for game in series["games"] if not game.is_played]
        if not left:
            continue
        upcoming.append(
            {
                "opponent": series["opponent"],
                "played": len(series["games"]) - len(left),
                "left": len(left),
                "games": left,
            }
        )
        if len(upcoming) == limit:
            break
    return upcoming
