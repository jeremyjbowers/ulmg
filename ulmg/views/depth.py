# ABOUTME: The season depth chart: plate appearances by position, the 162 starts, and bullpen innings.
# ABOUTME: Anyone can read it. Only the team's owner and the commissioner can file players on it.

from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from ulmg import depth, models, plans, utils
from ulmg.season_paths import bounce, season_url


def _depth_url(team, season):
    return season_url("teams", team.abbreviation.lower(), "depth", season=season)


def _posted_amount(post):
    """The posted number and whether the row is unlimited. A bad number is the string "bad"."""
    unlimited = post.get("unlimited") in ("on", "true", "1")
    if unlimited:
        return 0, True
    raw = (post.get("amount") or "").strip()
    if raw == "":
        return None, False
    try:
        return int(raw), False
    except ValueError:
        return "bad", False


def _player(raw):
    try:
        return models.Player.objects.filter(pk=int(raw)).first()
    except (TypeError, ValueError):
        return None


def _assignment(chart, raw):
    try:
        pk = int(raw)
    except (TypeError, ValueError):
        return None
    return models.DepthAssignment.objects.filter(chart=chart, pk=pk).select_related("player").first()


def _apply(chart, post):
    action = post.get("action")
    if action == "add":
        amount, unlimited = _posted_amount(post)
        depth.add_player(chart, _player(post.get("player")), post.get("bucket"), amount, unlimited)
        return
    if action == "update":
        row = _assignment(chart, post.get("assignment"))
        if row is None:
            raise depth.DepthError(["That row is not on this depth chart."])
        amount, unlimited = _posted_amount(post)
        depth.change_player(row, amount, unlimited)
        return
    if action == "remove":
        row = _assignment(chart, post.get("assignment"))
        if row is None:
            raise depth.DepthError(["That row is not on this depth chart."])
        depth.remove_player(row)
        return
    raise depth.DepthError(["That action is not on the depth chart."])


@never_cache
def team_depth(request, abbreviation, season=None):
    team = get_object_or_404(models.Team, abbreviation__iexact=abbreviation)
    bounced = bounce(request, "teams", team.abbreviation.lower(), "depth", season=season)
    if bounced:
        return bounced
    season = int(season)
    errors = []
    if request.method == "POST":
        if not plans.can_edit(request.user, team):
            return HttpResponseForbidden(
                "Only this team's owner and the commissioner can edit its depth chart."
            )
        chart = depth.ensure(team, season)
        try:
            _apply(chart, request.POST)
        except depth.DepthError as exc:
            errors = exc.errors
        else:
            return redirect(_depth_url(team, season))
    context = utils.build_context(request)
    context.update(
        {
            "team": team,
            "plan_season": season,
            "can_edit": plans.can_edit(request.user, team),
            "depth_chart": depth.describe(team, season),
            "errors": errors,
        }
    )
    return render(request, "team_depth.html", context)
