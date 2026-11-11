# ABOUTME: Test-setup defaults for setup_sim_season: picks each team's rotation, bullpen, lineups and bench from its 30-man.
# ABOUTME: These picks exist only so testers get a playable plan; managers' real plans go through the plan pages.

from ulmg import models, plans, usage

# Everything in this module is for building a test season. None of it is a
# league rule, and nothing outside setup_sim_season should call it.
#
# The defaults, from the 30-man players who have a card for the season:
# - Rotation: the five pitchers with the most card-season starts (gs).
# - Closer: the bullpen arm with the most card-season saves (sv), then holds (hld).
# - Setup: the next two by holds, then saves.
# - Middle relief: every other pitcher who did not start, in the same order.
# - Long relief: every other pitcher who started, in the same order.
# - Lineups: the nine best hitters by card wrc_plus. The best eight who can
#   cover C, 1B, 2B, 3B, SS, LF, CF and RF field those positions (a position
#   is playable when the card has a defense rating there), and the best
#   remaining bat is the DH. Batting order is by wrc_plus. Both lineup cards
#   get the same nine, because a card has one wrc_plus; the vs-LHP / vs-RHP
#   choice on each day is still made by the plan rules.
# - Bench: every other hitter, by wrc_plus.
# Ties go to the player whose name sorts first. A card without wrc_plus ranks
# below every card with one.

ROTATION_SIZE = 5
SETUP_ARMS = 2
FIELD_POSITIONS = [p for p in plans.LINEUP_POSITIONS if p != "DH"]


def _count(stats, key):
    try:
        return int(stats.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _hitter_rank(player, card):
    wrc_plus = card.wrc_plus if card.wrc_plus is not None else float("-inf")
    return (-wrc_plus, player.name, player.id)


def _playable(card):
    defense = card.defense or {}
    return [p for p in FIELD_POSITIONS if defense.get(p) is not None]


def _fielders(hitters, cards):
    """
    The best hitters who can cover the eight field positions, as
    {position: player}. Hitters are taken best first; each one joins when
    the players already chosen can be rearranged to make room for him.
    """
    assigned = {}

    def place(player, tried):
        for position in _playable(cards[player.id]):
            if position in tried:
                continue
            tried.add(position)
            holder = assigned.get(position)
            if holder is None or place(holder, tried):
                assigned[position] = player
                return True
        return False

    for player in hitters:
        if len(assigned) == len(FIELD_POSITIONS):
            break
        place(player, set())
    return assigned


def _lineup(hitters, cards):
    """The default lineup entries from hitters ranked best first, and its problems."""
    assigned = _fielders(hitters, cards)
    problems = [
        f"No hitter with a card can play {position}."
        for position in FIELD_POSITIONS
        if position not in assigned
    ]
    position_of = {player.id: position for position, player in assigned.items()}
    designated = next((p for p in hitters if p.id not in position_of), None)
    if designated is None:
        problems.append("Too few hitters with cards for a designated hitter.")
    else:
        position_of[designated.id] = "DH"

    batting = [p for p in hitters if p.id in position_of]
    entries = [
        {"order": i + 1, "player": player, "position": position_of[player.id]}
        for i, player in enumerate(batting)
    ]
    return entries, problems


def default_plan(team, season):
    """
    The test-setup plan fields for a team's 30-man, ready for plans.fill_plan,
    and the problems found picking them: players without a card (left out)
    and positions nobody can fill.
    """
    problems = []
    cards = {}
    for player in plans.thirty_man(team):
        card = plans.card_for(player, season)
        if card is None:
            problems.append(f"No card for {player.name}; left out of the plan.")
        else:
            cards[player.id] = (player, card)

    pitchers = [player for player, _ in cards.values() if plans.can_pitch(player)]
    pitch_stats = {p.id: usage.card_stats(p, season)[1] for p in pitchers}

    starters = sorted(
        (p for p in pitchers if _count(pitch_stats[p.id], "gs") > 0),
        key=lambda p: (-_count(pitch_stats[p.id], "gs"), p.name, p.id),
    )
    rotation = starters[:ROTATION_SIZE]
    if len(rotation) < ROTATION_SIZE:
        problems.append(
            f"Only {len(rotation)} pitchers with card-season starts; the rotation has {len(rotation)}."
        )

    bullpen = [p for p in pitchers if p not in rotation]
    by_saves = sorted(
        bullpen,
        key=lambda p: (-_count(pitch_stats[p.id], "sv"), -_count(pitch_stats[p.id], "hld"), p.name, p.id),
    )
    closer = by_saves[0] if by_saves else None
    by_holds = sorted(
        (p for p in bullpen if p != closer),
        key=lambda p: (-_count(pitch_stats[p.id], "hld"), -_count(pitch_stats[p.id], "sv"), p.name, p.id),
    )

    hitter_cards = {pid: card for pid, (player, card) in cards.items() if not plans.is_pitcher(player)}
    hitters = sorted(
        (player for player, _ in cards.values() if player.id in hitter_cards),
        key=lambda p: _hitter_rank(p, hitter_cards[p.id]),
    )
    lineup, lineup_problems = _lineup(hitters, hitter_cards)
    problems += lineup_problems
    in_lineup = {entry["player"].id for entry in lineup}

    rest = by_holds[SETUP_ARMS:]
    fields = {
        "rotation": rotation,
        "closer": closer,
        "setup": by_holds[:SETUP_ARMS],
        "middle": [p for p in rest if _count(pitch_stats[p.id], "gs") == 0],
        "long_relief": [p for p in rest if _count(pitch_stats[p.id], "gs") > 0],
        "bench": [p for p in hitters if p.id not in in_lineup],
        "lineup_vs_lhp": lineup,
        "lineup_vs_rhp": [dict(entry) for entry in lineup],
    }
    return fields, problems


def fill_season_plans(season, halves):
    """
    Replace the season's half plans with the test-setup defaults for every
    team, filling the given halves through plans.fill_plan. The second half
    is filled whatever TEAM_SEASON_HALF says. Returns [(team, {half:
    problems}, setup problems)] in team order.
    """
    models.HalfPlan.objects.filter(season=season).delete()
    results = []
    for team in models.Team.objects.order_by("abbreviation"):
        fields, problems = default_plan(team, season)
        by_half = {}
        for half in halves:
            plan = plans.plan_for(team, season, half)
            by_half[half] = plans.fill_plan(plan, ignore_half_lock=(half == 2), **fields)
        results.append((team, by_half, problems))
    return results
