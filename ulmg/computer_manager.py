# ABOUTME: The computer manager's choices in a sim game: its starter and his hook, bullpen roles, steals and bench replacements.
# ABOUTME: Each choice walks an order from the half plan and takes the first player a legality check passes.

from dataclasses import dataclass, field

# Bullpen roles, named as the half plan's fields. OTHER is every other pitcher on the game's roster.
CLOSER = "closer"
SETUP_L = "setup_l"
SETUP_R = "setup_r"
SIRP = "sirp"
MIRP = "mirp"
OTHER = "other"
ROLE_LABELS = {
    CLOSER: "closer",
    SETUP_L: "setup vs L",
    SETUP_R: "setup vs R",
    SIRP: "short relief",
    MIRP: "middle relief",
    OTHER: "other arms",
}

# The closer: the ninth inning or later, in a save situation.
CLOSER_FIRST_INNING = 9
# Rule 9.19(d)(1): a lead of no more than three runs, with at least an inning to pitch.
SAVE_MAX_LEAD = 3
# A one-inning bridge in the seventh, then a setup man in the eighth, when the lead is this small or the game is tied.
SIRP_INNING = 7
SETUP_INNING = 8
SETUP_MAX_LEAD = 3

# The starter hook, by the half plan's setting: the share of his fatigue ceiling he may spend,
# and the runs he may allow in the game, before the computer pulls him.
HOOK_CEILING_SHARE = {"quick": 0.85, "normal": 0.95, "slow": 1.00}
HOOK_RUNS = {"quick": 4, "normal": 5, "slow": 6}
DEFAULT_HOOK = "normal"


@dataclass
class Choice:
    """
    The player the computer chose, or None, and the (player, reason) pairs it
    passed over on the way. group is the bullpen role he was taken from.
    """

    player: object = None
    skipped: list = field(default_factory=list)
    group: str = None


def _first_legal(candidates, problem):
    """The first candidate problem() finds nothing wrong with. problem(player) returns a reason or None."""
    choice = Choice()
    seen = set()
    for player in candidates:
        if player is None or player.id in seen:
            continue
        seen.add(player.id)
        reason = problem(player)
        if reason is None:
            choice.player = player
            return choice
        choice.skipped.append((player, reason))
    return choice


def starter(planned, rotation, problem):
    """
    The computer's starter. The planned starter when he is legal; otherwise
    the next legal pitcher in rotation order after him, wrapping around. A
    planned spot starter who isn't in the rotation is followed by the
    rotation from the top.
    """
    rotation = list(rotation)
    if planned is not None and planned in rotation:
        index = rotation.index(planned)
        order = [planned] + rotation[index + 1:] + rotation[:index]
    else:
        order = [planned] + rotation
    return _first_legal(order, problem)


def bullpen_order(closer, setup_l, setup_r, sirp, mirp, others=()):
    """
    The order a human's pitching choices are listed in: the closer, then
    setup against left-handed batters, setup against right-handed batters,
    short relief, middle relief, then any other pitcher on the game's roster.
    """
    return [closer, *setup_l, *setup_r, *sirp, *mirp, *others]


def is_save_situation(lead, runners_on, outs):
    """
    Rule 9.19(d) for a pitcher entering in the ninth inning or later: a lead
    of three or fewer with a full inning left to pitch, which there is only
    with nobody out, or the tying run on base, at bat or on deck. (d)(3)'s
    three innings can't be pitched from the ninth on, since the game ends
    with the half inning when the fielding side still leads.
    """
    if lead <= 0:
        return False
    if lead <= SAVE_MAX_LEAD and outs == 0:
        return True
    # The runners, the batter and the man on deck could each bring a run in.
    return lead <= runners_on + 2


def bullpen_role(inning, lead, runners_on, outs, batter_bats="R"):
    """
    The role the situation calls for. lead is the fielding side's, negative
    when it trails. batter_bats is the hitter due up: a left-handed batter
    in the eighth of a close game calls for setup vs L, and a right-handed
    or switch hitter calls for setup vs R. The seventh of a close game is
    one inning of short relief. Anything earlier, or a game that is not
    close, is middle relief, which can go more than one inning.
    """
    if inning >= CLOSER_FIRST_INNING and is_save_situation(lead, runners_on, outs):
        return CLOSER
    if 0 <= lead <= SETUP_MAX_LEAD:
        if inning == SETUP_INNING:
            return SETUP_L if batter_bats == "L" else SETUP_R
        if inning == SIRP_INNING:
            return SIRP
    return MIRP


def group_order(role):
    """
    The role's own group, then the next groups a manager would try, then
    every other pitcher. A save goes to setup before a middle man. A short
    or middle need goes to the other multi-inning and one-inning arms before
    it spends the closer.
    """
    if role == SETUP_L:
        rest = (SETUP_R, SIRP, MIRP, CLOSER)
    elif role == SETUP_R:
        rest = (SETUP_L, SIRP, MIRP, CLOSER)
    elif role == SIRP:
        rest = (MIRP, SETUP_R, SETUP_L, CLOSER)
    elif role == CLOSER:
        rest = (SETUP_R, SETUP_L, SIRP, MIRP)
    else:
        rest = (SIRP, SETUP_R, SETUP_L, CLOSER)
    return [role, *rest, OTHER]


def _first_in_groups(order, groups, problem):
    choice = Choice()
    seen = set()
    for group in order:
        players = [p for p in groups.get(group, []) if p is not None and p.id not in seen]
        seen |= {p.id for p in players}
        found = _first_legal(players, problem)
        choice.skipped += found.skipped
        if found.player is not None:
            choice.player = found.player
            choice.group = group
            return choice
    return choice


def reliever(role, groups, problem):
    """
    The arm the computer brings in when its mound needs one: the first
    available in the role's group, then in each group of group_order(role).
    groups maps each role to its players in plan order.
    """
    return _first_in_groups(group_order(role), groups, problem)


def preferred_arm(role, groups, problem):
    """The first available arm in the role's own group only, for a change the mound doesn't force."""
    return _first_in_groups([role], groups, problem)


def hook_reason(hook, fatigue):
    """
    Why the starter's hook pulls him now, or None. fatigue is the engine's
    state for him: effort against his drawn ceiling, and the runs scored
    while he pitched. The engine's own fatigue line and his per-game limit
    take him out without asking this.
    """
    hook = hook if hook in HOOK_RUNS else DEFAULT_HOOK
    runs = fatigue.get("runs_allowed", 0)
    if runs >= HOOK_RUNS[hook]:
        return f"he has allowed {runs} runs, and a {hook} hook pulls a starter at {HOOK_RUNS[hook]}."
    share = HOOK_CEILING_SHARE[hook]
    ceiling = fatigue.get("ceiling") or 0
    effort = fatigue.get("effort", 0)
    if ceiling > 0 and effort >= share * ceiling:
        return (
            f"he has spent {effort / ceiling:.0%} of his fatigue ceiling, "
            f"and a {hook} hook pulls a starter at {share:.0%}."
        )
    return None


def is_steal_situation(bases, outs):
    """A runner on first, second base open, and fewer than two outs."""
    return bool(bases.get("first")) and not bases.get("second") and outs < 2


def calls_steal(attempt_rate, draw):
    """Whether the computer sends the runner. draw is uniform in [0, 1), so this is true with probability attempt_rate."""
    return attempt_rate is not None and draw < attempt_rate


def bench_replacement(bench, problem):
    """The first legal player in the side's bench order."""
    return _first_legal(bench, problem)
