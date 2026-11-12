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
