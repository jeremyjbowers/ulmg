# ABOUTME: The team Game page, and roster moves made from it: one call-up and one send-down as a single move.
# ABOUTME: The move page offers the legal partners for one player. Only the owner and the commissioner can move.
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from ulmg import models, plans, roster_moves, utils


def _posted_player(request, name):
    value = request.POST.get(name, "")
    return models.Player.objects.filter(pk=int(value)).first() if value.isdigit() else None


def game_url(team):
    return f"/teams/{team.abbreviation.lower()}/game/#roster-moves"


def _own_team(user, team):
    owner = utils.get_owner_for_user(user)
    own_team = owner is not None and owner.team() == team
    if getattr(user, "is_superuser", False):
        own_team = True
    return own_team


@never_cache
def team_game(request, abbreviation):
    """
    The team's game page: the four stretches of the season, the home roster
    the half opened with, and the away roster a call-up changes.
    """
    team = get_object_or_404(models.Team, abbreviation__iexact=abbreviation)
    season, half = settings.CURRENT_SEASON, plans.current_half()
    started = roster_moves.half_has_started(season, half)
    rosters = roster_moves.HalfRosters(team, season, half)
    can_edit = plans.can_edit(request.user, team)
    context = utils.build_context(request)
    context.update(
        {
            "team": team,
            "own_team": _own_team(request.user, team),
            "half_started": started,
            "move_half": half,
            "periods": roster_moves.play_periods(season),
            "home_roster": models.Player.objects.filter(id__in=rosters.home).order_by("name"),
            "away_roster": models.Player.objects.filter(id__in=rosters.road).order_by("name"),
            "call_up_pool": models.Player.objects.filter(
                team=team, is_ulmg_aaa_roster=True, is_ulmg_mlb_roster=False
            ).order_by("name"),
            "moves_per_half": roster_moves.MOVES_PER_HALF,
            "moves_left": roster_moves.moves_left(team, season, half),
            "active_stays": roster_moves.active_stays(team, season),
            "move_log": roster_moves.move_log(team, season),
            "can_edit": can_edit,
            "can_move": can_edit and started,
        }
    )
    if context["can_move"]:
        context["call_up_choices"] = context["call_up_pool"]
        context["send_down_choices"] = context["away_roster"]
    return render(request, "team_game.html", context)


@never_cache
@login_required
@require_POST
def team_roster_move(request, abbreviation):
    team = get_object_or_404(models.Team, abbreviation__iexact=abbreviation)
    if not plans.can_edit(request.user, team):
        return HttpResponseForbidden("Only this team's owner and the commissioner can make its roster moves.")

    player_up = _posted_player(request, "player_up")
    player_down = _posted_player(request, "player_down")
    if player_up is None or player_down is None:
        messages.error(request, "Pick a player to call up and a player to send down.")
        return redirect(game_url(team))

    try:
        roster_moves.make_move(
            team,
            player_up,
            player_down,
            season=settings.CURRENT_SEASON,
            half=plans.current_half(),
            user=request.user,
        )
    except roster_moves.MoveError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Called up {player_up.name} and sent down {player_down.name}.")
    return redirect(game_url(team))


@never_cache
@login_required
@require_GET
def team_roster_move_choice(request, abbreviation):
    """
    A move started from one player: `?down=<id>` for a 30-man player, `?up=<id>`
    for an AAA player. Offers the players make_move would accept with him, and
    posts the pair to team_roster_move.
    """
    team = get_object_or_404(models.Team, abbreviation__iexact=abbreviation)
    if not plans.can_edit(request.user, team):
        return HttpResponseForbidden("Only this team's owner and the commissioner can make its roster moves.")

    given = [(direction, request.GET.get(direction, "")) for direction in (roster_moves.DOWN, roster_moves.UP)]
    given = [(direction, value) for direction, value in given if value]
    player = None
    if len(given) == 1 and given[0][1].isdigit():
        direction = given[0][0]
        player = models.Player.objects.filter(pk=int(given[0][1])).first()
    if player is None:
        messages.error(request, "Start a move from a player on the game page.")
        return redirect(game_url(team))

    season, half = settings.CURRENT_SEASON, plans.current_half()
    context = utils.build_context(request)
    context.update(
        {
            "team": team,
            "move_half": half,
            "moves_left": roster_moves.moves_left(team, season, half),
            "moves_per_half": roster_moves.MOVES_PER_HALF,
            "choices": roster_moves.move_choices(team, player, direction, season, half),
            "going_down": direction == roster_moves.DOWN,
        }
    )
    return render(request, "team_roster_move.html", context)
