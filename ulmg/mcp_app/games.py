# ABOUTME: Read-only game results for the MCP API: scores, box scores, standings, sim stats, leaders, team seasons, usage.
# ABOUTME: Serializes what ulmg.season_record and ulmg.box_score already compute for the site's season pages.
from django.db.models import Exists, OuterRef, Q

from ulmg import box_score, models, season_record, usage, utils
from ulmg.mcp_app import serializers

ULMG = models.PlayerStatSeason.ULMG
Event = models.GameEvent

FINAL = "final"
IN_PROGRESS = "in_progress"
SCHEDULED = "scheduled"
ALL = "all"
GAME_STATUSES = (FINAL, IN_PROGRESS, SCHEDULED, ALL)

BATTING = "batting"
PITCHING = "pitching"
STAT_KINDS = (BATTING, PITCHING)

MAX_LIMIT = 2500


class GameReadError(Exception):
    """A read the caller can correct, with a message written here and an HTTP status."""

    status = 400

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class NotFound(GameReadError):
    """A game or team the read names does not exist."""

    status = 404


class BadArgument(GameReadError):
    """An argument out of its allowed values or not a number."""


def _int(value, name):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise BadArgument(f"{name} must be a whole number") from None


def _season(season):
    """The season asked for, else the league season the site's pages use."""
    if season in (None, ""):
        return utils.league_season()
    return _int(season, "season")


def _limit(limit, default):
    return max(1, min(_int(limit or default, "limit"), MAX_LIMIT))


def _team(abbreviation=None, owner=None):
    if abbreviation:
        team = models.Team.objects.filter(abbreviation__iexact=abbreviation.strip()).first()
        if team is None:
            raise NotFound(f"No team {abbreviation}")
        return team
    team = owner.team() if owner else None
    if team is None:
        raise NotFound("No team given and this owner has no team")
    return team


def player_ref(player):
    if player is None:
        return None
    return {
        "id": player.id,
        "name": player.name,
        "position": player.position,
        "team": player.team.abbreviation if player.team_id else None,
    }


# Scores


def _games(season):
    final = Event.objects.filter(log__game=OuterRef("pk"), kind=Event.FINAL)
    return (
        models.ScheduleGame.objects.filter(series__slot__season=season)
        .select_related("series__slot", "series__home_team", "series__road_team")
        .annotate(is_final=Exists(final), has_log=Exists(models.GameLog.objects.filter(game=OuterRef("pk"))))
    )


def _status(game):
    if game.is_final:
        return FINAL
    if game.has_log or game.opened_at is not None:
        return IN_PROGRESS
    return SCHEDULED


def game_brief(game):
    series = game.series
    status = _status(game)
    winner = None
    if status == FINAL and game.home_score != game.road_score:
        winner = (series.home_team if game.home_score > game.road_score else series.road_team).abbreviation
    return {
        "id": game.id,
        "season": series.slot.season,
        "half": series.slot.half,
        "day": game.day,
        "game_in_series": game.game_number,
        "series_type": series.slot.slot_type,
        "status": status,
        "road": serializers.team_brief(series.road_team),
        "home": serializers.team_brief(series.home_team),
        "road_score": game.road_score,
        "home_score": game.home_score,
        "winner": winner,
    }


def list_games(*, season=None, team=None, day_from=None, day_to=None, status=FINAL, limit=200):
    """The season's games in day order with their scores, filtered by team, day range and status."""
    status = status or FINAL
    if status not in GAME_STATUSES:
        raise BadArgument(f"status must be one of {', '.join(GAME_STATUSES)}")
    season = _season(season)
    games = _games(season)
    if team:
        club = _team(team)
        games = games.filter(Q(series__home_team=club) | Q(series__road_team=club))
    if day_from not in (None, ""):
        games = games.filter(day__gte=_int(day_from, "day_from"))
    if day_to not in (None, ""):
        games = games.filter(day__lte=_int(day_to, "day_to"))
    if status == FINAL:
        games = games.filter(is_final=True)
    elif status == IN_PROGRESS:
        games = games.filter(is_final=False).filter(Q(has_log=True) | Q(opened_at__isnull=False))
    elif status == SCHEDULED:
        games = games.filter(is_final=False, has_log=False, opened_at__isnull=True)
    games = games.order_by("day", "series__home_team__abbreviation")[: _limit(limit, 200)]
    return {"season": season, "status": status, "games": [game_brief(g) for g in games]}


# Box score


def _batting_line(line):
    return {
        "player": player_ref(line.player),
        "position": line.notation,
        "substitute": line.substitute,
        "pa": line.pa,
        "ab": line.ab,
        "r": line.r,
        "h": line.h,
        "2b": line.doubles,
        "3b": line.triples,
        "hr": line.hr,
        "rbi": line.rbi,
        "bb": line.bb,
        "so": line.so,
        "sb": line.sb,
        "cs": line.cs,
        "hbp": line.hbp,
        "sf": line.sf,
        "sh": line.sh,
        "gidp": line.gidp,
        "lob": line.lob,
    }


def _batting_totals(totals):
    names = {"doubles": "2b", "triples": "3b"}
    return {names.get(key, key): value for key, value in totals.items()}


def _pitching_line(line):
    return {
        "player": player_ref(line.player),
        "ip": line.ip,
        "outs": line.outs,
        "bf": line.bf,
        "h": line.h,
        "r": line.r,
        "er": line.er,
        "bb": line.bb,
        "so": line.so,
        "hr": line.hr,
        "pitches": line.pitches,
    }


def get_box_score(game_id):
    """A game's box score: line score, batting and pitching lines, decisions and notes. Empty before it opens."""
    game = _games_by_id(game_id)
    log = models.GameLog.objects.filter(game=game).first()
    empty = {
        "game": game_brief(game),
        "final": False,
        "line_score": None,
        "totals": None,
        "batting": None,
        "batting_totals": None,
        "pitching": None,
        "decisions": None,
        "notes": [],
    }
    if log is None:
        return empty
    box = box_score.box_score(log)
    if not box.batting:
        return {**empty, "final": box.final}
    sides = box_score.SIDES
    return {
        "game": game_brief(game),
        "final": box.final,
        "line_score": {"innings": box.innings, **{side: box.line[side] for side in sides}},
        "totals": {side: box.totals[side] for side in sides},
        "batting": {side: [_batting_line(line) for line in box.batting[side]] for side in sides},
        "batting_totals": {side: _batting_totals(box.batting_totals[side]) for side in sides},
        "team_lob": {side: box.team_lob[side] for side in sides},
        "errors": {side: box.error_notes[side] for side in sides},
        "pitching": {side: [_pitching_line(line) for line in box.pitching[side]] for side in sides},
        "decisions": {
            "win": player_ref(box.win),
            "loss": player_ref(box.loss),
            "save": player_ref(box.save),
            "holds": [player_ref(p) for p in box.holds],
        },
        "notes": [{"label": note.label, "text": note.text} for note in box.notes],
    }


def _games_by_id(game_id):
    season = (
        models.ScheduleGame.objects.filter(pk=game_id).values_list("series__slot__season", flat=True).first()
    )
    if season is None:
        raise NotFound(f"No game {game_id}")
    return _games(season).get(pk=game_id)


# Standings and team seasons


def _standing_row(row, records):
    record = records.get(row.team.id)
    return {
        "team": serializers.team_brief(row.team),
        "wins": row.wins,
        "losses": row.losses,
        "pct": row.pct_display,
        "games_behind": row.games_behind_display,
        "wild_card": row.games_out_display,
        "runs_scored": record.runs_scored if record else 0,
        "runs_allowed": record.runs_allowed if record else 0,
        "usage_penalty": row.penalty,
    }


def get_standings(*, season=None):
    """Each conference's divisions with games behind and wild-card games out, and its wild-card race."""
    season = _season(season)
    records = {r.team_id: r for r in models.TeamSeasonRecord.objects.filter(season=season)}
    conferences = []
    for conference in season_record.standings(season):
        conferences.append({
            "name": conference.name,
            "divisions": [
                {"name": d.name, "teams": [_standing_row(row, records) for row in d.rows]}
                for d in conference.divisions
            ],
            "wild_card": [
                {**_standing_row(row, records), "games_out": row.games_out_display, "status": row.status}
                for row in conference.wild_card
            ],
        })
    return {"season": season, "conferences": conferences}


def get_team_season(*, abbreviation=None, season=None, owner=None):
    """One club's season: record, place in the standings, team batting and pitching totals, and every final."""
    season = _season(season)
    team = _team(abbreviation, owner)
    record = season_record.team_record(team, season)
    totals = season_record.team_totals(team, season)
    results = [
        {
            "game_id": r.game.id,
            "day": r.game.day,
            "home": r.is_home,
            "opponent": r.opponent.abbreviation,
            "runs_scored": r.scored,
            "runs_allowed": r.allowed,
            "outcome": r.outcome,
        }
        for r in season_record.team_results(team, season)
    ]
    return {
        "season": season,
        "team": serializers.team_brief(team),
        "record": {
            "wins": record.wins,
            "losses": record.losses,
            "pct": record.pct_display,
            "runs_scored": record.runs_scored,
            "runs_allowed": record.runs_allowed,
        },
        "standing": season_record.team_standing(team, season),
        "totals": {"batting": totals["batting"], "pitching": totals["pitching"]},
        "results": results,
    }


# Sim stats, leaders and usage


def list_sim_stats(
    *, season=None, team=None, player_id=None, kind=None, sort=None, order="desc", min_pa=None, min_ip=None, limit=100
):
    """
    Players' 6-ulmg sim lines for the season. kind keeps players with a
    batting or pitching line and picks which line sort reads.
    """
    if kind not in (None, "") and kind not in STAT_KINDS:
        raise BadArgument(f"kind must be one of {', '.join(STAT_KINDS)}")
    season = _season(season)
    lines = models.PlayerStatSeason.objects.filter(
        season=season, classification=ULMG, is_career=False
    ).select_related("player__team")
    if team:
        lines = lines.filter(player__team=_team(team))
    if player_id not in (None, ""):
        lines = lines.filter(player_id=_int(player_id, "player_id"))
    if kind == BATTING:
        lines = lines.filter(hit_stats__isnull=False)
    elif kind == PITCHING:
        lines = lines.filter(pitch_stats__isnull=False)
    rows = [
        {"player": player_ref(line.player), "batting": line.hit_stats or None, "pitching": line.pitch_stats or None}
        for line in lines
    ]
    if min_pa not in (None, ""):
        floor = _int(min_pa, "min_pa")
        rows = [r for r in rows if r["batting"] and (r["batting"].get("pa") or 0) >= floor]
    if min_ip not in (None, ""):
        floor = usage.innings_to_outs(min_ip)
        rows = [r for r in rows if r["pitching"] and usage.innings_to_outs(r["pitching"].get("ip")) >= floor]

    source = PITCHING if kind == PITCHING else BATTING
    if sort:
        keyed = [r for r in rows if (r[source] or {}).get(sort) is not None]
        missing = [r for r in rows if (r[source] or {}).get(sort) is None]
        keyed.sort(key=lambda r: r[source][sort], reverse=order != "asc")
        rows = keyed + missing
    else:
        rows.sort(key=lambda r: ((r["player"]["team"] or ""), r["player"]["name"] or ""))
    return {"season": season, "kind": kind or None, "sort": sort or None, "players": rows[: _limit(limit, 100)]}


def get_sim_leaders(*, season=None, limit=season_record.LEADERS_SHOWN):
    """The season's leaders in each counting stat the site's leaders page shows."""
    season = _season(season)
    leaders = season_record.leaders(season, limit=_limit(limit, season_record.LEADERS_SHOWN))

    def boards(group):
        return [
            {
                "key": board.key,
                "label": board.label,
                "leaders": [{"player": player_ref(row.player), "value": row.value} for row in board.rows],
            }
            for board in group
        ]

    return {"season": season, "batting": boards(leaders.batting), "pitching": boards(leaders.pitching)}


def get_usage(*, season=None, team=None):
    """Usage against caps: plate appearances, starts and innings, with each player's limits."""
    season = _season(season)
    club = _team(team) if team else None
    rows = []
    for row in season_record.usage_rows(season, club):
        rows.append({
            "player": player_ref(row["player"]),
            "plate_appearances": row["plate_appearances"],
            "plate_appearances_cap": row["plate_appearances_cap"],
            "starts": row["starts"],
            "starts_cap": row["starts_cap"],
            "innings": row["innings"],
            "innings_cap": row["innings_cap"],
            "start_limit_innings": row["start_limit"],
            "relief_limit_innings": row["relief_limit"],
        })
    return {"season": season, "team": serializers.team_brief(club), "players": rows}
