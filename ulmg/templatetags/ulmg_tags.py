from django import template
from decimal import Decimal

register = template.Library()


@register.simple_tag
def play_next_href(team, user, season=None):
    """The next away game this viewer may open, or an empty string when there is none.

    The season is the one on the page. A 2026 schedule still plays 2026 after
    the calendar has rolled to the next league year.
    """
    if team is None or not getattr(user, "is_authenticated", False):
        return ""
    from ulmg import plans, schedule, utils

    owns = utils.get_team_for_owner(utils.get_owner_for_user(user)) == team
    if not owns and not utils.is_sim_tester(user):
        return ""
    if season in (None, ""):
        season = utils.league_season()
    game = schedule.next_unplayed_road_game(team, int(season))
    if game is None or game.series.slot.half not in plans.visible_halves():
        return ""
    return f"/games/{game.id}/"


def _open_road_game(team, season, halves):
    """The next unplayed road game in an open half, or None."""
    from ulmg import schedule

    game = schedule.next_unplayed_road_game(team, season)
    if game is not None and game.series.slot.half not in halves:
        return None
    return game


def _away_is_complete(progress):
    """True once every away game in the counted halves has been played."""
    away = progress["away"]
    return away["scheduled"] > 0 and away["percent"] == 100


def _staff_next(user, own, schedule_team, season, halves, bar_team):
    """A staff user's button for the club whose schedule he is reading.

    None unless he is staff and that club is not already the bar's club.
    done is that club's away schedule at 100%. The game is its next road
    game in an open half, and is absent once that schedule is finished.
    """
    from ulmg import models, schedule

    if not getattr(user, "is_staff", False) or not isinstance(schedule_team, models.Team):
        return None
    if bar_team is not None and bar_team.pk == schedule_team.pk:
        return None
    if isinstance(own, models.Team) and own.pk == schedule_team.pk:
        return None
    progress = schedule.side_progress(schedule_team, season, halves)
    done = _away_is_complete(progress)
    game = None if done else _open_road_game(schedule_team, season, halves)
    return {"team": schedule_team, "game": game, "done": done}


def play_bar_for(user, own, page, season=None, schedule_team=None):
    """The in-season bar for this viewer: his club, or the club a tester is reading.

    None when he has no club to play, or that club has no games in the open halves,
    and he is not staff reading another club's schedule.
    The game is his next road game in an open half. Once his away games are all
    played, away_complete is set and the game is absent so the button can stay.
    staff is the club on the schedule page, for a staff user, when that club is
    not already his bar. season is the one on the page. A 2026 schedule still
    plays 2026 after the calendar rolls.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    from ulmg import models, plans, schedule, utils

    if season in (None, ""):
        season = utils.league_season()
    season = int(season)
    halves = plans.visible_halves()

    team = own if isinstance(own, models.Team) else None
    if team is None:
        page_team = page if isinstance(page, models.Team) else None
        if page_team is not None and utils.is_sim_tester(user):
            team = page_team

    bar = None
    if team is not None:
        progress = schedule.side_progress(team, season, halves)
        if progress["home"]["scheduled"] + progress["away"]["scheduled"] != 0:
            complete = _away_is_complete(progress)
            bar = {
                "team": team,
                "game": None if complete else _open_road_game(team, season, halves),
                "home": progress["home"],
                "away": progress["away"],
                "away_complete": complete,
            }

    staff = _staff_next(user, own, schedule_team, season, halves, bar["team"] if bar else None)
    if bar is None and staff is None:
        return None
    if bar is None:
        bar = {"team": None, "game": None, "home": None, "away": None, "away_complete": False}
    bar["staff"] = staff
    return bar


def _page_season(context):
    """The season the page is about, when it names one. Otherwise the league season."""
    for key in ("record_season", "schedule_season", "plan_season", "league_season"):
        value = context.get(key)
        if value not in (None, ""):
            return value
    return None


@register.inclusion_tag("includes/play_bar.html", takes_context=True)
def play_bar(context):
    """The bar above the player filter. His own club follows him; a tester reads the club on the page.

    On a team's schedule, staff also get that club's next road game.
    """
    schedule_team = context.get("team") if context.get("schedule_season") not in (None, "") else None
    return {
        "bar": play_bar_for(
            context.get("user"),
            context.get("my_team"),
            context.get("team"),
            _page_season(context),
            schedule_team,
        )
    }


@register.filter(name="percents_to_hundreds")
def percents_to_hundreds(value):
    value = float(value)
    return value * 100.0


@register.filter(name="kill_leading_zero")
def kill_leading_zero(value):
    if isinstance(value, Decimal):
        return str(value).replace("0.", ".")

    if isinstance(value, float):
        return str(value).replace("0.", ".")

    if isinstance(value, str):
        return value.replace("0.", ".")

    return value


@register.filter(name="ops_plus")
def ops_plus(hit_stats):
    """Return OPS+ from FanGraphs hit_stats, or derive it from OBP+ and SLG+."""
    if not hit_stats:
        return None

    if isinstance(hit_stats, dict):
        if hit_stats.get("ops_plus") not in (None, ""):
            return hit_stats["ops_plus"]

        obp_plus = hit_stats.get("obp_plus")
        slg_plus = hit_stats.get("slg_plus")
        if obp_plus not in (None, "") and slg_plus not in (None, ""):
            return float(obp_plus) + float(slg_plus) - 100

    return None


@register.filter(name="commafy")
def commafy(n):
    r = []
    for i, c in enumerate(reversed(str(n))):
        if i and (not (i % 3)):
            r.insert(0, ",")
        r.insert(0, c)
    return "".join(r)
