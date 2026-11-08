# ABOUTME: Public ULMG season pages: the standings with the wild-card race, a team's results, and the league leaders.
# ABOUTME: Readable without logging in, like the schedule; read live from the stored season record on every request.
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from ulmg import models, season_record, usage, utils


def _season(request):
    try:
        return int(request.GET.get("season", ""))
    except ValueError:
        return settings.CURRENT_SEASON


@never_cache
def league_standings(request):
    context = utils.build_context(request)
    season = _season(request)
    context["record_season"] = season
    context["conferences"] = season_record.standings(season)
    return render(request, "standings.html", context)


@never_cache
def team_results(request, abbreviation):
    context = utils.build_context(request)
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    season = _season(request)
    context["team"] = team
    context["record_season"] = season
    context["record"] = season_record.team_record(team, season)
    context["results"] = season_record.team_results(team, season)
    context["penalties"] = usage.penalty_lines(team, season)
    context["overrides"] = season_record.team_overrides(team, season)
    return render(request, "team_results.html", context)


@never_cache
def league_leaders(request):
    context = utils.build_context(request)
    season = _season(request)
    context["record_season"] = season
    context["leaders"] = season_record.leaders(season)
    return render(request, "leaders.html", context)
