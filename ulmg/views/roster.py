# ABOUTME: The team Game page, the Roster tab's drag board, and paired roster moves.
# ABOUTME: A move calls one player up and sends one down. Only the owner and the commissioner can move.
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from ulmg import decision_cards, models, plans, roster_moves, schedule, utils
from ulmg.season_paths import bounce
from ulmg.views.plan import by_last_name


def _posted_player(request, name):
    value = request.POST.get(name, "")
    return models.Player.objects.filter(pk=int(value)).first() if value.isdigit() else None


def roster_board_url(team):
    """Where a move lands: the Roster tab for the half being played."""
    season, half = _playing_season(), plans.current_half()
    return f"/teams/{team.abbreviation.lower()}/plan/{half}/{season}/roster/#roster-moves"


def _playing_season():
    """The league year these pages follow. It opens on November 1, same as the schedule and plan URLs."""
    return utils.league_season()


def _gap_links(team, season, half, can_edit):
    base = f"/teams/{team.abbreviation.lower()}/plan/{half}/{season}"
    return {
        "lineups": f"{base}/edit/" if can_edit else f"{base}/",
        "rotation": f"{base}/rotation/",
        "bullpen": f"{base}/bullpen/",
    }


def _road_series(team, season, half, user, own_team):
    plan = plans.find_plan(team, season, half)
    by_day = plans.starters(plan) if plan else {}
    nxt = schedule.next_unplayed_road_game(team, season)
    next_id = nxt.id if nxt else None
    tester = utils.is_sim_tester(user)
    rows = []
    for series in schedule.upcoming_road_series(team, season, half):
        games = []
        for game in series["games"]:
            games.append(
                {
                    "game": game,
                    "starter": by_day.get(game.day),
                    "can_play": tester or (own_team and game.id == next_id),
                }
            )
        rows.append({**series, "games": games})
    return rows


def _own_team(user, team):
    owner = utils.get_owner_for_user(user)
    own_team = owner is not None and owner.team() == team
    if getattr(user, "is_superuser", False):
        own_team = True
    return own_team


@never_cache
def team_game(request, abbreviation):
    """
    The team's game page: what still needs filing, and once the half is in
    play, games played and left plus the next road series. Home games stay
    off this list. Roster moves live on the Roster tab.
    """
    team = get_object_or_404(models.Team, abbreviation__iexact=abbreviation)
    season, half = _playing_season(), plans.current_half()
    started = roster_moves.half_has_started(season, half)
    can_edit = plans.can_edit(request.user, team)
    own_team = _own_team(request.user, team)
    counts = schedule.half_game_counts(team, season, half)
    links = _gap_links(team, season, half, can_edit)
    context = utils.build_context(request)
    context.update(
        {
            "team": team,
            "own_team": own_team,
            "half_started": started,
            "move_half": half,
            "gaps": [{**gap, "href": links[gap["kind"]]} for gap in plans.plan_gaps(team, season, half)],
            "road_series": _road_series(team, season, half, request.user, own_team),
            "away_played": counts["away"]["played"],
            "away_left": counts["away"]["left"],
            "home_played": counts["home"]["played"],
            "home_left": counts["home"]["left"],
            "can_edit": can_edit,
        }
    )
    return render(request, "team_game.html", context)


def _board_team(abbreviation, half):
    if half not in plans.HALVES:
        raise Http404("A season has two halves.")
    return get_object_or_404(models.Team, abbreviation__iexact=abbreviation)


def _reasons(team, players, side, season):
    error = roster_moves.send_down_error if side == "mlb" else roster_moves.call_up_error
    return {player.id: error(team, player, season) for player in players}


def _cards(players, season):
    """Decision cards for the roster board. A two-way player gets a hitter card and a pitcher card."""
    stats, stored = decision_cards.load(players, season)
    built = {}
    for player in players:
        hit, pitch = stats.get(player.id, ({}, {}))
        card = stored.get(player.id)
        if not plans.is_pitcher(player):
            built[(player.id, "h")] = decision_cards.hitter_card(player, hit, card)
        if plans.can_pitch(player):
            built[(player.id, "p")] = decision_cards.pitcher_card(player, pitch, card)
    return built


def _rows(team, players, side, reasons, *, can_offer, over_cap, other_open):
    """One roster column: who can be dragged, who is held, and the no-JavaScript link."""
    abbr = team.abbreviation.lower()
    rows = []
    for player in by_last_name(players):
        reason = reasons[player.id]
        held = side == "mlb" and player.is_ulmg_2h_draft
        query = "down" if side == "mlb" else "up"
        can_drag = bool(can_offer and not over_cap and reason is None and other_open)
        rows.append(
            {
                "player": player,
                "reason": reason or "",
                "can_drag": can_drag,
                "choice_href": (
                    f"/teams/{abbr}/moves/new/?{query}={player.id}" if can_offer and not held else ""
                ),
            }
        )
    return rows


def _shown(row, card):
    shown = dict(row)
    shown["card"] = dict(card)
    shown["card"]["can_drag"] = row["can_drag"]
    return shown


def _role_groups(rows, cards):
    """Hitters, and pitchers. A two-way player is in both columns, each with its own card."""
    hitters = []
    pitchers = []
    for row in rows:
        player = row["player"]
        if not plans.is_pitcher(player):
            hitters.append(_shown(row, cards[(player.id, "h")]))
        if plans.can_pitch(player):
            pitchers.append(_shown(row, cards[(player.id, "p")]))
    return hitters, pitchers


@never_cache
def team_roster_board(request, abbreviation, half, season=None):
    """
    The Roster tab: the MLB and AAA rosters for one half. The owner drags a
    player onto the player he replaces. A move is still one call-up and one
    send-down, and the MLB roster cannot go over its limit.
    """
    team = _board_team(abbreviation, half)
    bounced = bounce(
        request, "teams", team.abbreviation.lower(), "plan", half, season=season, tail=("roster",)
    )
    if bounced:
        return bounced
    season = int(season)
    playing = season == _playing_season() and half == plans.current_half()
    started = roster_moves.half_has_started(season, half)
    can_edit = plans.can_edit(request.user, team)
    moves_left = roster_moves.moves_left(team, season, half)
    mlb_players = list(models.Player.objects.filter(team=team, is_ulmg_mlb_roster=True))
    aaa_players = list(
        models.Player.objects.filter(team=team, is_ulmg_aaa_roster=True, is_ulmg_mlb_roster=False)
    )
    mlb_reasons = _reasons(team, mlb_players, "mlb", season)
    aaa_reasons = _reasons(team, aaa_players, "aaa", season)
    mlb_count = len(mlb_players)
    over_cap = mlb_count > settings.MLB_ROSTER_SIZE
    can_offer = playing and can_edit and started and moves_left > 0
    aaa_open = any(reason is None for reason in aaa_reasons.values())
    mlb_open = any(reason is None for reason in mlb_reasons.values())
    mlb_rows = _rows(
        team, mlb_players, "mlb", mlb_reasons,
        can_offer=can_offer, over_cap=over_cap, other_open=aaa_open,
    )
    aaa_rows = _rows(
        team, aaa_players, "aaa", aaa_reasons,
        can_offer=can_offer, over_cap=over_cap, other_open=mlb_open,
    )
    cards = _cards(mlb_players + aaa_players, season)
    mlb_hitters, mlb_pitchers = _role_groups(mlb_rows, cards)
    aaa_hitters, aaa_pitchers = _role_groups(aaa_rows, cards)
    context = utils.build_context(request)
    context.update(
        {
            "team": team,
            "half": half,
            "plan_season": season,
            "can_edit": can_edit,
            "half_started": started,
            "move_half": half,
            "moves_per_half": roster_moves.MOVES_PER_HALF,
            "moves_left": moves_left,
            "active_stays": roster_moves.active_stays(team, season),
            "move_log": roster_moves.move_log(team, season),
            "mlb_count": mlb_count,
            "mlb_roster_size": settings.MLB_ROSTER_SIZE,
            "over_cap": over_cap,
            "mlb_hitters": mlb_hitters,
            "mlb_pitchers": mlb_pitchers,
            "aaa_hitters": aaa_hitters,
            "aaa_pitchers": aaa_pitchers,
            "can_drag": any(row["can_drag"] for row in mlb_rows + aaa_rows),
        }
    )
    return render(request, "team_roster_board.html", context)


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
        return redirect(roster_board_url(team))

    try:
        roster_moves.make_move(
            team,
            player_up,
            player_down,
            season=_playing_season(),
            half=plans.current_half(),
            user=request.user,
        )
    except roster_moves.MoveError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, f"Called up {player_up.name} and sent down {player_down.name}.")
    return redirect(roster_board_url(team))


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
        messages.error(request, "Start a move from a player on the roster tab.")
        return redirect(roster_board_url(team))

    season, half = _playing_season(), plans.current_half()
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
