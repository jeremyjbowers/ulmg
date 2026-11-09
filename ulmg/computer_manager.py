# ABOUTME: The computer manager's choices in a sim game: its starter and his hook, bullpen roles and how it uses them, steals and bench moves.
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

# How the closer is used. Ninth waits for a save in the ninth or later. Eighth also
# takes the eighth of a game within three runs. Leverage comes in from the sixth
# when the tying run is already on base, at bat or on deck.
NINTH = "ninth"
EIGHTH = "eighth"
LEVERAGE = "leverage"
CLOSER_USAGES = (NINTH, EIGHTH, LEVERAGE)
DEFAULT_CLOSER_USAGE = NINTH
LEVERAGE_INNING = 6

# How setup and short relief are used. Standard is the seventh and the eighth.
# Early moves that window up one inning. Tight uses it only with a lead.
STANDARD = "standard"
EARLY = "early"
TIGHT = "tight"
RELIEF_USAGES = (STANDARD, EARLY, TIGHT)
DEFAULT_RELIEF_USAGE = STANDARD

# How the bench is used. Stand only replaces someone the rules force out.
# Pinch pinch-hits, and pinch-runs, in a late game the side does not lead.
# Glove replaces a fielder once the side is ahead.
STAND = "stand"
PINCH = "pinch"
GLOVE = "glove"
BENCH_USAGES = (STAND, PINCH, GLOVE)
DEFAULT_BENCH_USAGE = STAND
PINCH_INNING = 7
PINCH_RUN_INNING = 8
PINCH_GAP = 20
PINCH_MAX_DEFICIT = 3
RUN_SPD_GAP = 2.0
GLOVE_INNING = 7
GLOVE_GAP = 5.0


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


def is_high_leverage(lead, runners_on):
    """
    A game within three runs with someone already on base and the tying run
    on base, at bat or on deck. A tie with a runner on counts; a clean inning
    does not, however small the lead.
    """
    if runners_on <= 0 or not (0 <= lead <= SAVE_MAX_LEAD):
        return False
    if lead == 0:
        return True
    return lead <= runners_on + 2


def bullpen_role(
    inning, lead, runners_on, outs, batter_bats="R", closer_usage=NINTH, relief_usage=STANDARD
):
    """
    The role the situation calls for. lead is the fielding side's, negative
    when it trails. batter_bats is the hitter due up.

    closer_usage ninth waits for a save in the ninth or later. eighth also
    takes the eighth when the game is within three runs. leverage takes a
    high-leverage spot from the sixth on, and still closes a ninth-inning save.

    relief_usage standard is short relief in the seventh and setup, by the
    batter's hand, in the eighth, when the lead is within three or the game
    is tied. early moves that window up one inning, and setup takes the
    seventh ahead of short relief. tight uses those innings only with a lead.
    Anything else is middle relief. An unknown usage reads as the default.
    """
    closer_usage = closer_usage if closer_usage in CLOSER_USAGES else NINTH
    relief_usage = relief_usage if relief_usage in RELIEF_USAGES else STANDARD
    if _closer_spot(closer_usage, inning, lead, runners_on, outs):
        return CLOSER
    close = 1 <= lead <= SETUP_MAX_LEAD if relief_usage == TIGHT else 0 <= lead <= SETUP_MAX_LEAD
    setup_innings = (SETUP_INNING - 1, SETUP_INNING) if relief_usage == EARLY else (SETUP_INNING,)
    sirp_innings = (SIRP_INNING - 1,) if relief_usage == EARLY else (SIRP_INNING,)
    if close and inning in setup_innings:
        return SETUP_L if batter_bats == "L" else SETUP_R
    if close and inning in sirp_innings:
        return SIRP
    return MIRP


def _closer_spot(usage, inning, lead, runners_on, outs):
    save = inning >= CLOSER_FIRST_INNING and is_save_situation(lead, runners_on, outs)
    if usage == LEVERAGE:
        return save or (inning >= LEVERAGE_INNING and is_high_leverage(lead, runners_on))
    if usage == EIGHTH:
        return save or (inning == SETUP_INNING and 0 <= lead <= SETUP_MAX_LEAD)
    return save


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


def wants_pinch_hit(style, inning, batting_lead):
    """Pinch-hit from the seventh on, when the side is tied or trails by at most three."""
    return style == PINCH and inning >= PINCH_INNING and -PINCH_MAX_DEFICIT <= batting_lead <= 0


def pinch_hitter(due_wrc, bench):
    """
    The first player in bench order, as (player, wrc_plus), who beats the
    batter due up by PINCH_GAP. No wRC+ on the due batter means no pinch hit.
    """
    if due_wrc is None:
        return None
    for player, wrc in bench:
        if wrc is not None and wrc >= due_wrc + PINCH_GAP:
            return player
    return None


def wants_pinch_run(style, inning, batting_lead):
    """Pinch-run from the eighth on, when the side is tied or trails by one."""
    return style == PINCH and inning >= PINCH_RUN_INNING and -1 <= batting_lead <= 0


def pinch_runner(runner_spd, bench):
    """The first player in bench order, as (player, spd), who is RUN_SPD_GAP faster than the runner."""
    if runner_spd is None:
        return None
    for player, spd in bench:
        if spd is not None and spd >= runner_spd + RUN_SPD_GAP:
            return player
    return None


def wants_glove(style, inning, fielding_lead, half_inning_start):
    """A defensive replacement at the start of a half inning from the seventh on, when the side leads."""
    return style == GLOVE and half_inning_start and inning >= GLOVE_INNING and fielding_lead >= 1


def defensive_replacement(fielders, bench):
    """
    The biggest glove upgrade of at least GLOVE_GAP defensive runs.

    fielders is (slot, position, runs) for the men in the field. bench is
    (player, {position: runs}) in bench order. A player with no rating at
    the position is left where he is. Ties go to the earlier bench player,
    then the earlier slot. Returns (slot, player), or None.
    """
    best = None
    for slot, position, runs in fielders:
        if position in ("DH", "P") or runs is None:
            continue
        for index, (player, gloves) in enumerate(bench):
            upgrade = gloves.get(position)
            if upgrade is None:
                continue
            gain = upgrade - runs
            if gain < GLOVE_GAP:
                continue
            rank = (-gain, index, slot)
            if best is None or rank < best[0]:
                best = (rank, slot, player)
    if best is None:
        return None
    return best[1], best[2]
