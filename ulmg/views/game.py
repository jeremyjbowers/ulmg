# ABOUTME: The sim game pages: the game page with one form per action, each POST playing at most one plate appearance.
# ABOUTME: Also the public box score page. Seeds never come from the browser; every action carries the log position it expects.
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from ulmg import box_score, engine_client, models, sim_game, utils


def _game(game_id):
    return get_object_or_404(
        models.ScheduleGame.objects.select_related("series__slot", "series__home_team", "series__road_team"),
        pk=game_id,
    )


def game_url(game):
    return f"/games/{game.id}/"


def _posted_player(request, name):
    value = request.POST.get(name, "")
    return models.Player.objects.filter(pk=int(value)).first() if value.isdigit() else None


def _posted_side(request):
    side = request.POST.get("side")
    if side not in sim_game.SIDES:
        raise sim_game.GameRefused("Pick a side.")
    return side


def _posted_lineup(request):
    """Nine batting-order rows from the pregame lineup form: player-N and position-N for N in 1-9."""
    entries = []
    for order in range(1, 10):
        player = _posted_player(request, f"player-{order}")
        if player is None:
            raise sim_game.GameRefused(f"Pick a batter for the {sim_game.ordinal(order)} slot.")
        entries.append({"order": order, "player": player, "position": request.POST.get(f"position-{order}", "")})
    return entries


def _posted_positions(request):
    """Batting-order slots (0-8) to positions from the positions form's position-N for N in 1-9. A blank is no change."""
    return {
        order - 1: request.POST[f"position-{order}"]
        for order in range(1, 10)
        if request.POST.get(f"position-{order}")
    }


@never_cache
@login_required
def game_page(request, game_id):
    game = _game(game_id)
    context = utils.build_context(request)
    log = models.GameLog.objects.filter(game=game).first()
    try:
        if log is None:
            context.update(sim_game.pregame(game, request.user))
        else:
            context.update(sim_game.page(log, request.user))
    except engine_client.EngineUnavailable:
        context.update({"game": game, "log": log, "engine_down": True})
    return render(request, "game.html", context)


def _act(request, game, action):
    user = request.user
    if action == "open":
        seats = [side for side in request.POST.get("seats", "").split(",") if side]
        sim_game.open_game(game, user, seats)
        return
    log = models.GameLog.objects.filter(game=game).first()
    if log is None:
        raise sim_game.GameRefused("This game has not been opened.")
    expected = request.POST.get("expected")
    if action == "step":
        sim_game.step(log, user, expected, call=request.POST.get("call") or None)
    elif action == "pitcher":
        player = _posted_player(request, "player")
        if player is None:
            raise sim_game.GameRefused("Pick a pitcher.")
        sim_game.change_pitcher(log, user, _posted_side(request), player, expected)
    elif action == "replace":
        player = _posted_player(request, "player")
        if player is None:
            raise sim_game.GameRefused("Pick a replacement.")
        sim_game.replace_batter(log, user, _posted_side(request), player, expected)
    elif action in ("pinch_hit", "pinch_run", "defense"):
        player = _posted_player(request, "player")
        if player is None:
            raise sim_game.GameRefused("Pick a substitute.")
        side = _posted_side(request)
        if action == "pinch_hit":
            sim_game.pinch_hit(log, user, side, player, expected)
        elif action == "pinch_run":
            sim_game.pinch_run(log, user, side, request.POST.get("base", ""), player, expected)
        else:
            slot = request.POST.get("slot", "")
            if not slot.isdigit():
                raise sim_game.GameRefused("Pick the player he replaces.")
            sim_game.defensive_substitution(log, user, side, int(slot) - 1, player, expected)
    elif action == "positions":
        sim_game.set_positions(log, user, _posted_side(request), _posted_positions(request), expected)
    elif action == "lineup":
        sim_game.change_lineup(log, user, _posted_side(request), _posted_lineup(request), expected)
    elif action == "move":
        up, down = _posted_player(request, "player_up"), _posted_player(request, "player_down")
        if up is None or down is None:
            raise sim_game.GameRefused("Pick a player to call up and a player to send down.")
        sim_game.make_roster_move(log, user, _posted_side(request), up, down, expected)
    elif action == "take":
        sim_game.take_seat(log, user, _posted_side(request), expected)
    elif action == "leave":
        sim_game.leave_seat(log, user, _posted_side(request), expected)
    elif action == "check":
        sim_game.check_pause(log, user, expected)
    else:
        raise Http404("No such game action.")


@never_cache
@login_required
@require_POST
def game_action(request, game_id, action):
    game = _game(game_id)
    try:
        _act(request, game, action)
    except sim_game.GameRefused as refused:
        for reason in refused.reasons:
            messages.error(request, reason)
    except engine_client.EngineUnavailable:
        messages.error(request, "The game engine is not answering, so nothing was played. Try again in a minute.")
    return redirect(game_url(game))


@never_cache
def game_box_score(request, game_id):
    game = _game(game_id)
    context = utils.build_context(request)
    log = get_object_or_404(models.GameLog, game=game)
    context.update({"game": game, "log": log, "box": box_score.box_score(log)})
    return render(request, "game_box_score.html", context)
