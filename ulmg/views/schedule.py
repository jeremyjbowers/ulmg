# ABOUTME: Public season schedule pages: the league schedule by slot and day, and one team's 162 games.
# ABOUTME: Readable without logging in; shows the half plans' starters and marks a manager's own road games.
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from ulmg import models, plans, schedule, utils


def _schedule_season(request):
    try:
        return int(request.GET.get("season", ""))
    except ValueError:
        return settings.CURRENT_SEASON


def _team_result(game, is_home):
    if not game.is_played:
        return "unplayed"
    team_score, opponent_score = (
        (game.home_score, game.road_score) if is_home else (game.road_score, game.home_score)
    )
    if team_score > opponent_score:
        outcome = "W"
    elif team_score < opponent_score:
        outcome = "L"
    else:
        outcome = "T"
    return f"{outcome} {team_score}-{opponent_score}"


@never_cache
def league_schedule(request):
    context = utils.build_context(request)
    season = _schedule_season(request)
    context["schedule_season"] = season
    context["slots"] = list(
        models.ScheduleSlot.objects.filter(season=season).prefetch_related(
            "series__home_team", "series__road_team"
        )
    )
    return render(request, "schedule.html", context)


@never_cache
def team_schedule(request, abbreviation):
    context = utils.build_context(request)
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    season = _schedule_season(request)
    context["team"] = team
    context["schedule_season"] = season

    owner = utils.get_owner_for_user(request.user)
    own_team = owner is not None and owner.team() == team
    context["own_team"] = own_team

    starters = plans.season_starters(season)
    rows = []
    for game in schedule.team_games(team, season):
        is_home = game.series.home_team_id == team.id
        opponent = game.series.road_team if is_home else game.series.home_team
        rows.append(
            {
                "game": game,
                "is_home": is_home,
                "opponent": opponent,
                "starter": starters.get((team.id, game.day)),
                "opponent_starter": starters.get((opponent.id, game.day)),
                "result": _team_result(game, is_home),
                "manager_plays": own_team and not is_home,
            }
        )
    context["rows"] = rows
    return render(request, "team_schedule.html", context)
