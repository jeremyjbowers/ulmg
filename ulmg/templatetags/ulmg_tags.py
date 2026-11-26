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


def play_bar_for(user, own, page, season=None):
    """The in-season bar for this viewer: his club, or the club a tester is reading.

    None when he has no club to play, or that club has no games in the open halves.
    The game is his next road game in an open half, or None when that half is played out.
    season is the one on the page. A 2026 schedule still plays 2026 after the calendar rolls.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    from ulmg import models, plans, schedule, utils

    team = own if isinstance(own, models.Team) else None
    if team is None:
        page_team = page if isinstance(page, models.Team) else None
        if page_team is None or not utils.is_sim_tester(user):
            return None
        team = page_team
    if season in (None, ""):
        season = utils.league_season()
    season = int(season)
    halves = plans.visible_halves()
    progress = schedule.side_progress(team, season, halves)
    if progress["home"]["scheduled"] + progress["away"]["scheduled"] == 0:
        return None
    game = schedule.next_unplayed_road_game(team, season)
    if game is not None and game.series.slot.half not in halves:
        game = None
    return {"team": team, "game": game, "home": progress["home"], "away": progress["away"]}


def _page_season(context):
    """The season the page is about, when it names one. Otherwise the league season."""
    for key in ("record_season", "schedule_season", "plan_season", "league_season"):
        value = context.get(key)
        if value not in (None, ""):
            return value
    return None


@register.inclusion_tag("includes/play_bar.html", takes_context=True)
def play_bar(context):
    """The bar above the player filter. His own club follows him; a tester reads the club on the page."""
    return {
        "bar": play_bar_for(
            context.get("user"), context.get("my_team"), context.get("team"), _page_season(context)
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
