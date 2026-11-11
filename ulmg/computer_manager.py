# ABOUTME: The computer manager's choices in a sim game: its starter and his hook, bullpen roles, steals and bench replacements.
# ABOUTME: Each choice walks an order from the half plan and takes the first player a legality check passes.

from dataclasses import dataclass, field

# Bullpen roles, named as the half plan's fields. OTHER is every other pitcher on the game's roster.
CLOSER = "closer"
SIRP = "sirp"
MIRP = "mirp"
OTHER = "other"
ROLE_LABELS = {
    CLOSER: "closer",
    SIRP: "single-inning",
    MIRP: "multi-inning",
    OTHER: "other arms",
}
# When the situation's group has no available arm, the next groups in this order.
# Multi-inning goes before single-inning and the closer, so a missing arm does not burn a leverage arm first.
FALLBACK_ORDER = (MIRP, SIRP, CLOSER)

# Rule 9.19(d)(1): a lead of no more than three runs, with at least an inning to pitch.
SAVE_MAX_LEAD = 3
# A close game is within this many runs either way. Traditional usage wants one inning from the 6th on.
CLOSE_RUNS = 3

# Bullpen usage, the half plan's choices. Each one says when the closer and
# single-inning relief come in. Anything they do not claim is multi-inning
# relief. quick, normal and slow are the earlier names, still read from a
# game that opened before the bullpen page offered these buttons.
def _usage(
    note,
    *,
    sirp_innings=(),
    sirp_from=None,
    closer_first=9,
    closer="save",
    sirp_min_lead=0,
    sirp_max_lead=SAVE_MAX_LEAD,
    closer_max_lead=None,
    closer_min_lead=1,
):
    return {
        "note": note,
        "sirp_innings": sirp_innings,
        "sirp_from": sirp_from,
        "sirp_min_lead": sirp_min_lead,
        "sirp_max_lead": sirp_max_lead,
        "closer_first": closer_first,
        "closer": closer,
        "closer_max_lead": closer_max_lead,
        "closer_min_lead": closer_min_lead,
    }


_TRADITIONAL = _usage(
    "The closer pitches the ninth or later in a save situation. Single-inning relief pitches from the sixth "
    "on when the game is within three runs. Multi-inning relief works before the sixth, or when the game is not that close.",
    sirp_from=6,
    sirp_min_lead=-CLOSE_RUNS,
    sirp_max_lead=CLOSE_RUNS,
)
BULLPEN_WINDOWS = {
    "traditional": _TRADITIONAL,
    "normal": _TRADITIONAL,
    "leverage": _usage(
        "The closer comes in from the seventh on for a one- or two-run save, a ninth-inning save, "
        "or a one-run game or a tie with a runner on. Single-inning relief pitches the sixth, seventh and eighth "
        "when the lead is three or fewer and the closer stays in the pen. Multi-inning relief works the rest.",
        sirp_innings=(6, 7, 8),
        closer_first=7,
        closer="traffic",
    ),
    "quick": _usage(
        "Single-inning relief in the 6th, 7th and 8th, tied or leading by 3 or fewer. "
        "The closer from the 8th on, in a save situation. Multi-inning relief otherwise.",
        sirp_innings=(6, 7, 8),
        closer_first=8,
    ),
    "fireman": _usage(
        "The closer is a multi-inning ace. From the sixth on he pitches a tie or a one-run lead, "
        "and from the eighth on a save, and he stays while that is still true. Single-inning relief holds a two- or "
        "three-run lead in the seventh and eighth. Multi-inning relief works the rest.",
        sirp_innings=(7, 8),
        closer_first=6,
        closer="fireman",
        sirp_min_lead=2,
    ),
    "protect": _usage(
        "A lead gets the good arms. Single-inning relief pitches the seventh and eighth when leading by one, two or three. "
        "The closer pitches the ninth or later whenever the lead is three or fewer, save or not. "
        "Tied or trailing, multi-inning relief works.",
        sirp_innings=(7, 8),
        closer_first=9,
        closer="lead",
        sirp_min_lead=1,
        closer_max_lead=SAVE_MAX_LEAD,
    ),
    "save": _usage(
        "The closer pitches the ninth only in a save of one or two runs. Single-inning relief pitches the eighth "
        "only in a tie or a one-run lead. Multi-inning relief works the rest.",
        sirp_innings=(8,),
        closer_first=9,
        closer_max_lead=2,
        sirp_max_lead=1,
    ),
    "slow": _usage(
        "Single-inning relief in the 8th, tied or leading by 3 or fewer. "
        "The closer from the 9th on, in a save situation. Multi-inning relief otherwise.",
        sirp_innings=(8,),
        closer_first=9,
    ),
}
DEFAULT_BULLPEN = "traditional"

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


def bullpen_order(closer, sirp, mirp, others=()):
    """
    The order a human's pitching choices are listed in: the closer, then
    single-inning relief, then multi-inning relief, then any other pitcher
    on the game's roster.
    """
    return [closer, *sirp, *mirp, *others]


def _window(logic):
    return BULLPEN_WINDOWS.get(logic, BULLPEN_WINDOWS[DEFAULT_BULLPEN])


def describe_bullpen_logic(logic):
    """The sentence the bullpen page shows for this usage. An unknown usage reads as traditional."""
    return _window(logic)["note"]


def _calls_closer(window, inning, lead, runners_on, outs):
    if inning < window["closer_first"]:
        return False
    mode = window["closer"]
    save = is_save_situation(lead, runners_on, outs)
    if mode == "save":
        cap = window["closer_max_lead"]
        return save and (cap is None or lead <= cap)
    if mode == "lead":
        return window["closer_min_lead"] <= lead <= window["closer_max_lead"]
    if mode == "fireman":
        if lead in (0, 1):
            return True
        return inning >= 8 and save
    if mode == "traffic":
        cap = window["closer_max_lead"]
        if inning >= 9 and save and (cap is None or lead <= cap):
            return True
        if save and 0 < lead <= 2:
            return True
        return lead in (-1, 0, 1) and runners_on >= 1
    return False


def _calls_sirp(window, inning, lead):
    if not window["sirp_min_lead"] <= lead <= window["sirp_max_lead"]:
        return False
    if window["sirp_from"] is not None and inning >= window["sirp_from"]:
        return True
    return inning in window["sirp_innings"]


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


def bullpen_role(inning, lead, runners_on, outs, logic=None):
    """
    The role the situation calls for under a bullpen usage. lead is the
    fielding side's, negative when it trails. An unknown usage reads as
    traditional: the closer in a save from the 9th on, single-inning relief
    from the 6th on when the game is within three runs, and multi-inning
    relief otherwise.
    """
    window = _window(logic)
    if _calls_closer(window, inning, lead, runners_on, outs):
        return CLOSER
    if _calls_sirp(window, inning, lead):
        return SIRP
    return MIRP


def group_order(role):
    """The role's group, then the others in fallback order, then every other pitcher."""
    return [role] + [group for group in FALLBACK_ORDER if group != role] + [OTHER]


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
