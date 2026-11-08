# ABOUTME: Roster moves from the team page: one call-up and one send-down as a single non-injury move,
# ABOUTME: and the move page that offers the legal partners for one player. Only the owner and the commissioner can move.
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


def team_url(team):
    return f"/teams/{team.abbreviation.lower()}/#roster-moves"


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
        return redirect(team_url(team))

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
    return redirect(team_url(team))


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
        messages.error(request, "Start a move from a player on the team page.")
        return redirect(team_url(team))

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
