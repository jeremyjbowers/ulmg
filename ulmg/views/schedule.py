# ABOUTME: Public season schedule pages: the league schedule by slot and day, and one team's 162 games.
# ABOUTME: Readable without logging in; shows plan starters, a manager's own road games, Play links and box scores.
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
    games = schedule.team_games(team, season)
    # A tester can play any unplayed game; a manager his own team's next unplayed road game.
    tester = utils.is_sim_tester(request.user)
    owner_team = owner.team() if owner is not None else None
    next_road = schedule.next_unplayed_road_game(owner_team, season) if owner_team else None
    logged = set(models.GameLog.objects.filter(game__in=games).values_list("game_id", flat=True))
    rows = []
    for game in games:
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
                "can_play": not game.is_played and (tester or (next_road is not None and game.id == next_road.id)),
                "has_box": game.is_played and game.id in logged,
            }
        )
    context["rows"] = rows
    return render(request, "team_schedule.html", context)
