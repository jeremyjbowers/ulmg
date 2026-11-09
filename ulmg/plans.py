# ABOUTME: Half plans: each team's rotation, lineup cards, bench and bullpen for one season half, on the league calendar.
# ABOUTME: Auto-fills starters through the usage ledger, keeps manual edits apart, and freezes a game's sheet when it opens.

from collections import defaultdict

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ulmg import models, roster_moves, schedule, usage, utils

LINEUP_POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
LINEUP_SIZE = len(LINEUP_POSITIONS)
CATCHER = "C"

# A lineup card is chosen by the throwing hand of the opposing starter.
LEFT = "L"
RIGHT = "R"
LINEUP_LABELS = {LEFT: "vs LHP", RIGHT: "vs RHP"}

SECOND_HALF_OPENS = "2h"
HALVES = (1, 2)


class PlanError(Exception):
    """A plan or day edit that breaks a rule. errors are messages; days are the days without a legal starter."""

    def __init__(self, errors, days=None):
        self.errors = list(errors)
        self.days = list(days or [])
        super().__init__(" ".join(self.errors))


# The half and who may edit


def is_open(half):
    """The first-half plan is open from the start of the season; the second opens at the trade break."""
    return half == 1 or settings.TEAM_SEASON_HALF == SECOND_HALF_OPENS


def current_half():
    return 2 if settings.TEAM_SEASON_HALF == SECOND_HALF_OPENS else 1


def closed_message(half):
    return f"The half {half} plan opens after the trade break."


def can_edit(user, team):
    """The team's owner and the commissioner can edit a plan. Everyone can read one."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return utils.get_team_for_owner(utils.get_owner_for_user(user)) == team


# Lookups


def plan_for(team, season, half):
    """The team's plan for a half, created empty if it doesn't exist."""
    plan, _ = models.HalfPlan.objects.get_or_create(team=team, season=season, half=half)
    return plan


def find_plan(team, season, half):
    return models.HalfPlan.objects.filter(team=team, season=season, half=half).first()


def thirty_man(team):
    return models.Player.objects.filter(team=team, is_ulmg_mlb_roster=True).order_by("name")


def is_pitcher(player):
    """A pure pitcher. Pitchers do not hit."""
    return player.position == models.Player.PITCHER


def can_pitch(player):
    """A pitcher or a two-way player."""
    return models.Player.PITCHER in (player.position or "").split("-")


def half_games(team, season, half):
    """The team's games in a half, home and road, as {day: game}."""
    return {
        game.day: game
        for game in schedule.team_games(team, season)
        if game.series.slot.half == half
    }


def is_locked(game):
    """A game that has opened or been played. Its plan day can no longer change."""
    return game.opened_at is not None or game.is_played


def card_for(player, season):
    """The engine card a ULMG season plays with: the previous MLB season's."""
    return models.Card.objects.filter(player=player, season=season - 1).first()


def _players_by_id(ids):
    ids = {i for i in ids if i is not None}
    return models.Player.objects.in_bulk(ids)


def _ordered_players(ids):
    players = _players_by_id(ids)
    return [players[i] for i in ids if i in players]


# Validation


def _unique_errors(errors):
    return list(dict.fromkeys(errors))


def _roster_error(player, team, roster_ids):
    if player.id not in roster_ids:
        return f"{player.name} is not on {team.abbreviation}'s 30-man."
    return None


def lineup_errors(team, season, entries, label, roster_problem):
    """
    Rule errors for one lineup. entries are dicts of order (1-9), player (a
    Player) and position. Nine batters, each order and each position once,
    no pitchers, only the 30-man, and a catcher rating to play C.
    roster_problem(player) says why a player isn't on the roster the lineup
    is for, or returns None.
    """
    errors = []
    if len(entries) != LINEUP_SIZE:
        errors.append(f"{label}: a lineup needs nine batters; this one has {len(entries)}.")

    orders = [entry["order"] for entry in entries]
    for order in sorted(set(orders)):
        if order not in range(1, LINEUP_SIZE + 1):
            errors.append(f"{label}: batting order {order} is not 1 through 9.")
        elif orders.count(order) > 1:
            errors.append(f"{label}: Batting order {order} is used twice.")

    positions = [entry["position"] for entry in entries]
    for position in sorted(set(positions)):
        if position not in LINEUP_POSITIONS:
            errors.append(f"{label}: {position} is not a lineup position.")
        elif positions.count(position) > 1:
            errors.append(f"{label}: {position} is filed twice.")
    if len(entries) == LINEUP_SIZE:
        for position in LINEUP_POSITIONS:
            if position not in positions:
                errors.append(f"{label}: nobody is filed at {position}.")

    seen = set()
    for entry in entries:
        player = entry["player"]
        if player.id in seen:
            errors.append(f"{label}: {player.name} is in the lineup twice.")
        seen.add(player.id)
        roster = roster_problem(player)
        if roster:
            errors.append(f"{label}: {roster}")
        if is_pitcher(player):
            errors.append(f"{label}: {player.name} is a pitcher; pitchers do not hit.")
        if entry["position"] == CATCHER:
            card = card_for(player, season)
            if card is None or (card.defense or {}).get(CATCHER) is None:
                errors.append(f"{label}: {player.name} has no catcher rating and cannot be filed at C.")
    return errors


def stored_lineup(entries):
    """Lineup entries as stored: [{"player": id, "position": code}] in batting order."""
    return [
        {"player": entry["player"].id, "position": entry["position"]}
        for entry in sorted(entries, key=lambda e: e["order"])
    ]


def lineup_entries(stored):
    """A stored lineup back as entries with Player objects, for validation and forms."""
    players = _players_by_id(e["player"] for e in stored)
    return [
        {"order": i + 1, "player": players[e["player"]], "position": e["position"]}
        for i, e in enumerate(stored)
        if e["player"] in players
    ]


def _call_up_card_errors(team, season, half, rosters, cards):
    """
    A call-up can be planned into road games only, and the lineup cards
    cover every home day that hasn't opened, so a call-up can't be on a card
    while one is left. He goes into road days' lineups one day at a time.
    """
    call_ups = rosters.road - rosters.home
    carded = [(label, entry["player"]) for label, entries in cards for entry in entries]
    if not any(player.id in call_ups for _, player in carded):
        return []
    home_left = any(
        game.series.home_team_id == team.id and not is_locked(game)
        for game in half_games(team, season, half).values()
    )
    if not home_left:
        return []
    return [
        f"{label}: {player.name} is a call-up and can be planned into road games only; "
        "the lineup cards also cover home days. File him into road days' lineups instead."
        for label, player in carded
        if player.id in call_ups
    ]


def rotation_errors(team, rotation, roster_ids):
    """Rule errors for a rotation: at least one starter, each a 30-man pitcher, each once."""
    errors = []
    if not rotation:
        errors.append("The rotation needs at least one starter.")
    for player in rotation:
        errors.append(_roster_error(player, team, roster_ids))
        if not can_pitch(player):
            errors.append(f"{player.name} is not a pitcher and cannot be in the rotation.")
        if rotation.count(player) > 1:
            errors.append(f"{player.name} is in the rotation twice.")
    return _unique_errors([e for e in errors if e])


def _bullpen_players(closer, setup_l, setup_r, sirp, mirp):
    return ([closer] if closer else []) + list(setup_l) + list(setup_r) + list(sirp) + list(mirp)


def bullpen_errors(team, closer, setup_l, setup_r, sirp, mirp, roster_ids):
    """Rule errors for the bullpen roles: 30-man pitchers, each in one role once."""
    errors = []
    bullpen = _bullpen_players(closer, setup_l, setup_r, sirp, mirp)
    for player in bullpen:
        errors.append(_roster_error(player, team, roster_ids))
        if not can_pitch(player):
            errors.append(f"{player.name} is not a pitcher and cannot be in the bullpen.")
        if bullpen.count(player) > 1:
            errors.append(f"{player.name} is in the bullpen twice.")
    return _unique_errors([e for e in errors if e])


def bench_errors(team, bench, roster_ids):
    """Rule errors for the bench order: 30-man non-pitchers, each once."""
    errors = []
    for player in bench:
        errors.append(_roster_error(player, team, roster_ids))
        if is_pitcher(player):
            errors.append(f"The bench is for non-pitchers; {player.name} is a pitcher.")
        if bench.count(player) > 1:
            errors.append(f"{player.name} is on the bench twice.")
    return _unique_errors([e for e in errors if e])


def plan_errors(team, season, half, *, rotation, closer, setup_l, setup_r, sirp, mirp, bench, lineup_vs_lhp, lineup_vs_rhp):
    """
    Every rule error in a plan's rotation, bullpen, bench and lineup cards.
    They are checked against everyone the team can play in some game of the
    half; each game's own roster is applied day by day.
    """
    rosters = roster_moves.HalfRosters(team, season, half)
    roster_ids = rosters.all
    errors = []
    errors += rotation_errors(team, rotation, roster_ids)
    errors += bullpen_errors(team, closer, setup_l, setup_r, sirp, mirp, roster_ids)
    errors += bench_errors(team, bench, roster_ids)

    def roster_problem(player):
        return _roster_error(player, team, roster_ids)

    errors += lineup_errors(team, season, lineup_vs_lhp, "Lineup vs LHP", roster_problem)
    errors += lineup_errors(team, season, lineup_vs_rhp, "Lineup vs RHP", roster_problem)
    errors += _call_up_card_errors(
        team, season, half, rosters, [("Lineup vs LHP", lineup_vs_lhp), ("Lineup vs RHP", lineup_vs_rhp)]
    )
    return _unique_errors([e for e in errors if e])


def _stored_fields(plan):
    """A saved plan's fields as Player objects, for re-checking it."""
    return {
        "rotation": _ordered_players(plan.rotation),
        "closer": plan.closer,
        "setup_l": _ordered_players(plan.setup_l),
        "setup_r": _ordered_players(plan.setup_r),
        "sirp": _ordered_players(plan.sirp),
        "mirp": _ordered_players(plan.mirp),
        "bench": _ordered_players(plan.bench),
        "lineup_vs_lhp": lineup_entries(plan.lineup_vs_lhp),
        "lineup_vs_rhp": lineup_entries(plan.lineup_vs_rhp),
    }


# Starters


def _day_rows(plan, games):
    """The plan's day rows for every game in its half, created where missing."""
    rows = {
        row.day: row
        for row in plan.days.select_related("auto_starter", "manual_starter")
    }
    missing = [models.HalfPlanDay(plan=plan, day=day) for day in games if day not in rows]
    if missing:
        models.HalfPlanDay.objects.bulk_create(missing)
        return _day_rows(plan, games)
    return rows


def _other_half_starts(plan):
    """Unplayed starts the team's other-half plan has, as {player id: [games]}."""
    starts = defaultdict(list)
    other = find_plan(plan.team, plan.season, 3 - plan.half)
    if other is None:
        return starts
    games = half_games(plan.team, plan.season, other.half)
    for row in other.days.select_related("auto_starter", "manual_starter"):
        game = games.get(row.day)
        if game is not None and row.starter is not None and not game.is_played:
            starts[row.starter.id].append(game)
    return starts


def _planned_starts(plan, games, rows, include):
    """Unplayed planned starts this season by pitcher id, from the other half and the rows include() picks."""
    starts = _other_half_starts(plan)
    for day, row in rows.items():
        game = games[day]
        if row.starter is not None and not game.is_played and include(game, row):
            starts[row.starter.id].append(game)
    return starts


def _auto_fill(plan, games, rows, rosters, reads):
    """
    Fill every unopened day without a manual starter from the rotation. The
    k-th game of the half goes to slot ((k - 1) mod N) + 1; a slot whose
    pitcher would pass his start cap, isn't rested inside the series, or
    isn't on that game's roster (a call-up at home, a sent-down pitcher on
    the road) goes to the next legal pitcher in order, and the cycle
    continues from him. Returns the days no one could start. reads are the
    ledger reads for this refill; filling days writes nothing to the ledger.
    """
    rotation = _ordered_players(plan.rotation)
    reads.preload(rotation)
    rotation_ids = [p.id for p in rotation]
    planned = _planned_starts(
        plan, games, rows, lambda game, row: is_locked(game) or row.manual_starter_id
    )

    unfilled = []
    pointer = 0
    for day in sorted(games):
        game, row = games[day], rows[day]
        if is_locked(game):
            if row.manual_starter_id is None and row.auto_starter_id in rotation_ids:
                pointer = rotation_ids.index(row.auto_starter_id) + 1
            else:
                pointer += 1
            continue
        if row.manual_starter_id:
            pointer += 1
            continue

        chosen = None
        for step in range(len(rotation)):
            index = (pointer + step) % len(rotation)
            candidate = rotation[index]
            if candidate.id not in rosters.for_game(game):
                continue
            if usage.check_planned_start(candidate, game, planned[candidate.id], reads=reads).legal:
                chosen = candidate
                pointer = index + 1
                break
        if chosen is None:
            unfilled.append(day)
            pointer += 1
        else:
            planned[chosen.id].append(game)

        if row.auto_starter_id != (chosen.id if chosen else None):
            row.auto_starter = chosen
            row.save(update_fields=["auto_starter", "last_modified"])
    return unfilled


def _manual_start_problems(plan, games, rows, rosters, reads=None):
    """Rule errors for the unopened days' manual starters, against every other planned start."""
    planned = _planned_starts(plan, games, rows, lambda game, row: True)
    problems = []
    for day in sorted(rows):
        row, game = rows[day], games[day]
        starter = row.manual_starter
        if starter is None or is_locked(game):
            continue
        problem = _start_problem(starter, game, planned[starter.id], rosters, reads)
        if problem:
            problems.append(f"Day {day}: {problem}")
    return problems


def _start_problem(starter, game, planned_games, rosters, reads=None):
    roster = rosters.problem(starter, game)
    if roster:
        return roster
    if not can_pitch(starter):
        return f"{starter.name} is not a pitcher."
    others = [g for g in planned_games if g.id != game.id]
    check = usage.check_planned_start(starter, game, others, reads=reads)
    return None if check.legal else check.reason


def _refill_problems(plan, rosters):
    """Re-run auto-fill and check every day. Returns the errors and the days without a legal starter."""
    games = half_games(plan.team, plan.season, plan.half)
    rows = _day_rows(plan, games)
    # Nothing here writes to the usage ledger, so one read of it serves every day.
    reads = usage.LedgerReads(plan.season)
    unfilled = _auto_fill(plan, games, rows, rosters, reads)
    errors = _manual_start_problems(plan, games, rows, rosters, reads)
    if unfilled:
        days = ", ".join(str(d) for d in unfilled)
        errors.insert(
            0,
            f"No legal starter for days {days}. Spot-start those days or make a roster move.",
        )
    return errors, unfilled


def _refill(plan, rosters):
    """Re-run auto-fill and check every day. Raises PlanError listing the days without a legal starter."""
    errors, unfilled = _refill_problems(plan, rosters)
    if errors:
        raise PlanError(errors, unfilled)


def _designate(plan):
    """
    Set each plan pitcher's swingman designation for the current half: in
    the rotation or with a planned spot start, he starts and relieves; only
    in the bullpen, he is confined to relief. Returns warnings for any
    bullpen-only swingman whose spot start ends that confinement.
    """
    if plan.half != current_half():
        return []
    games = half_games(plan.team, plan.season, plan.half)
    spot_ids = {
        row.manual_starter_id
        for row in plan.days.filter(manual_starter__isnull=False)
        if row.day in games and not is_locked(games[row.day])
    }
    rotation_ids = set(plan.rotation)
    starting_ids = rotation_ids | spot_ids
    bullpen_ids = set(plan.setup_l) | set(plan.setup_r) | set(plan.sirp) | set(plan.mirp)
    if plan.closer_id:
        bullpen_ids.add(plan.closer_id)

    warnings = []
    for player in _players_by_id(starting_ids | bullpen_ids).values():
        if not can_pitch(player):
            continue
        designation = usage.ROTATION if player.id in starting_ids else usage.BULLPEN
        counter = usage.counter_for(player, plan.season)
        if (
            designation == usage.ROTATION
            and player.id not in rotation_ids
            and counter.confined_to_relief
            and counter.confined_innings_cap_outs is not None
        ):
            warnings.append(
                f"Planning a start for {player.name} ends his relief-only designation for {plan.season}."
            )
        usage.set_swingman_designation(player, plan.season, designation)
    return warnings


def reapply_designations(season):
    """
    Set every kept plan's swingman designations again, for a season whose
    usage counters were just reset. Returns the number of plans applied.
    """
    applied = 0
    for plan in models.HalfPlan.objects.filter(season=season).select_related("team"):
        _designate(plan)
        applied += 1
    return applied


# Saving


def starter_hook_errors(starter_hook):
    hooks = [value for value, _ in models.HalfPlan.STARTER_HOOK_CHOICES]
    if starter_hook is not None and starter_hook not in hooks:
        return [f"The starter hook must be {', '.join(hooks[:-1])} or {hooks[-1]}."]
    return []


def save_plan(plan, *, rotation, closer, setup_l, setup_r, sirp, mirp, bench, lineup_vs_lhp, lineup_vs_rhp, starter_hook=None):
    """
    Save a half plan's rotation, bullpen, bench, lineup cards and starter
    hook, re-run auto-fill and set swingman designations. A starter_hook of
    None keeps the plan's. Nothing is saved when a rule is broken or a day
    has no legal starter. Returns warnings to show.
    """
    if not is_open(plan.half):
        raise PlanError([closed_message(plan.half)])
    fields = {
        "rotation": list(rotation),
        "closer": closer,
        "setup_l": list(setup_l),
        "setup_r": list(setup_r),
        "sirp": list(sirp),
        "mirp": list(mirp),
        "bench": list(bench),
        "lineup_vs_lhp": list(lineup_vs_lhp),
        "lineup_vs_rhp": list(lineup_vs_rhp),
    }
    errors = plan_errors(plan.team, plan.season, plan.half, **fields) + starter_hook_errors(starter_hook)
    if errors:
        raise PlanError(errors)

    rosters = roster_moves.HalfRosters(plan.team, plan.season, plan.half)
    with transaction.atomic():
        plan.rotation = [p.id for p in fields["rotation"]]
        plan.closer = closer
        plan.setup_l = [p.id for p in fields["setup_l"]]
        plan.setup_r = [p.id for p in fields["setup_r"]]
        plan.sirp = [p.id for p in fields["sirp"]]
        plan.mirp = [p.id for p in fields["mirp"]]
        plan.bench = [p.id for p in fields["bench"]]
        plan.lineup_vs_lhp = stored_lineup(fields["lineup_vs_lhp"])
        plan.lineup_vs_rhp = stored_lineup(fields["lineup_vs_rhp"])
        if starter_hook is not None:
            plan.starter_hook = starter_hook
        plan.save()
        _refill(plan, rosters)
        return _designate(plan)


def fill_plan(
    plan, *, rotation, closer, setup_l, setup_r, sirp, mirp, bench, lineup_vs_lhp, lineup_vs_rhp, ignore_half_lock=False
):
    """
    Save as much of a half plan as is legal, for building a test season
    (setup_sim_season). Unlike save_plan it never rejects the whole plan: a
    rotation, bullpen, bench or lineup card that breaks a rule is saved
    empty, auto-fill fills every day it can, and swingman designations are
    set as save_plan sets them. Returns the problems as messages.

    ignore_half_lock fills a second-half plan before the trade break. Only
    test setup passes it; the plan pages always go through save_plan and
    is_open.
    """
    if not ignore_half_lock and not is_open(plan.half):
        raise PlanError([closed_message(plan.half)])
    team = plan.team
    rosters = roster_moves.HalfRosters(team, plan.season, plan.half)
    roster_ids = rosters.all
    rotation, setup_l, setup_r, sirp, mirp, bench = (
        list(rotation), list(setup_l), list(setup_r), list(sirp), list(mirp), list(bench)
    )
    lineup_vs_lhp, lineup_vs_rhp = list(lineup_vs_lhp), list(lineup_vs_rhp)

    problems = []
    errors = rotation_errors(plan.team, rotation, roster_ids)
    if errors:
        problems += errors
        rotation = []
    errors = bullpen_errors(plan.team, closer, setup_l, setup_r, sirp, mirp, roster_ids)
    if errors:
        problems += errors
        closer, setup_l, setup_r, sirp, mirp = None, [], [], [], []
    errors = bench_errors(plan.team, bench, roster_ids)
    if errors:
        problems += errors
        bench = []

    def roster_problem(player):
        return _roster_error(player, team, roster_ids)

    def card_errors(entries, label):
        return lineup_errors(team, plan.season, entries, label, roster_problem) + _call_up_card_errors(
            team, plan.season, plan.half, rosters, [(label, entries)]
        )

    errors = card_errors(lineup_vs_lhp, "Lineup vs LHP")
    if errors:
        problems += errors
        lineup_vs_lhp = []
    errors = card_errors(lineup_vs_rhp, "Lineup vs RHP")
    if errors:
        problems += errors
        lineup_vs_rhp = []

    with transaction.atomic():
        plan.rotation = [p.id for p in rotation]
        plan.closer = closer
        plan.setup_l = [p.id for p in setup_l]
        plan.setup_r = [p.id for p in setup_r]
        plan.sirp = [p.id for p in sirp]
        plan.mirp = [p.id for p in mirp]
        plan.bench = [p.id for p in bench]
        plan.lineup_vs_lhp = stored_lineup(lineup_vs_lhp)
        plan.lineup_vs_rhp = stored_lineup(lineup_vs_rhp)
        plan.save()
        errors, _ = _refill_problems(plan, rosters)
        _designate(plan)
    return problems + errors


def save_day(plan, day, *, starter=None, lineup=None):
    """
    Set or clear one unopened day's manual starter and manual lineup. None
    returns that part of the day to auto-fill. A spot starter must be a
    30-man pitcher, rested inside the series and under his start cap,
    counting his starts made and every other start in the plan. Returns
    warnings to show.
    """
    if not is_open(plan.half):
        raise PlanError([closed_message(plan.half)])
    games = half_games(plan.team, plan.season, plan.half)
    game = games.get(day)
    if game is None:
        raise PlanError([f"Day {day} is not in half {plan.half}."])
    if is_locked(game):
        raise PlanError([f"Day {day} has opened; its plan can no longer change."])

    errors = plan_errors(plan.team, plan.season, plan.half, **_stored_fields(plan))
    if errors:
        raise PlanError(["Save the plan first: " + errors[0]] + errors[1:])

    rosters = roster_moves.HalfRosters(plan.team, plan.season, plan.half)
    if lineup is not None:
        errors += lineup_errors(
            plan.team, plan.season, lineup, f"Day {day} lineup", lambda p: rosters.problem(p, game)
        )

    rows = _day_rows(plan, games)
    if starter is not None:
        planned = _planned_starts(plan, games, rows, lambda g, row: g.day != day)
        problem = _start_problem(starter, game, planned[starter.id], rosters)
        if problem:
            errors.append(f"Day {day}: {problem}")
    if errors:
        raise PlanError(errors)

    with transaction.atomic():
        row = rows[day]
        row.manual_starter = starter
        row.manual_lineup = stored_lineup(lineup) if lineup is not None else None
        row.save()
        _refill(plan, rosters)
        return _designate(plan)


def set_starter(plan, day, starter):
    """
    Set or clear one day's starter from the schedule, and leave that day's
    lineup alone. None returns the day to the rotation.
    """
    games = half_games(plan.team, plan.season, plan.half)
    row = plan.days.filter(day=day).first() if day in games else None
    lineup = lineup_entries(row.manual_lineup) if row is not None and row.manual_lineup else None
    return save_day(plan, day, starter=starter, lineup=lineup)


def schedule_starter_choices(team, season):
    """
    The pitchers an editor may start in each unopened game of an open half,
    and how many starts each still has room for, counting starts made and
    every other start the plan already gives him. A pitcher at his cap, or
    without rest inside the series, is left out.
    """
    choices = {}
    for half in HALVES:
        if not is_open(half):
            continue
        plan = find_plan(team, season, half)
        if plan is None:
            continue
        games = half_games(team, season, half)
        rows = _day_rows(plan, games)
        rosters = roster_moves.HalfRosters(team, season, half)
        pitchers = [p for p in models.Player.objects.filter(id__in=rosters.all).order_by("name") if can_pitch(p)]
        reads = usage.LedgerReads(season)
        reads.preload(pitchers)
        planned = _planned_starts(plan, games, rows, lambda game, row: True)
        for day in sorted(games):
            game = games[day]
            if is_locked(game):
                continue
            offered = []
            for pitcher in pitchers:
                others = [g for g in planned[pitcher.id] if g.id != game.id]
                if _start_problem(pitcher, game, others, rosters, reads):
                    continue
                counter = reads.for_game(game).counter(pitcher)
                left = counter.starts_cap - counter.starts - len(others)
                offered.append({"player": pitcher, "left": left})
            choices[game.id] = offered
    return choices


# Reading


def starters(plan):
    """The plan's starter for each day of its half, manual or auto-filled."""
    return {
        row.day: row.starter
        for row in plan.days.select_related("auto_starter", "manual_starter")
    }


def season_starters(season):
    """Every plan's starter for the season as {(team id, day): Player}."""
    rows = models.HalfPlanDay.objects.filter(plan__season=season).select_related(
        "plan", "auto_starter", "manual_starter"
    )
    return {(row.plan.team_id, row.day): row.starter for row in rows if row.starter}


class PlanBook:
    """The saved plans of one season half, loaded once to read game sheets from."""

    def __init__(self, season, half, teams=None):
        self.season = season
        self.half = half
        plans = models.HalfPlan.objects.filter(season=season, half=half).select_related("closer")
        if teams is not None:
            plans = plans.filter(team__in=teams)
        self.plans = {plan.team_id: plan for plan in plans}
        self.rows = {}
        for row in models.HalfPlanDay.objects.filter(plan__in=self.plans.values()).select_related(
            "auto_starter", "manual_starter"
        ):
            self.rows[(row.plan_id, row.day)] = row
        ids = set()
        for plan in self.plans.values():
            ids |= set(plan.bench) | set(plan.setup_l) | set(plan.setup_r) | set(plan.sirp) | set(plan.mirp)
            ids |= {e["player"] for e in plan.lineup_vs_lhp + plan.lineup_vs_rhp}
        for row in self.rows.values():
            ids |= {e["player"] for e in row.manual_lineup or []}
        self.players = _players_by_id(ids)
        self.rosters = {}

    def _rosters(self, team):
        if team.id not in self.rosters:
            self.rosters[team.id] = roster_moves.HalfRosters(team, self.season, self.half)
        return self.rosters[team.id]

    def _row(self, team, day):
        plan = self.plans.get(team.id)
        return plan, self.rows.get((plan.id, day)) if plan else None

    def _resolve(self, ids):
        missing = {i for i in ids if i is not None and i not in self.players}
        if missing:
            self.players.update(_players_by_id(missing))
        return [self.players.get(i) for i in ids]

    def _lineup(self, stored):
        players = self._resolve([e["player"] for e in stored])
        return [(p, e["position"]) for p, e in zip(players, stored) if p is not None]

    def live_side(self, game, team, opponent):
        """
        A team's sheet for a game from the plans as they stand now. The bench
        and bullpen hold only that game's roster. unavailable holds the
        starter and batters who aren't on it, such as a sent-down player on
        a road lineup card: the next plan save re-fills a starter, and the
        bench replaces a batter when the game opens (#164).
        """
        eligible = self._rosters(team).for_game(game)

        def on_roster(players):
            return [p for p in players if p is not None and p.id in eligible]

        plan, row = self._row(team, game.day)
        _, opponent_row = self._row(opponent, game.day)
        starter = row.starter if row else None
        opponent_starter = opponent_row.starter if opponent_row else None
        vs = LEFT if opponent_starter is not None and opponent_starter.throws == LEFT else RIGHT
        manual = row.manual_lineup if row else None
        if manual:
            stored = manual
        elif plan:
            stored = plan.lineup_vs_lhp if vs == LEFT else plan.lineup_vs_rhp
        else:
            stored = []
        lineup = self._lineup(stored)
        closer = plan.closer if plan else None
        return {
            "team": team,
            "plan": plan,
            "starter": starter,
            "starter_manual": bool(row and row.manual_starter_id),
            "opponent_starter": opponent_starter,
            "vs": vs,
            "lineup_stored": list(stored),
            "lineup": lineup,
            "lineup_manual": bool(manual),
            "unavailable": {p.id for p, _ in lineup if p.id not in eligible}
            | ({starter.id} if starter is not None and starter.id not in eligible else set()),
            "bench": on_roster(self._resolve(plan.bench)) if plan else [],
            "closer": closer if closer is not None and closer.id in eligible else None,
            "setup_l": on_roster(self._resolve(plan.setup_l)) if plan else [],
            "setup_r": on_roster(self._resolve(plan.setup_r)) if plan else [],
            "sirp": on_roster(self._resolve(plan.sirp)) if plan else [],
            "mirp": on_roster(self._resolve(plan.mirp)) if plan else [],
            "starter_hook": plan.starter_hook if plan else models.HalfPlan.NORMAL_HOOK,
        }

    def opened_side(self, sheet, opponent_sheet, team):
        """A team's sheet for an opened game, read from the game's frozen copy."""
        starter, opponent_starter, closer = self._resolve(
            [sheet["starter"], opponent_sheet["starter"], sheet["closer"]]
        )
        return {
            "team": team,
            "plan": self.plans.get(team.id),
            "starter": starter,
            "starter_manual": sheet["starter_manual"],
            "opponent_starter": opponent_starter,
            "vs": sheet["vs"],
            "lineup_stored": sheet["lineup"],
            "lineup": self._lineup(sheet["lineup"]),
            "lineup_manual": sheet["lineup_manual"],
            "unavailable": set(),
            "bench": self._resolve(sheet["bench"]),
            "closer": closer,
            "setup_l": self._resolve(_sheet_bullpen(sheet, "setup_l")),
            "setup_r": self._resolve(_sheet_bullpen(sheet, "setup_r", "setup")),
            "sirp": self._resolve(_sheet_bullpen(sheet, "sirp")),
            "mirp": self._resolve(_sheet_bullpen(sheet, "mirp", "middle_long")),
            "starter_hook": sheet.get("starter_hook", models.HalfPlan.NORMAL_HOOK),
        }

    def sheet(self, game):
        """Both teams' sheets for a game: {"home": side, "road": side}."""
        home, road = game.series.home_team, game.series.road_team
        if game.opening_sheet:
            frozen = game.opening_sheet
            return {
                "home": self.opened_side(frozen["home"], frozen["road"], home),
                "road": self.opened_side(frozen["road"], frozen["home"], road),
            }
        return {
            "home": self.live_side(game, home, road),
            "road": self.live_side(game, road, home),
        }


def _sheet_bullpen(sheet, key, old_key=None):
    """A frozen bullpen list. A sheet opened before the roles split keeps its old key."""
    if key in sheet:
        return sheet[key] or []
    if old_key and old_key in sheet:
        return sheet[old_key] or []
    return []


def game_sheet(game):
    """Both teams' starters, lineups, bench and bullpen for a game, frozen once it opens."""
    slot = game.series.slot
    book = PlanBook(slot.season, slot.half, teams=[game.series.home_team, game.series.road_team])
    return book.sheet(game)


def _frozen_side(side):
    return {
        "team": side["team"].abbreviation,
        "starter": side["starter"].id if side["starter"] else None,
        "starter_manual": side["starter_manual"],
        "vs": side["vs"],
        "lineup": side["lineup_stored"],
        "lineup_manual": side["lineup_manual"],
        "bench": [p.id for p in side["bench"] if p],
        "closer": side["closer"].id if side["closer"] else None,
        "setup_l": [p.id for p in side["setup_l"] if p],
        "setup_r": [p.id for p in side["setup_r"] if p],
        "sirp": [p.id for p in side["sirp"] if p],
        "mirp": [p.id for p in side["mirp"] if p],
        "starter_hook": side["starter_hook"],
    }


def open_game(game):
    """
    Copy both teams' plans for the game's day onto the game, once. The road
    game (#164) calls this when it opens and copies the result into its log.
    Later plan edits never change an opened game. Returns the frozen sheet,
    which holds Player ids.
    """
    with transaction.atomic():
        game = (
            models.ScheduleGame.objects.select_for_update()
            .select_related("series__slot", "series__home_team", "series__road_team")
            .get(pk=game.pk)
        )
        if game.opened_at is not None:
            return game.opening_sheet
        # The half's first game to open fixes the rosters it started with.
        roster_moves.ensure_snapshot(game.series.slot.season, game.series.slot.half)
        sheet = game_sheet(game)
        game.opening_sheet = {key: _frozen_side(side) for key, side in sheet.items()}
        game.opened_at = timezone.now()
        game.save(update_fields=["opening_sheet", "opened_at", "last_modified"])
        return game.opening_sheet


def plan_rows(plan):
    """
    One row per game in the plan's half for the plan page: the day, the
    opponent, the team's sheet and whether the day can still be edited.
    """
    games = half_games(plan.team, plan.season, plan.half)
    opponents = {
        g.series.road_team if g.series.home_team_id == plan.team_id else g.series.home_team
        for g in games.values()
    }
    book = PlanBook(plan.season, plan.half, teams=[plan.team, *opponents])
    rows = []
    for day in sorted(games):
        game = games[day]
        is_home = game.series.home_team_id == plan.team_id
        sheet = book.sheet(game)
        rows.append(
            {
                "day": day,
                "game": game,
                "is_home": is_home,
                "opponent": game.series.road_team if is_home else game.series.home_team,
                "side": sheet["home"] if is_home else sheet["road"],
                "locked": is_locked(game),
            }
        )
    return rows


def player_line(player, season, position=None):
    """
    What the plan screen shows beside a name: the card's overall line, the
    defense number at the slotted position, and remaining usage. A missing
    card leaves the line empty.
    """
    card = card_for(player, season)
    line = None
    defense = None
    if card is not None:
        line = card.pitcher_line() if is_pitcher(player) else card.hitter_line()
        if position and position in (card.defense or {}):
            defense = card.defense[position]
    summary = usage.usage_summary(player, season)
    return {
        "player": player,
        "position": position,
        "card": card,
        "line": line,
        "defense": defense,
        "usage": summary,
        "capped": not is_pitcher(player) and summary["plate_appearances_left"] == 0,
    }


def is_capped_batter(player, season):
    """A batter with no plate appearances left. The plan flags him; the bench replaces him when the game opens."""
    return usage.usage_summary(player, season)["plate_appearances_left"] == 0
