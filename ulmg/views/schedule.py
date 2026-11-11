# ABOUTME: Season schedule pages, and the grid a manager uses to set starters.
# ABOUTME: The second half stays off the grid until it is enabled. Anyone can read; the owner can edit.
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from ulmg import decision_cards, models, plans, roster_moves, schedule, utils
from ulmg.season_paths import bounce, season_url
from ulmg.views.plan import _built_cards, _int_or_none, by_last_name


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


def _visible(games):
    halves = set(plans.visible_halves())
    return [game for game in games if game.series.slot.half in halves]


@never_cache
def league_schedule(request, season=None):
    bounced = bounce(request, "schedule", season=season)
    if bounced:
        return bounced
    season = int(season)
    context = utils.build_context(request)
    context["schedule_season"] = season
    slots = models.ScheduleSlot.objects.filter(season=season)
    if 2 not in plans.visible_halves():
        slots = slots.filter(half=1)
    context["slots"] = list(slots.prefetch_related("series__home_team", "series__road_team"))
    context["second_half_open"] = 2 in plans.visible_halves()
    return render(request, "schedule.html", context)


def _planned_rows(team, season):
    """plan_rows for each visible half that has a plan, keyed by day."""
    planned = {}
    for half in plans.visible_halves():
        plan = plans.find_plan(team, season, half)
        if plan is None:
            continue
        for row in plans.plan_rows(plan):
            planned[row["day"]] = row
    return planned


def _save_starters(request, team, season):
    """Apply the posted starter for each day. Returns errors, or None after redirecting."""
    games = {game.day: game for game in schedule.team_games(team, season)}
    posted = {}
    for key, value in request.POST.items():
        if key.startswith("starter_") and key[len("starter_"):].isdigit():
            posted[int(key[len("starter_"):])] = _int_or_none(value)
    players = models.Player.objects.in_bulk({player_id for player_id in posted.values() if player_id})
    errors = []
    by_half = {1: {}, 2: {}}
    for day, player_id in posted.items():
        game = games.get(day)
        if game is None:
            errors.append(f"Day {day} is not on the schedule.")
            continue
        if player_id and player_id not in players:
            errors.append(f"Day {day}: that starter is not a player.")
            continue
        by_half[game.series.slot.half][day] = players.get(player_id)
    if errors:
        return errors
    try:
        warnings = []
        for half, assignments in by_half.items():
            if not assignments:
                continue
            warnings += plans.assign_starters(plans.plan_for(team, season, half), assignments)
    except plans.PlanError as error:
        return error.errors
    for warning in warnings:
        messages.warning(request, warning)
    messages.success(request, "Saved the starters.")
    return None


@never_cache
def team_schedule(request, abbreviation, season=None):
    team = get_object_or_404(models.Team, abbreviation__icontains=abbreviation)
    bounced = bounce(request, "teams", team.abbreviation.lower(), "schedule", season=season)
    if bounced:
        return bounced
    season = int(season)
    can_edit = plans.can_edit(request.user, team)

    errors = []
    if request.method == "POST":
        if not can_edit:
            return HttpResponseForbidden("Only this team's owner and the commissioner can set starters.")
        errors = _save_starters(request, team, season)
        if errors is None:
            return redirect(season_url("teams", team.abbreviation.lower(), "schedule", season=season))
    errors = errors or []

    context = utils.build_context(request)
    context["team"] = team
    context["schedule_season"] = season
    context["can_edit"] = can_edit
    context["second_half_open"] = 2 in plans.visible_halves()
    context["errors"] = errors

    owner = utils.get_owner_for_user(request.user)
    own_team = owner is not None and owner.team() == team
    context["own_team"] = own_team

    planned = _planned_rows(team, season)
    games = _visible(schedule.team_games(team, season))
    tester = utils.is_sim_tester(request.user)
    owner_team = owner.team() if owner is not None else None
    next_road = schedule.next_unplayed_road_game(owner_team, season) if owner_team else None
    logged = set(models.GameLog.objects.filter(game__in=games).values_list("game_id", flat=True))

    roster_ids = set()
    for half in plans.visible_halves():
        roster_ids |= roster_moves.HalfRosters(team, season, half).all
    pitchers = [
        player
        for player in by_last_name(models.Player.objects.filter(id__in=roster_ids))
        if plans.can_pitch(player)
    ]
    pitcher_cards = _built_cards(pitchers, season, "p") if can_edit else {}

    rows = []
    for game in games:
        is_home = game.series.home_team_id == team.id
        opponent = game.series.road_team if is_home else game.series.home_team
        sheet = planned.get(game.day)
        side = sheet["side"] if sheet else None
        starter = side["starter"] if side else None
        manual = bool(side and side["starter_manual"])
        locked = plans.is_locked(game)
        rows.append(
            {
                "game": game,
                "is_home": is_home,
                "opponent": opponent,
                "starter": starter,
                "starter_manual": manual,
                "starter_card": pitcher_cards.get(starter.id) if starter else None,
                "opponent_starter": side["opponent_starter"] if side else None,
                "result": _team_result(game, is_home),
                "manager_plays": own_team and not is_home,
                "can_play": not game.is_played and (tester or (next_road is not None and game.id == next_road.id)),
                "has_box": game.is_played and game.id in logged,
                "locked": locked,
                "editable": can_edit and not locked and plans.is_open(game.series.slot.half),
                "lineup_gap": bool(side and side["unavailable"]),
            }
        )
    context["rows"] = rows
    context["pitcher_cards"] = list(pitcher_cards.values())
    context["designation_url"] = season_url(
        "teams",
        team.abbreviation.lower(),
        "plan",
        plans.current_half(),
        season=season,
        tail=("designation",),
    )
    return render(request, "team_schedule.html", context, status=400 if errors else 200)
