# ABOUTME: The league's run environment against the engine's: runs, hits and the spread of scoring, from final games.
# ABOUTME: The expected numbers are engine/fixtures/run_environment.json, which the engine's calibration test keeps current.

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ulmg import models, season_record

FIXTURE = Path(__file__).resolve().parent.parent / "engine" / "fixtures" / "run_environment.json"

# A team's runs in one game, bucketed as the fixture's team_runs_shares are.
BUCKET_LABELS = [str(runs) for runs in range(11)] + ["11+"]

# A metric is called above or below expected when it is more than this many standard errors away.
STANDARD_ERRORS = 2

SIX_RUNS = 6

WITHIN = "within"
ABOVE = "above"
BELOW = "below"

# Counting stats summed from the season's 6-ulmg batting lines, as (metric key, label, stat key, fixture key).
COUNTING = (
    ("hits", "Hits", "h", "hits_per_team"),
    ("home_runs", "Home runs", "hr", "home_runs_per_team"),
    ("walks", "Walks", "bb", "walks_per_team"),
    ("strikeouts", "Strikeouts", "so", "strikeouts_per_team"),
)


@lru_cache(maxsize=1)
def expected():
    """The engine's league-average run environment."""
    with open(FIXTURE) as handle:
        return json.load(handle)


@dataclass
class Metric:
    key: str
    label: str
    actual: float
    expected: float
    margin: float
    share: bool = False

    @property
    def low(self):
        return self.expected - self.margin

    @property
    def high(self):
        return self.expected + self.margin

    def _display(self, value):
        if self.share:
            return f"{value * 100:.1f}%"
        return f"{value:.2f}"

    @property
    def actual_display(self):
        return self._display(self.actual)

    @property
    def expected_display(self):
        return self._display(self.expected)

    @property
    def range_display(self):
        return f"{self._display(max(self.low, 0))} to {self._display(self.high)}"

    @property
    def verdict(self):
        if self.actual > self.high:
            return ABOVE
        if self.actual < self.low:
            return BELOW
        return WITHIN


@dataclass
class Bucket:
    label: str
    count: int
    actual: float
    expected: float
    expected_count: float


    @property
    def actual_width(self):
        """Bar width in percent, a 20% share filling the bar."""
        return min(round(self.actual * 500), 100)

    @property
    def expected_width(self):
        return min(round(self.expected * 500), 100)


@dataclass
class TeamRow:
    team: object
    games: int
    scored: float
    allowed: float


@dataclass
class Report:
    season: int
    games: int
    team_games: int
    metrics: list
    distribution: list
    teams: list
    expected: dict


def _share_margin(p, n):
    return STANDARD_ERRORS * math.sqrt(p * (1 - p) / n)


def _team_runs(season):
    """Each team's runs in each final game, and the number of games with both teams at six or more."""
    runs = []
    both_six = 0
    for log in season_record.final_logs(season):
        game = log.game
        runs.extend([game.road_score, game.home_score])
        both_six += game.road_score >= SIX_RUNS and game.home_score >= SIX_RUNS
    return runs, both_six


def _batting_totals(season):
    rows = models.PlayerStatSeason.objects.filter(season=season, classification=season_record.ULMG, is_career=False)
    totals = {stat: 0 for _, _, stat, _ in COUNTING}
    for row in rows:
        for stat in totals:
            totals[stat] += int((row.hit_stats or {}).get(stat) or 0)
    return totals


def _metrics(runs, both_six, batting, base):
    team_games = len(runs)
    games = team_games // 2
    metrics = [
        Metric(
            "runs", "Runs", sum(runs) / team_games, base["runs_per_team"],
            STANDARD_ERRORS * base["runs_sd"] / math.sqrt(team_games),
        )
    ]
    # A team's count of these in a game is close to Poisson, so its standard error is sqrt(mean / n).
    for key, label, stat, fixture_key in COUNTING:
        mean = base[fixture_key]
        metrics.append(
            Metric(key, label, batting[stat] / team_games, mean, STANDARD_ERRORS * math.sqrt(mean / team_games))
        )
    six = sum(r >= SIX_RUNS for r in runs)
    metrics.append(
        Metric(
            "team_six_plus", "A team scores 6+", six / team_games, base["team_six_plus"],
            _share_margin(base["team_six_plus"], team_games), share=True,
        )
    )
    metrics.append(
        Metric(
            "both_six_plus", "Both teams score 6+", both_six / games, base["both_six_plus"],
            _share_margin(base["both_six_plus"], games), share=True,
        )
    )
    return metrics


def _distribution(runs, base):
    team_games = len(runs)
    counts = [0] * len(BUCKET_LABELS)
    for r in runs:
        counts[min(r, len(BUCKET_LABELS) - 1)] += 1
    return [
        Bucket(label, count, count / team_games, share, share * team_games)
        for label, count, share in zip(BUCKET_LABELS, counts, base["team_runs_shares"])
    ]


def _teams(season):
    rows = []
    records = models.TeamSeasonRecord.objects.filter(season=season).select_related("team")
    for record in records.order_by("team__abbreviation"):
        games = record.wins + record.losses
        if games:
            rows.append(TeamRow(record.team, games, record.runs_scored / games, record.runs_allowed / games))
    return rows


def report(season):
    """The season's run environment from its final games, against the engine's league-average games."""
    base = expected()
    runs, both_six = _team_runs(season)
    if not runs:
        return Report(season, 0, 0, [], [], [], base)
    return Report(
        season=season,
        games=len(runs) // 2,
        team_games=len(runs),
        metrics=_metrics(runs, both_six, _batting_totals(season), base),
        distribution=_distribution(runs, base),
        teams=_teams(season),
        expected=base,
    )
