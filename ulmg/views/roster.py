# ABOUTME: The roster move form on the team page: one call-up and one send-down as a single non-injury move.
# ABOUTME: Only the team's owner and the commissioner can make a move; the result shows as a message on the team page.
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from ulmg import models, plans, roster_moves


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
