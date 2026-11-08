# ABOUTME: Half plan pages: the public plan for a team's half, the plan editor, and the one-day override editor.
# ABOUTME: Anyone can read a plan; only the team's owner and the commissioner can edit it.
from django.contrib import messages
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from ulmg import models, plans, roster_moves, utils
from ulmg.views.schedule import _schedule_season

# Empty selects the editor offers past the players already filed.
ROTATION_SLOTS = 6
SETUP_SLOTS = 4
MIDDLE_LONG_SLOTS = 8
LINEUP_PREFIXES = {"vs_lhp": "Lineup vs LHP", "vs_rhp": "Lineup vs RHP"}


def _team_and_half(abbreviation, half):
    if half not in plans.HALVES:
        raise Http404("A season has two halves.")
    return get_object_or_404(models.Team, abbreviation__iexact=abbreviation)


def _plan_url(team, half, season, day=None):
    url = f"/teams/{team.abbreviation.lower()}/plan/{half}/?season={season}"
    return f"{url}#day-{day}" if day else url


def _padded(ids, minimum):
    ids = list(ids)
    return ids + [None] * max(minimum - len(ids), 1)


def _lineup_rows(stored):
    """Nine editor rows of (order, player id, position) from a stored lineup."""
    rows = [(i + 1, e["player"], e["position"]) for i, e in enumerate(stored)]
    while len(rows) < plans.LINEUP_SIZE:
        rows.append((len(rows) + 1, None, plans.LINEUP_POSITIONS[len(rows)]))
    return rows


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class FormState:
    """The editor's selections, from a saved plan or from a posted form."""

    def __init__(self, rotation, closer, setup, middle_long, bench, lineups, starter_hook):
        self.rotation = rotation
        self.closer = closer
        self.setup = setup
        self.middle_long = middle_long
        self.bench = bench
        self.lineups = lineups
        self.starter_hook = starter_hook

    @classmethod
    def from_plan(cls, plan):
        return cls(
            plan.rotation,
            plan.closer_id,
            plan.setup,
            plan.middle_long,
            plan.bench,
            {"vs_lhp": _lineup_rows(plan.lineup_vs_lhp), "vs_rhp": _lineup_rows(plan.lineup_vs_rhp)},
            plan.starter_hook,
        )

    @classmethod
    def from_post(cls, post):
        def ids(name):
            return [i for i in (_int_or_none(v) for v in post.getlist(name)) if i is not None]

        return cls(
            ids("rotation"),
            _int_or_none(post.get("closer")),
            ids("setup"),
            ids("middle_long"),
            ids("bench"),
            {prefix: _posted_lineup_rows(post, prefix) for prefix in LINEUP_PREFIXES},
            post.get("starter_hook"),
        )


def _posted_lineup_rows(post, prefix):
    return [
        (
            _int_or_none(post.get(f"{prefix}_order_{i}")),
            _int_or_none(post.get(f"{prefix}_player_{i}")),
            post.get(f"{prefix}_position_{i}", ""),
        )
        for i in range(1, plans.LINEUP_SIZE + 1)
    ]


def _entries(rows, players, errors, label):
    """Lineup entries from editor rows; rows without a player are left out."""
    entries = []
    for order, player_id, position in rows:
        if player_id is None:
            continue
        player = players.get(player_id)
        if player is None or order is None:
            errors.append(f"{label}: each batter needs a player and a batting order.")
            continue
        entries.append({"order": order, "player": player, "position": position})
    return entries


def _fields(state):
    """save_plan's keyword arguments from editor selections, plus errors for unknown players."""
    ids = set(state.rotation) | set(state.setup) | set(state.middle_long) | set(state.bench)
    ids |= {state.closer} if state.closer else set()
    for rows in state.lineups.values():
        ids |= {player_id for _, player_id, _ in rows if player_id is not None}
    players = models.Player.objects.in_bulk(ids)
    errors = []

    def listed(values):
        return [players[i] for i in values if i in players]

    fields = {
        "rotation": listed(state.rotation),
        "closer": players.get(state.closer),
        "setup": listed(state.setup),
        "middle_long": listed(state.middle_long),
        "bench": listed(state.bench),
        "lineup_vs_lhp": _entries(state.lineups["vs_lhp"], players, errors, "Lineup vs LHP"),
        "lineup_vs_rhp": _entries(state.lineups["vs_rhp"], players, errors, "Lineup vs RHP"),
        "starter_hook": state.starter_hook,
    }
    return fields, errors


def _roster_context(team, season, half, game=None):
    """
    The players the editor offers: everyone the team can play in some game
    of the half, or, for one day, that game's roster.
    """
    rosters = roster_moves.HalfRosters(team, season, half)
    ids = rosters.for_game(game) if game is not None else rosters.all
    roster = list(models.Player.objects.filter(id__in=ids).order_by("name"))
    return {
        "pitchers": [p for p in roster if plans.can_pitch(p)],
        "hitters": [p for p in roster if not plans.is_pitcher(p)],
        "positions": plans.LINEUP_POSITIONS,
    }


def _lines(ids, season, position=None):
    players = models.Player.objects.in_bulk([i for i in ids if i])
    return [plans.player_line(players[i], season, position) for i in ids if i in players]


def _lineup_lines(stored, season):
    players = models.Player.objects.in_bulk([e["player"] for e in stored])
    return [
        plans.player_line(players[e["player"]], season, e["position"])
        for e in stored
        if e["player"] in players
    ]


@never_cache
def team_plan(request, abbreviation, half):
    team = _team_and_half(abbreviation, half)
    context = utils.build_context(request)
    season = _schedule_season(request)
    plan = plans.find_plan(team, season, half)
    context.update(
        {
            "team": team,
            "half": half,
            "plan_season": season,
            "plan": plan,
            "is_open": plans.is_open(half),
            "can_edit": plans.can_edit(request.user, team),
            "closed_message": plans.closed_message(half),
        }
    )
    if plan is not None:
        context["rows"] = plans.plan_rows(plan)
        context["rotation"] = _lines(plan.rotation, season)
        context["closer"] = _lines([plan.closer_id], season)
        context["setup"] = _lines(plan.setup, season)
        context["middle_long"] = _lines(plan.middle_long, season)
        context["starter_hook"] = plan.get_starter_hook_display()
        context["bench"] = _lines(plan.bench, season)
        context["lineup_cards"] = [
            ("vs LHP", _lineup_lines(plan.lineup_vs_lhp, season)),
            ("vs RHP", _lineup_lines(plan.lineup_vs_rhp, season)),
        ]
        batters = {
            player
            for row in context["rows"]
            for player, _ in row["side"]["lineup"]
        }
        context["capped_ids"] = {p.id for p in batters if plans.is_capped_batter(p, season)}
    return render(request, "team_plan.html", context)


def _editor_context(request, team, half, season, state, errors):
    context = utils.build_context(request)
    context.update(_roster_context(team, season, half))
    context.update(
        {
            "team": team,
            "half": half,
            "plan_season": season,
            "is_open": plans.is_open(half),
            "closed_message": plans.closed_message(half),
            "errors": errors,
            "rotation_slots": _padded(state.rotation, ROTATION_SLOTS),
            "closer_id": state.closer,
            "setup_slots": _padded(state.setup, SETUP_SLOTS),
            "middle_long_slots": _padded(state.middle_long, MIDDLE_LONG_SLOTS),
            "starter_hook": state.starter_hook or models.HalfPlan.NORMAL_HOOK,
            "starter_hooks": models.HalfPlan.STARTER_HOOK_CHOICES,
            "bench_slots": _padded(state.bench, len(context["hitters"])),
            "lineups": [
                (prefix, label, state.lineups[prefix]) for prefix, label in LINEUP_PREFIXES.items()
            ],
        }
    )
    return context


@never_cache
def team_plan_edit(request, abbreviation, half):
    team = _team_and_half(abbreviation, half)
    if not plans.can_edit(request.user, team):
        return HttpResponseForbidden("Only this team's owner and the commissioner can edit its plan.")
    season = _schedule_season(request)
    plan = plans.find_plan(team, season, half) or models.HalfPlan(team=team, season=season, half=half)

    errors = []
    if request.method == "POST":
        state = FormState.from_post(request.POST)
        fields, errors = _fields(state)
        if not errors:
            try:
                warnings = plans.save_plan(plan, **fields)
            except plans.PlanError as error:
                errors = error.errors
            else:
                for warning in warnings:
                    messages.warning(request, warning)
                messages.success(request, f"Saved the half {half} plan.")
                return redirect(_plan_url(team, half, season))
    else:
        state = FormState.from_plan(plan)

    context = _editor_context(request, team, half, season, state, errors)
    return render(request, "team_plan_edit.html", context, status=400 if errors else 200)


@never_cache
def team_plan_day(request, abbreviation, half, day):
    team = _team_and_half(abbreviation, half)
    if not plans.can_edit(request.user, team):
        return HttpResponseForbidden("Only this team's owner and the commissioner can edit its plan.")
    season = _schedule_season(request)
    plan = get_object_or_404(models.HalfPlan, team=team, season=season, half=half)
    row = next((r for r in plans.plan_rows(plan) if r["day"] == day), None)
    if row is None:
        raise Http404(f"Day {day} is not in half {half}.")

    errors = []
    side = row["side"]
    starter_id = side["starter"].id if side["starter_manual"] else None
    override = side["lineup_manual"]
    lineup_rows = _lineup_rows(side["lineup_stored"])
    if request.method == "POST":
        starter_id = _int_or_none(request.POST.get("starter"))
        override = bool(request.POST.get("override_lineup"))
        lineup_rows = _posted_lineup_rows(request.POST, "day")
        players = models.Player.objects.in_bulk(
            {p for _, p, _ in lineup_rows if p is not None} | ({starter_id} if starter_id else set())
        )
        starter = players.get(starter_id)
        if starter_id and starter is None:
            errors.append("That starter is not a player.")
        lineup = _entries(lineup_rows, players, errors, f"Day {day} lineup") if override else None
        if not errors:
            try:
                warnings = plans.save_day(plan, day, starter=starter, lineup=lineup)
            except plans.PlanError as error:
                errors = error.errors
            else:
                for warning in warnings:
                    messages.warning(request, warning)
                messages.success(request, f"Saved day {day}.")
                return redirect(_plan_url(team, half, season, day))

    context = utils.build_context(request)
    context.update(_roster_context(team, season, half, row["game"]))
    context.update(
        {
            "team": team,
            "half": half,
            "plan_season": season,
            "row": row,
            "side": side,
            "is_open": plans.is_open(half),
            "closed_message": plans.closed_message(half),
            "errors": errors,
            "starter_id": starter_id,
            "override": override,
            "lineup_rows": lineup_rows,
        }
    )
    return render(request, "team_plan_day.html", context, status=400 if errors else 200)
