# ABOUTME: Public ULMG season pages: standings, a team's results and stats, the leaders, and usage.
# ABOUTME: Readable without logging in, like the schedule; the year is a path and the pages read the stored record.
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from ulmg import models, plans, season_record, usage, utils
from ulmg.season_paths import bounce


@never_cache
def league_standings(request, season=None):
    bounced = bounce(request, "standings", season=season)
    if bounced:
        return bounced
    season = int(season)
    context = utils.build_context(request)
    context["record_season"] = season
    context["conferences"] = season_record.standings(season)
    return render(request, "standings.html", context)


@never_cache
def team_results(request, abbreviation, season=None):
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    bounced = bounce(request, "teams", team.abbreviation.lower(), "results", season=season)
    if bounced:
        return bounced
    season = int(season)
    context = utils.build_context(request)
    context["team"] = team
    context["record_season"] = season
    context["can_edit"] = plans.can_edit(request.user, team)
    context["record"] = season_record.team_record(team, season)
    context["results"] = season_record.team_results(team, season)
    context["penalties"] = usage.penalty_lines(team, season)
    context["overrides"] = season_record.team_overrides(team, season)
    return render(request, "team_results.html", context)


@never_cache
def league_leaders(request, season=None):
    bounced = bounce(request, "leaders", season=season)
    if bounced:
        return bounced
    season = int(season)
    context = utils.build_context(request)
    context["record_season"] = season
    context["leaders"] = season_record.leaders(season)
    return render(request, "leaders.html", context)


@never_cache
def team_stats(request, abbreviation, season=None):
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    bounced = bounce(request, "teams", team.abbreviation.lower(), "stats", season=season)
    if bounced:
        return bounced
    season = int(season)
    context = utils.build_context(request)
    context["team"] = team
    context["record_season"] = season
    context["standing"] = season_record.team_standing(team, season)
    context["totals"] = season_record.team_totals(team, season)
    return render(request, "team_stats.html", context)


@never_cache
def league_usage(request, season=None):
    bounced = bounce(request, "usage", season=season)
    if bounced:
        return bounced
    season = int(season)
    context = utils.build_context(request)
    context["record_season"] = season
    context["rows"] = season_record.usage_rows(season)
    return render(request, "usage.html", context)


@never_cache
def team_usage(request, abbreviation, season=None):
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    bounced = bounce(request, "teams", team.abbreviation.lower(), "usage", season=season)
    if bounced:
        return bounced
    season = int(season)
    context = utils.build_context(request)
    context["team"] = team
    context["record_season"] = season
    context["rows"] = season_record.usage_rows(season, team)
    return render(request, "team_usage.html", context)
