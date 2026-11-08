# ABOUTME: The ULMG season record: 6-ulmg PlayerStatSeason lines and TeamSeasonRecord rows, summed from final game logs.
# ABOUTME: Also answers standings with games behind and the wild-card race, a team's results, its overrides and the leaders.

from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q

from ulmg import box_score, models, usage
from ulmg.constants import CONFERENCE_BY_DIVISION

ULMG = models.PlayerStatSeason.ULMG
Event = models.GameEvent

# Constitution, from 2026: each conference sends its two division winners and
# the next two best records.
WILD_CARDS = 2

# Wild-card race places.
IN = "in"
TIED = "tied"
OUT = "out"

# Logs are read this many at a time so a full season never sits in memory at once.
LOG_BATCH = 25

# Counting stats summed from the box score lines, as (stat key, line attribute).
# The keys are the ones live_update_stats_from_fg_stats writes for 1-mlb rows.
BATTING_COUNTS = (
    ("pa", "pa"), ("ab", "ab"), ("r", "r"), ("h", "h"), ("2b", "doubles"), ("3b", "triples"), ("hr", "hr"),
    ("rbi", "rbi"), ("bb", "bb"), ("so", "so"), ("sb", "sb"), ("cs", "cs"), ("gdp", "gidp"), ("sf", "sf"),
    ("hbp", "hbp"), ("sh", "sh"),
)
PITCHING_COUNTS = (
    ("tbf", "bf"), ("h", "h"), ("r", "r"), ("er", "er"), ("bb", "bb"), ("so", "so"), ("hr", "hr"),
    ("pitches", "pitches"),
)

# Leader boards: the counting stats the site shows for MLB lines and teams.
BATTING_LEADERS = (
    ("h", "Hits"), ("2b", "Doubles"), ("3b", "Triples"), ("hr", "Home runs"), ("r", "Runs"), ("rbi", "RBI"),
    ("sb", "Stolen bases"), ("bb", "Walks"), ("so", "Strikeouts"),
)
PITCHING_LEADERS = (
    ("w", "Wins"), ("sv", "Saves"), ("so", "Strikeouts"), ("ip", "Innings"), ("g", "Games"), ("gs", "Starts"),
)
LEADERS_SHOWN = 10


# Final games


def final_logs(season):
    """The season's game logs that reached a final, in day order."""
    return (
        models.GameLog.objects.filter(game__series__slot__season=season, events__kind=Event.FINAL)
        .select_related("game__series__slot", "game__series__home_team", "game__series__road_team")
        .distinct()
        .order_by("game__day", "game_id")
    )


def boxes(logs):
    """(log, box score) for each log, reading each batch's events in one query."""
    logs = list(logs)
    for start in range(0, len(logs), LOG_BATCH):
        batch = logs[start:start + LOG_BATCH]
        events = {log.id: [] for log in batch}
        for event in Event.objects.filter(log__in=batch).order_by("log_id", "sequence"):
            events[event.log_id].append(event)
        for log in batch:
            yield log, box_score.box_score(log, events[log.id])


# Totals


@dataclass
class Totals:
    batting: dict = field(default_factory=dict)
    pitching: dict = field(default_factory=dict)
    records: dict = field(default_factory=dict)
    games: int = 0

    def add(self, box):
        """Add one final game's box score."""
        self.games += 1
        for side in box_score.SIDES:
            for line in box.batting[side]:
                row = self.batting.setdefault(line.player.id, dict.fromkeys(["g"] + [k for k, _ in BATTING_COUNTS], 0))
                row["g"] += 1
                for key, name in BATTING_COUNTS:
                    row[key] += getattr(line, name)
            for index, line in enumerate(box.pitching[side]):
                row = self.pitching.setdefault(
                    line.player.id,
                    dict.fromkeys(["g", "gs", "w", "l", "sv", "outs"] + [k for k, _ in PITCHING_COUNTS], 0),
                )
                row["g"] += 1
                if index == 0:
                    row["gs"] += 1
                row["outs"] += line.outs
                for key, name in PITCHING_COUNTS:
                    row[key] += getattr(line, name)
        for key, player in (("w", box.win), ("l", box.loss), ("sv", box.save)):
            if player is not None:
                self.pitching[player.id][key] += 1

        runs = {side: box.totals[side]["r"] for side in box_score.SIDES}
        for side in box_score.SIDES:
            team = box.teams[side]
            record = self.records.setdefault(team.id, dict(wins=0, losses=0, runs_scored=0, runs_allowed=0))
            scored, allowed = runs[side], runs[box_score.other(side)]
            record["runs_scored"] += scored
            record["runs_allowed"] += allowed
            if scored > allowed:
                record["wins"] += 1
            elif scored < allowed:
                record["losses"] += 1


# A rebuild reports its progress every this many games.
PROGRESS_EVERY = 100


def season_totals(logs, progress=None):
    """The summed lines and records of the logs' final games. progress, if given, gets a line now and then."""
    logs = list(logs)
    totals = Totals()
    for index, (_, box) in enumerate(boxes(logs), start=1):
        if box.final:
            totals.add(box)
        if progress is not None and (index % PROGRESS_EVERY == 0 or index == len(logs)):
            progress(f"{index}/{len(logs)} game logs read")
    return totals


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def hit_stats(row):
    """A hitter's 6-ulmg hit_stats: the summed counts and the site's rate keys."""
    stats = dict(row)
    singles = row["h"] - row["2b"] - row["3b"] - row["hr"]
    total_bases = singles + 2 * row["2b"] + 3 * row["3b"] + 4 * row["hr"]
    stats["1b"] = singles
    stats["avg"] = _ratio(row["h"], row["ab"])
    stats["obp"] = _ratio(row["h"] + row["bb"] + row["hbp"], row["ab"] + row["bb"] + row["hbp"] + row["sf"])
    stats["slg"] = _ratio(total_bases, row["ab"])
    stats["ops"] = None if stats["obp"] is None or stats["slg"] is None else stats["obp"] + stats["slg"]
    stats["iso"] = None if stats["avg"] is None else stats["slg"] - stats["avg"]
    stats["k_pct"] = _ratio(row["so"], row["pa"])
    stats["bb_pct"] = _ratio(row["bb"], row["pa"])
    return stats


def innings(outs):
    """Outs as FanGraphs writes innings, 20 as 6.2."""
    return float(f"{outs // 3}.{outs % 3}")


def pitch_stats(row):
    """A pitcher's 6-ulmg pitch_stats: the summed counts and the site's rate keys, ip as FanGraphs writes it."""
    stats = {key: value for key, value in row.items() if key != "outs"}
    outs = row["outs"]
    nine = 27
    stats["ip"] = innings(outs)
    stats["era"] = _ratio(nine * row["er"], outs)
    stats["whip"] = _ratio(3 * (row["bb"] + row["h"]), outs)
    stats["k_9"] = _ratio(nine * row["so"], outs)
    stats["bb_9"] = _ratio(nine * row["bb"], outs)
    stats["hr_9"] = _ratio(nine * row["hr"], outs)
    stats["h_9"] = _ratio(nine * row["h"], outs)
    stats["k_pct"] = _ratio(row["so"], row["tbf"])
    stats["bb_pct"] = _ratio(row["bb"], row["tbf"])
    return stats


# Writing the record


@dataclass
class RebuildResult:
    season: int
    games: int
    lines_written: int
    lines_deleted: int
    records_written: int
    records_deleted: int
    dry_run: bool

    def describe(self):
        if self.dry_run:
            return (
                f"Dry run for {self.season}: {self.games} final games; would write {self.lines_written} player lines "
                f"and {self.records_written} team records, and delete {self.lines_deleted} lines and "
                f"{self.records_deleted} records. Nothing changed."
            )
        return (
            f"Rebuilt {self.season} from {self.games} final games: wrote {self.lines_written} player lines and "
            f"{self.records_written} team records, deleted {self.lines_deleted} lines and {self.records_deleted} records."
        )


def _write(season, totals, player_ids, team_ids, dry_run):
    """
    Make the season's 6-ulmg lines and records for the given players and
    teams (every one of the season's when None) match the totals.
    """
    lines = models.PlayerStatSeason.objects.filter(season=season, classification=ULMG, is_career=False)
    records = models.TeamSeasonRecord.objects.filter(season=season)
    if player_ids is not None:
        lines = lines.filter(player_id__in=player_ids)
    if team_ids is not None:
        records = records.filter(team_id__in=team_ids)

    played = set(totals.batting) | set(totals.pitching)
    if player_ids is not None:
        played &= set(player_ids)
    teams = set(totals.records) if team_ids is None else set(totals.records) & set(team_ids)
    stale_lines = lines.exclude(player_id__in=played)
    stale_records = records.exclude(team_id__in=teams)
    result = dict(
        lines_written=len(played),
        lines_deleted=stale_lines.count(),
        records_written=len(teams),
        records_deleted=stale_records.count(),
    )
    if dry_run:
        return result

    stale_lines.delete()
    stale_records.delete()
    for pid in played:
        batting, pitching = totals.batting.get(pid), totals.pitching.get(pid)
        models.PlayerStatSeason.objects.update_or_create(
            player_id=pid,
            season=season,
            classification=ULMG,
            is_career=False,
            defaults={
                "hit_stats": hit_stats(batting) if batting else None,
                "pitch_stats": pitch_stats(pitching) if pitching else None,
            },
        )
    for team_id in teams:
        models.TeamSeasonRecord.objects.update_or_create(
            team_id=team_id, season=season, defaults=totals.records[team_id]
        )
    return result


@transaction.atomic
def rebuild_season(season, dry_run=False, progress=None):
    """Rebuild every 6-ulmg line and team record of the season from its final game logs."""
    totals = season_totals(final_logs(season), progress)
    result = _write(season, totals, None, None, dry_run)
    return RebuildResult(season=season, games=totals.games, dry_run=dry_run, **result)


def record_final(log):
    """
    Bring the season record up to date for a game that just became final:
    every line of a player in the game and both teams' records are summed
    again from all of their final games' logs.
    """
    game = log.game
    season = game.series.slot.season
    teams = [game.series.home_team_id, game.series.road_team_id]
    box = box_score.box_score(log)
    players = {line.player.id for side in box_score.SIDES for line in box.batting[side] + box.pitching[side]}
    # The games each of these players appeared in, and every game of both teams.
    games = Q(game__series__home_team_id__in=teams) | Q(game__series__road_team_id__in=teams)
    appeared = models.UsageAppearance.objects.filter(player_id__in=players).values("game_id")
    logs = final_logs(season).filter(games | Q(game_id__in=appeared) | Q(pk=log.pk))
    totals = season_totals(logs)
    _write(season, totals, players, teams, dry_run=False)


# Standings


@dataclass
class StandingRow:
    team: object
    wins: int
    losses: int
    games_behind: float = 0
    tied_for_lead: bool = False
    tied_for_division_lead: bool = False
    status: str = None
    # "20" or "10": the worst usage penalty line one of the club's players is over.
    penalty: str = None

    @property
    def pct(self):
        games = self.wins + self.losses
        return self.wins / games if games else 0.0

    @property
    def pct_display(self):
        return models.TeamSeasonRecord.format_pct(self.wins, self.losses)

    @property
    def games_behind_display(self):
        if self.games_behind == 0:
            return "-"
        text = f"{abs(self.games_behind):g}"
        return f"+{text}" if self.games_behind < 0 else text

    def same_record(self, other):
        """Tied: the same winning percentage and the same wins minus losses."""
        return self.wins * (other.wins + other.losses) == other.wins * (self.wins + self.losses) and (
            self.wins - self.losses == other.wins - other.losses
        )


def games_behind(leader, row):
    return ((leader.wins - row.wins) + (row.losses - leader.losses)) / 2


def _ranked(rows):
    return sorted(rows, key=lambda r: (-r.pct, -(r.wins - r.losses), r.team.abbreviation))


@dataclass
class Division:
    name: str
    rows: list

    @property
    def outright_leader(self):
        """The division's leader, or None when its lead is tied."""
        leaders = [row for row in self.rows if row.tied_for_lead]
        return None if leaders else (self.rows[0] if self.rows else None)


@dataclass
class Conference:
    name: str
    divisions: list
    wild_card: list


def _division(name, rows):
    rows = _ranked(rows)
    if rows:
        leader = rows[0]
        tied = [row for row in rows if row.same_record(leader)]
        for row in rows:
            row.games_behind = games_behind(leader, row)
            row.tied_for_lead = len(tied) > 1 and row in tied
    return Division(name, rows)


def _wild_card(divisions):
    """
    Everyone but the outright division winners, in record order. The places
    open are the two wild cards plus one for each division whose lead is
    tied. Teams level with the last place, when there are more of them than
    places left, are shown as tied for it.
    """
    race = []
    places = WILD_CARDS
    for division in divisions:
        leader = division.outright_leader
        if leader is None and division.rows:
            places += 1
        for row in division.rows:
            if row is leader:
                continue
            race.append(
                StandingRow(
                    row.team, row.wins, row.losses, tied_for_division_lead=row.tied_for_lead, penalty=row.penalty
                )
            )
    race = _ranked(race)
    if not race:
        return race
    cutoff = race[min(places, len(race)) - 1]
    ahead = [row for row in race if not row.same_record(cutoff) and race.index(row) < race.index(cutoff)]
    level = [row for row in race if row.same_record(cutoff)]
    for row in race:
        row.games_behind = games_behind(cutoff, row)
        if row in ahead:
            row.status = IN
        elif row in level:
            row.status = IN if len(ahead) + len(level) <= places else TIED
        else:
            row.status = OUT
    return race


def standings(season):
    """Each conference's divisions, with games behind, and its wild-card race."""
    records = {r.team_id: r for r in models.TeamSeasonRecord.objects.filter(season=season)}
    flags = penalty_flags(season)
    by_division = {}
    for team in models.Team.objects.filter(division__in=CONFERENCE_BY_DIVISION):
        record = records.get(team.id)
        row = StandingRow(
            team, record.wins if record else 0, record.losses if record else 0, penalty=flags.get(team.id)
        )
        by_division.setdefault(team.division, []).append(row)

    conferences = {}
    for division_name, conference_name in CONFERENCE_BY_DIVISION.items():
        division = _division(division_name, by_division.get(division_name, []))
        conferences.setdefault(conference_name, []).append(division)
    return [
        Conference(name, divisions, _wild_card(divisions))
        for name, divisions in sorted(conferences.items())
    ]


# Usage penalties


def penalty_flags(season):
    """{team id: "20" or "10"}: the worst usage penalty line any of a club's players is over."""
    flags = {}
    for team in models.Team.objects.all():
        lines = usage.penalty_lines(team, season)
        if lines.players_over_20:
            flags[team.id] = "20"
        elif lines.players_over_10:
            flags[team.id] = "10"
    return flags


def team_overrides(team, season):
    """The commissioner's approved usage overrides for the club's players this season."""
    return (
        models.UsageOverride.objects.filter(
            player__team=team, game__series__slot__season=season, approved_by__isnull=False
        )
        .select_related("player", "game__series__home_team", "game__series__road_team")
        .order_by("game__day", "player__name")
    )


# A team's season


def team_record(team, season):
    """The club's stored record, or an unsaved 0-0 one before its first final."""
    record = models.TeamSeasonRecord.objects.filter(team=team, season=season).first()
    return record or models.TeamSeasonRecord(team=team, season=season)


@dataclass
class Result:
    game: object
    is_home: bool
    opponent: object
    scored: int
    allowed: int

    @property
    def outcome(self):
        if self.scored > self.allowed:
            return "W"
        if self.scored < self.allowed:
            return "L"
        return "T"

    @property
    def display(self):
        return f"{self.outcome} {self.scored}-{self.allowed}"


def team_results(team, season):
    """Every final game of the club's season, in day order, with its score."""
    logs = final_logs(season).filter(Q(game__series__home_team=team) | Q(game__series__road_team=team))
    results = []
    for log in logs:
        game = log.game
        is_home = game.series.home_team_id == team.id
        opponent = game.series.road_team if is_home else game.series.home_team
        scored, allowed = (
            (game.home_score, game.road_score) if is_home else (game.road_score, game.home_score)
        )
        results.append(Result(game, is_home, opponent, scored, allowed))
    return results


# Leaders


@dataclass
class LeaderRow:
    player: object
    value: object


@dataclass
class Board:
    key: str
    label: str
    rows: list


@dataclass
class Leaders:
    batting: list
    pitching: list


def _board(lines, attribute, key, label, limit):
    rows = []
    for line in lines:
        stats = getattr(line, attribute) or {}
        value = stats.get(key)
        if value:
            rows.append(LeaderRow(line.player, value))
    rows.sort(key=lambda r: (-r.value, r.player.name or ""))
    return Board(key, label, rows[:limit])


def leaders(season, limit=LEADERS_SHOWN):
    """The season's leaders in each counting stat, from its 6-ulmg lines."""
    lines = list(
        models.PlayerStatSeason.objects.filter(season=season, classification=ULMG, is_career=False).select_related(
            "player__team"
        )
    )
    return Leaders(
        batting=[_board(lines, "hit_stats", key, label, limit) for key, label in BATTING_LEADERS],
        pitching=[_board(lines, "pitch_stats", key, label, limit) for key, label in PITCHING_LEADERS],
    )


def player_line(player, season):
    """The player's 6-ulmg line for the season, or None."""
    return models.PlayerStatSeason.objects.filter(
        player=player, season=season, classification=ULMG, is_career=False
    ).first()
