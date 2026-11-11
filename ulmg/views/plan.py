# ABOUTME: Lineup, rotation and bullpen pages for one half, plus the one-day lineup override.
# ABOUTME: Anyone can read them. Only the team's owner and the commissioner can change them.
from django.contrib import messages
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotAllowed,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache

from ulmg import computer_manager, decision_cards, models, plans, roster_moves, usage, utils
from ulmg.season_paths import bounce, season_url

# The rotation shortcut offers six slots. Fewer than six is a shorter rotation.
ROTATION_SLOTS = 6
# Empty slots on the bullpen page. A role that already names more arms shows every one of them.
BULLPEN_GROUPS = (
    ("closer", "Closer", 1, "The 9th or later, in a save."),
    ("sirp", "SIRP", 4, "One inning from the 6th on, when the game is within three runs."),
    ("mirp", "MIRP", 4, "Before the 6th, or when the game is not that close."),
)
LINEUP_COLUMNS = (("vs_rhp", "vs Righty"), ("vs_lhp", "vs Lefty"))


def _team_and_half(abbreviation, half):
    if half not in plans.HALVES:
        raise Http404("A season has two halves.")
    return get_object_or_404(models.Team, abbreviation__iexact=abbreviation)


def _plan_url(team, half, season, day=None):
    tail = ("day", day) if day else ()
    url = season_url("teams", team.abbreviation.lower(), "plan", half, season=season, tail=tail)
    return f"{url}#day-{day}" if day else url


def _edit_url(team, half, season):
    return season_url(
        "teams", team.abbreviation.lower(), "plan", half, season=season, tail=("edit",)
    )


def _rotation_url(team, half, season):
    return season_url(
        "teams", team.abbreviation.lower(), "plan", half, season=season, tail=("rotation",)
    )


def _schedule_url(team, season):
    return season_url("teams", team.abbreviation.lower(), "schedule", season=season)


def _bullpen_url(team, half, season):
    return season_url(
        "teams", team.abbreviation.lower(), "plan", half, season=season, tail=("bullpen",)
    )


def _designation_url(team, half, season):
    return season_url(
        "teams", team.abbreviation.lower(), "plan", half, season=season, tail=("designation",)
    )


def by_last_name(players):
    """Card-list order: last name, then first name. A bare name sorts on its last word."""

    def key(player):
        last = (player.last_name or "").strip()
        first = (player.first_name or "").strip()
        if not last and player.name:
            parts = player.name.split()
            last = parts[-1]
            first = " ".join(parts[:-1])
        return (last.casefold(), first.casefold(), (player.name or "").casefold(), player.pk or 0)

    return sorted(players, key=key)


def _lineup_rows(stored):
    """Nine rows of (order, player id, position) from a stored lineup."""
    rows = [(i + 1, entry["player"], entry["position"]) for i, entry in enumerate(stored)]
    while len(rows) < plans.LINEUP_SIZE:
        rows.append((len(rows) + 1, None, plans.LINEUP_POSITIONS[len(rows)]))
    return rows


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class FormState:
    """The lineup editor's selections, from a saved plan or from a posted form."""

    def __init__(self, lineups, starter_hook):
        self.lineups = lineups
        self.starter_hook = starter_hook

    @classmethod
    def from_plan(cls, plan):
        return cls(
            {
                "vs_lhp": _lineup_rows(plan.lineup_vs_lhp),
                "vs_rhp": _lineup_rows(plan.lineup_vs_rhp),
            },
            plan.starter_hook,
        )

    @classmethod
    def from_post(cls, post):
        return cls(
            {prefix: _posted_lineup_rows(post, prefix) for prefix, _ in LINEUP_COLUMNS},
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
    """Lineup entries from editor rows. Rows without a player are left out."""
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


def _lineup_fields(state):
    """Lineup entries for save_lineups, plus errors for unknown players."""
    ids = set()
    for rows in state.lineups.values():
        ids |= {player_id for _, player_id, _ in rows if player_id is not None}
    players = models.Player.objects.in_bulk(ids)
    errors = []
    fields = {
        "lineup_vs_lhp": _entries(state.lineups["vs_lhp"], players, errors, "Lineup vs LHP"),
        "lineup_vs_rhp": _entries(state.lineups["vs_rhp"], players, errors, "Lineup vs RHP"),
        "starter_hook": state.starter_hook,
    }
    return fields, errors


def _roster(team, season, half, game=None):
    """Pitchers from the half's roster, or one game's, and hitters on the MLB roster now.

    Both lists are in last-name order for the card stacks.
    """
    rosters = roster_moves.HalfRosters(team, season, half)
    ids = rosters.for_game(game) if game is not None else rosters.all
    roster = by_last_name(models.Player.objects.filter(id__in=ids))
    return {
        "pitchers": [player for player in roster if plans.can_pitch(player)],
        "hitters": by_last_name(plans.lineup_hitters(ids)),
    }


def _designation_flags(players, season):
    """player id → confined_to_relief, only for counters that already exist."""
    return dict(
        models.UsageCounter.objects.filter(
            player_id__in=[player.id for player in players],
            season=season,
        ).values_list("player_id", "confined_to_relief")
    )


def _built_cards(players, season, kind):
    stats, cards = decision_cards.load(players, season)
    flags = _designation_flags(players, season) if kind == "p" else {}
    built = {}
    for player in players:
        hit, pitch = stats.get(player.id, ({}, {}))
        card = cards.get(player.id)
        if kind == "p":
            confined = flags[player.id] if player.id in flags else None
            built[player.id] = decision_cards.pitcher_card(
                player,
                pitch,
                card,
                designation=decision_cards.shown_designation(pitch, confined),
            )
        else:
            built[player.id] = decision_cards.hitter_card(player, hit, card)
    return built


def _with_missing(cards, ids, season, kind):
    missing = [player_id for player_id in ids if player_id and player_id not in cards]
    if not missing:
        return cards
    extra = list(models.Player.objects.filter(id__in=missing))
    return {**cards, **_built_cards(extra, season, kind)}


def _slots(rows, cards, season, kind):
    cards = _with_missing(cards, [player_id for _, player_id, _ in rows], season, kind)
    slots = []
    for order, player_id, position in rows:
        card = cards.get(player_id)
        slots.append(
            {
                "order": order,
                "player_id": player_id or "",
                "position": position,
                "card": card,
                "choices": (card or {}).get("positions") or plans.LINEUP_POSITIONS,
            }
        )
    return slots


def _padded_slots(ids, cards, season, count):
    """Slots for a role: at least count of them, and one for every pitcher already named."""
    ids = [player_id for player_id in ids if player_id]
    width = max(count, len(ids))
    ids = ids + [None] * (width - len(ids))
    cards = _with_missing(cards, ids, season, "p")
    return [{"player_id": player_id or "", "card": cards.get(player_id)} for player_id in ids]


def _rotation_slots(ids, cards, season):
    return _padded_slots(list(ids)[:ROTATION_SLOTS], cards, season, ROTATION_SLOTS)


def _posted_ids(post, name):
    return [player_id for player_id in (_int_or_none(value) for value in post.getlist(name)) if player_id]


def _bullpen_from_plan(plan):
    return {
        "closer": [plan.closer_id] if plan.closer_id else [],
        "sirp": list(plan.sirp or []),
        "mirp": list(plan.mirp or []),
        "bullpen_logic": plan.bullpen_logic or models.HalfPlan.TRADITIONAL_PEN,
    }


def _bullpen_from_post(post):
    return {
        "closer": _posted_ids(post, "closer")[:1],
        "sirp": _posted_ids(post, "sirp"),
        "mirp": _posted_ids(post, "mirp"),
        "bullpen_logic": post.get("bullpen_logic"),
    }


def _half_note(half):
    if half == 1:
        return "First half. Games 82–162 stay off the schedule until the second half is enabled."
    return "Second half."


def _common(request, team, half, season):
    context = utils.build_context(request)
    context.update(
        {
            "team": team,
            "half": half,
            "plan_season": season,
            "is_open": plans.is_open(half),
            "can_edit": plans.can_edit(request.user, team),
            "closed_message": plans.closed_message(half),
            "half_note": _half_note(half),
            "positions": plans.LINEUP_POSITIONS,
            "designation_url": _designation_url(team, half, season),
        }
    )
    return context


@never_cache
def team_plan(request, abbreviation, half, season=None):
    team = _team_and_half(abbreviation, half)
    bounced = bounce(request, "teams", team.abbreviation.lower(), "plan", half, season=season)
    if bounced:
        return bounced
    season = int(season)
    context = _common(request, team, half, season)
    plan = plans.find_plan(team, season, half)
    context["plan"] = plan
    if plan is not None:
        hitters = {
            player_id
            for lineup in (plan.lineup_vs_lhp, plan.lineup_vs_rhp)
            for entry in lineup
            for player_id in (entry["player"],)
        }
        players = list(models.Player.objects.filter(id__in=hitters))
        cards = _built_cards(players, season, "h")
        capped = {player.id for player in players if plans.is_capped_batter(player, season)}
        columns = []
        for prefix, label in LINEUP_COLUMNS:
            stored = plan.lineup_vs_lhp if prefix == "vs_lhp" else plan.lineup_vs_rhp
            slots = _slots(_lineup_rows(stored), cards, season, "h")
            for slot in slots:
                if slot["card"] is not None:
                    slot["card"] = {**slot["card"], "capped": slot["card"]["player"].id in capped}
            columns.append((prefix, label, slots))
        context["lineup_columns"] = columns
    return render(request, "team_plan.html", context)


def _editor_context(request, team, half, season, state, errors):
    context = _common(request, team, half, season)
    roster = _roster(team, season, half)
    cards = _built_cards(roster["hitters"], season, "h")
    context.update(roster)
    context.update(
        {
            "errors": errors,
            "hitter_cards": list(cards.values()),
            "starter_hook": state.starter_hook or models.HalfPlan.NORMAL_HOOK,
            "starter_hooks": models.HalfPlan.STARTER_HOOK_CHOICES,
            "lineup_columns": [
                (prefix, label, _slots(state.lineups[prefix], cards, season, "h"))
                for prefix, label in LINEUP_COLUMNS
            ],
            "editable": True,
        }
    )
    return context


@never_cache
def team_plan_edit(request, abbreviation, half, season=None):
    team = _team_and_half(abbreviation, half)
    bounced = bounce(
        request, "teams", team.abbreviation.lower(), "plan", half, season=season, tail=("edit",)
    )
    if bounced:
        return bounced
    season = int(season)
    if not plans.can_edit(request.user, team):
        return HttpResponseForbidden("Only this team's owner and the commissioner can edit its lineups.")
    plan = plans.find_plan(team, season, half) or models.HalfPlan(team=team, season=season, half=half)

    errors = []
    if request.method == "POST":
        state = FormState.from_post(request.POST)
        fields, errors = _lineup_fields(state)
        if not errors:
            try:
                plans.save_lineups(plan, **fields)
            except plans.PlanError as error:
                errors = error.errors
            else:
                messages.success(request, f"Saved the half {half} lineups.")
                return redirect(_plan_url(team, half, season))
    else:
        state = FormState.from_plan(plan)

    context = _editor_context(request, team, half, season, state, errors)
    return render(request, "team_plan_edit.html", context, status=400 if errors else 200)


@never_cache
def team_plan_rotation(request, abbreviation, half, season=None):
    team = _team_and_half(abbreviation, half)
    bounced = bounce(
        request,
        "teams",
        team.abbreviation.lower(),
        "plan",
        half,
        season=season,
        tail=("rotation",),
    )
    if bounced:
        return bounced
    season = int(season)
    plan = plans.find_plan(team, season, half) or models.HalfPlan(team=team, season=season, half=half)
    ids = list(plan.rotation) if plan.pk else []

    errors = []
    if request.method == "POST":
        if not plans.can_edit(request.user, team):
            return HttpResponseForbidden("Only this team's owner and the commissioner can set the rotation.")
        posted = [_int_or_none(value) for value in request.POST.getlist("rotation")]
        posted = [player_id for player_id in posted if player_id]
        players = models.Player.objects.in_bulk(posted)
        unknown = [player_id for player_id in posted if player_id not in players]
        if unknown:
            errors.append("That starter is not a player.")
        if not errors:
            try:
                warnings = plans.push_rotation(plan, [players[player_id] for player_id in posted])
            except plans.PlanError as error:
                errors = error.errors
                ids = posted
            else:
                for warning in warnings:
                    messages.warning(request, warning)
                messages.success(request, "Pushed the rotation onto the schedule.")
                return redirect(_schedule_url(team, season))
        else:
            ids = posted

    context = _common(request, team, half, season)
    roster = _roster(team, season, half)
    cards = _built_cards(roster["pitchers"], season, "p")
    context.update(
        {
            "errors": errors,
            "pitcher_cards": list(cards.values()),
            "rotation_slots": _rotation_slots(ids, cards, season),
            "schedule_url": _schedule_url(team, season),
        }
    )
    return render(request, "team_rotation.html", context, status=400 if errors else 200)


def _bullpen_players(state, errors):
    """Players for each role, in the posted order. Unknown ids become an error and stop the save."""
    ids = [player_id for name, _, _, _ in BULLPEN_GROUPS for player_id in state[name]]
    players = models.Player.objects.in_bulk(ids)
    if any(player_id not in players for player_id in ids):
        errors.append("That pitcher is not a player.")
        return None
    return {name: [players[player_id] for player_id in state[name]] for name, _, _, _ in BULLPEN_GROUPS}


def _bullpen_context(request, team, half, season, state, errors):
    context = _common(request, team, half, season)
    roster = _roster(team, season, half)
    cards = _built_cards(roster["pitchers"], season, "p")
    labels = dict(models.HalfPlan.BULLPEN_LOGIC_CHOICES)
    logic = state["bullpen_logic"] or models.HalfPlan.TRADITIONAL_PEN
    context.update(
        {
            "errors": errors,
            "pitcher_cards": list(cards.values()),
            "bullpen_groups": [
                {
                    "name": name,
                    "label": label,
                    "note": note,
                    "slots": _padded_slots(state[name], cards, season, count),
                }
                for name, label, count, note in BULLPEN_GROUPS
            ],
            "bullpen_logic": logic,
            "bullpen_logic_label": labels.get(logic, logic),
            "bullpen_logic_note": computer_manager.describe_bullpen_logic(logic),
            "bullpen_logics": [
                {
                    "value": value,
                    "label": label,
                    "note": computer_manager.describe_bullpen_logic(value),
                    "checked": value == logic,
                }
                for value, label in models.HalfPlan.BULLPEN_LOGIC_CHOICES
            ],
        }
    )
    return context


@never_cache
def team_plan_bullpen(request, abbreviation, half, season=None):
    team = _team_and_half(abbreviation, half)
    bounced = bounce(
        request,
        "teams",
        team.abbreviation.lower(),
        "plan",
        half,
        season=season,
        tail=("bullpen",),
    )
    if bounced:
        return bounced
    season = int(season)
    plan = plans.find_plan(team, season, half) or models.HalfPlan(team=team, season=season, half=half)
    state = _bullpen_from_plan(plan)

    errors = []
    if request.method == "POST":
        if not plans.can_edit(request.user, team):
            return HttpResponseForbidden("Only this team's owner and the commissioner can set the bullpen.")
        state = _bullpen_from_post(request.POST)
        found = _bullpen_players(state, errors)
        if found is not None and not errors:
            try:
                warnings = plans.save_bullpen(
                    plan,
                    closer=found["closer"][0] if found["closer"] else None,
                    sirp=found["sirp"],
                    mirp=found["mirp"],
                    bullpen_logic=state["bullpen_logic"],
                )
            except plans.PlanError as error:
                errors = error.errors
            else:
                for warning in warnings:
                    messages.warning(request, warning)
                messages.success(request, "Saved the bullpen.")
                return redirect(_bullpen_url(team, half, season))

    context = _bullpen_context(request, team, half, season, state, errors)
    return render(request, "team_bullpen.html", context, status=400 if errors else 200)


@never_cache
def team_plan_designation(request, abbreviation, half, season=None):
    """Name one pitcher starter or reliever for this season's usage."""
    team = _team_and_half(abbreviation, half)
    bounced = bounce(
        request,
        "teams",
        team.abbreviation.lower(),
        "plan",
        half,
        season=season,
        tail=("designation",),
    )
    if bounced:
        return bounced
    season = int(season)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not plans.can_edit(request.user, team):
        return HttpResponseForbidden(
            "Only this team's owner and the commissioner can set a pitcher's designation."
        )
    if not plans.is_open(half):
        return HttpResponseBadRequest(plans.closed_message(half))
    designation = request.POST.get("designation")
    if designation not in usage.DESIGNATIONS:
        return HttpResponseBadRequest("Designation must be rotation or bullpen.")
    player_id = _int_or_none(request.POST.get("player"))
    roster = _roster(team, season, half)
    player = next((candidate for candidate in roster["pitchers"] if candidate.id == player_id), None)
    if player is None:
        return HttpResponseBadRequest("That pitcher is not on this half's roster.")
    usage.set_swingman_designation(player, season, designation)
    if request.headers.get("x-requested-with") == "fetch":
        return HttpResponse(status=204)
    return redirect(_rotation_url(team, half, season))


@never_cache
def team_plan_day(request, abbreviation, half, day, season=None):
    team = _team_and_half(abbreviation, half)
    bounced = bounce(
        request,
        "teams",
        team.abbreviation.lower(),
        "plan",
        half,
        season=season,
        tail=("day", day),
    )
    if bounced:
        return bounced
    season = int(season)
    if not plans.can_edit(request.user, team):
        return HttpResponseForbidden("Only this team's owner and the commissioner can edit its plan.")
    # An owner can open a day before the cards are filed. The plan is the place that day is stored.
    plan = plans.plan_for(team, season, half)
    row = next((item for item in plans.plan_rows(plan) if item["day"] == day), None)
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
            {player_id for _, player_id, _ in lineup_rows if player_id is not None}
            | ({starter_id} if starter_id else set())
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
                # The day number comes from the URL. Only a local path is a safe redirect.
                target = f"{_schedule_url(team, season)}#day-{int(day)}"
                if url_has_allowed_host_and_scheme(target, allowed_hosts=None):
                    return redirect(target)
                return redirect(_schedule_url(team, season))

    context = _common(request, team, half, season)
    roster = _roster(team, season, half, row["game"])
    pitcher_cards = _built_cards(roster["pitchers"], season, "p")
    hitter_cards = _built_cards(roster["hitters"], season, "h")
    context.update(roster)
    context.update(
        {
            "row": row,
            "side": side,
            "errors": errors,
            "pitcher_cards": list(pitcher_cards.values()),
            "hitter_cards": list(hitter_cards.values()),
            "starter_id": starter_id or "",
            "starter_card": pitcher_cards.get(starter_id),
            "override": override,
            "lineup_rows": _slots(lineup_rows, hitter_cards, season, "h"),
            "editable": True,
            "plan_url": _plan_url(team, half, season),
        }
    )
    return render(request, "team_plan_day.html", context, status=400 if errors else 200)
