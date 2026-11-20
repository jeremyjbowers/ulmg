# ABOUTME: The computer manager's choices in a sim game: its starter and his hook, bullpen roles, steals, pinch hitters and defensive replacements.
# ABOUTME: Each choice walks an order from the half plan and takes the first player a legality check passes.

import json
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
# A single-inning outing runs to 1.2 innings, including the next half inning. Not two.
SIRP_MAX_OUTS = 5

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
    hold_role=SIRP,
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
        # The group that pitches the innings the closer does not take. The other of SIRP and MIRP pitches the rest.
        "hold_role": hold_role,
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
# A plan's own rules, the same settings a shortcut is filled in with.
ADVANCED = "advanced"
ADVANCED_NOTE = (
    "Set when the closer comes in, which group pitches the high-leverage innings he doesn't, "
    "and how close the game has to be. The other group pitches the rest."
)

# The high-leverage window, as the advanced form names it. The first number is sirp_from.
# An empty inning list with no sirp_from is no window: the other group pitches every other spot.
HOLD_INNINGS = {
    "from6": (6, ()),
    "678": (None, (6, 7, 8)),
    "78": (None, (7, 8)),
    "8": (None, (8,)),
    "never": (None, ()),
}
_INNING_NAME = {6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth"}
_LEAD_WORD = {1: "one", 2: "two", 3: "three", 6: "six"}

# The advanced form. show is the closer modes that reveal the row.
ADV_FIELDS = (
    {
        "name": "adv_closer_first",
        "legend": "Closer comes in from the",
        "hint": "",
        "show": "",
        "choices": (("6", "6th"), ("7", "7th"), ("8", "8th"), ("9", "9th")),
    },
    {
        "name": "adv_closer",
        "legend": "He comes in for",
        "hint": "A save is a save situation. A lead is save or not. Fireman is a tie or a one-run lead, and a save from the eighth. Highest leverage is a one- or two-run save, a ninth-inning save, or a one-run game or a tie with a runner on.",
        "show": "",
        "choices": (
            ("save", "A save"),
            ("lead", "A lead"),
            ("fireman", "Fireman"),
            ("traffic", "Highest leverage"),
        ),
    },
    {
        "name": "adv_closer_max_lead",
        "legend": "Lead of at most",
        "hint": "For a save, the biggest save. For a lead, the biggest lead. For highest leverage, the biggest ninth-inning save.",
        "show": "save lead traffic",
        "choices": (("1", "1"), ("2", "2"), ("3", "3"), ("any", "Any")),
    },
    {
        "name": "adv_closer_min_lead",
        "legend": "Leading by at least",
        "hint": "",
        "show": "lead",
        "choices": (("0", "Tied"), ("1", "1"), ("2", "2"), ("3", "3")),
    },
    {
        "name": "adv_hold_role",
        "legend": "High-leverage relief uses",
        "hint": "The innings the closer doesn't take. MIRP here when your best arms are multi-inning relievers, and the SIRP column is left for the other spots.",
        "show": "",
        "choices": ((SIRP, "SIRP"), (MIRP, "MIRP")),
    },
    {
        "name": "adv_hold_innings",
        "legend": "In these innings",
        "hint": "None means the other column pitches every spot the closer doesn't.",
        "show": "",
        "choices": (
            ("from6", "6th on"),
            ("678", "6th, 7th and 8th"),
            ("78", "7th and 8th"),
            ("8", "8th only"),
            ("never", "None"),
        ),
    },
    {
        "name": "adv_hold_min_lead",
        "legend": "When the score is from",
        "hint": "",
        "show": "",
        "choices": (
            ("-6", "Down 6"),
            ("-3", "Down 3"),
            ("-1", "Down 1"),
            ("0", "Tied"),
            ("1", "Up 1"),
            ("2", "Up 2"),
            ("3", "Up 3"),
        ),
    },
    {
        "name": "adv_hold_max_lead",
        "legend": "Through",
        "hint": "",
        "show": "",
        "choices": (("0", "Tied"), ("1", "Up 1"), ("2", "Up 2"), ("3", "Up 3"), ("6", "Up 6")),
    },
)

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


def describe_bullpen_logic(logic, rules=None):
    """The sentence the bullpen page shows for this usage. An unknown usage reads as traditional."""
    if logic == ADVANCED:
        cleaned, errors = interpret_rules(rules)
        if errors:
            return ADVANCED_NOTE
        return describe_rules(cleaned)
    return _window(logic)["note"]


def _resolve_window(logic, rules):
    if logic == ADVANCED:
        cleaned, errors = interpret_rules(rules)
        if not errors:
            return _usage(
                describe_rules(cleaned),
                sirp_innings=tuple(cleaned["hold_innings"]),
                sirp_from=cleaned["hold_from"],
                closer_first=cleaned["closer_first"],
                closer=cleaned["closer"],
                sirp_min_lead=cleaned["hold_min_lead"],
                sirp_max_lead=cleaned["hold_max_lead"],
                closer_max_lead=cleaned["closer_max_lead"],
                closer_min_lead=cleaned["closer_min_lead"],
                hold_role=cleaned["hold_role"],
            )
    return _window(logic)


def rules_for(logic):
    """The settings a shortcut is filled in with, or None when logic is not a shortcut."""
    window = BULLPEN_WINDOWS.get(logic)
    if window is None:
        return None
    return {
        "closer_first": window["closer_first"],
        "closer": window["closer"],
        "closer_min_lead": window["closer_min_lead"],
        "closer_max_lead": window["closer_max_lead"],
        "hold_role": window.get("hold_role", SIRP),
        "hold_from": window["sirp_from"],
        "hold_innings": list(window["sirp_innings"]),
        "hold_min_lead": window["sirp_min_lead"],
        "hold_max_lead": window["sirp_max_lead"],
    }


def rules_for_display(logic, stored):
    """Rules to show on the form: a saved advanced plan, otherwise the shortcut's own settings."""
    if logic == ADVANCED:
        cleaned, errors = interpret_rules(stored)
        if not errors:
            return cleaned
    found = rules_for(logic)
    return found if found is not None else rules_for(DEFAULT_BULLPEN)


def _as_int(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _hold_code(hold_from, hold_innings):
    if hold_from is not None:
        hold_from = _as_int(hold_from)
    if not isinstance(hold_innings, (list, tuple)):
        return None
    innings = []
    for item in hold_innings:
        number = _as_int(item)
        if number is None:
            return None
        innings.append(number)
    found = (hold_from, tuple(innings))
    for code, pattern in HOLD_INNINGS.items():
        if pattern == found:
            return code
    return None


def interpret_rules(rules):
    """
    (canonical rules, error messages). Canonical rules are what a plan stores
    and what an opened game freezes. Unusable rules have no canonical form.
    """
    if not isinstance(rules, dict):
        return None, ["Set the advanced bullpen rules."]
    errors = []
    closer_first = _as_int(rules.get("closer_first"))
    if closer_first not in (6, 7, 8, 9):
        errors.append("The closer's first inning has to be the 6th, 7th, 8th or 9th.")
    closer = rules.get("closer")
    if closer not in ("save", "lead", "fireman", "traffic"):
        errors.append("The closer comes in for a save, a lead, a fireman outing or the highest leverage.")
    closer_min = _as_int(rules.get("closer_min_lead"))
    if closer_min not in (0, 1, 2, 3):
        errors.append("The closer's smallest lead has to be a tie or a lead of 1, 2 or 3.")
    raw_cap = rules.get("closer_max_lead")
    if raw_cap in (None, "any", ""):
        closer_max = None
    else:
        closer_max = _as_int(raw_cap)
        if closer_max not in (1, 2, 3):
            errors.append("The closer's lead cap has to be 1, 2, 3 or any.")
    if (
        closer == "lead"
        and closer_min is not None
        and closer_max is not None
        and closer_min > closer_max
    ):
        errors.append("The closer's lead has to run from a smaller lead to a larger one.")
    hold_role = rules.get("hold_role")
    if hold_role not in (SIRP, MIRP):
        errors.append("The high-leverage group has to be SIRP or MIRP.")
    code = _hold_code(rules.get("hold_from"), rules.get("hold_innings"))
    if code is None:
        errors.append(
            "The high-leverage innings have to be the 6th on, the 6th through 8th, "
            "the 7th and 8th, the 8th only, or none."
        )
    hold_min = _as_int(rules.get("hold_min_lead"))
    if hold_min not in (-6, -3, -1, 0, 1, 2, 3):
        errors.append("The high-leverage lead has to start at down 6, down 3, down 1, a tie, or up 1, 2 or 3.")
    hold_max = _as_int(rules.get("hold_max_lead"))
    if hold_max not in (0, 1, 2, 3, 6):
        errors.append("The high-leverage lead has to end at a tie or up 1, 2, 3 or 6.")
    if hold_min is not None and hold_max is not None and hold_min > hold_max:
        errors.append("The high-leverage lead has to run from a smaller lead to a larger one.")
    if errors:
        return None, errors
    pattern = HOLD_INNINGS[code]
    return {
        "closer_first": closer_first,
        "closer": closer,
        "closer_min_lead": closer_min,
        "closer_max_lead": closer_max,
        "hold_role": hold_role,
        "hold_from": pattern[0],
        "hold_innings": list(pattern[1]),
        "hold_min_lead": hold_min,
        "hold_max_lead": hold_max,
    }, []


def form_values(rules):
    """The advanced inputs for these rules. A missing lead cap is Any."""
    cap = rules["closer_max_lead"]
    return {
        "adv_closer_first": str(rules["closer_first"]),
        "adv_closer": rules["closer"],
        "adv_closer_min_lead": str(rules["closer_min_lead"]),
        "adv_closer_max_lead": "any" if cap is None else str(cap),
        "adv_hold_role": rules["hold_role"],
        "adv_hold_innings": _hold_code(rules["hold_from"], rules["hold_innings"]),
        "adv_hold_min_lead": str(rules["hold_min_lead"]),
        "adv_hold_max_lead": str(rules["hold_max_lead"]),
    }


def rules_from_post(post):
    """The advanced rules posted with the bullpen form, and any reason they cannot be used."""
    code = post.get("adv_hold_innings")
    pattern = HOLD_INNINGS.get(code)
    cap = post.get("adv_closer_max_lead")
    return interpret_rules({
        "closer_first": post.get("adv_closer_first"),
        "closer": post.get("adv_closer"),
        "closer_min_lead": post.get("adv_closer_min_lead"),
        "closer_max_lead": None if cap in (None, "", "any") else cap,
        "hold_role": post.get("adv_hold_role"),
        "hold_from": pattern[0] if pattern else "bad",
        "hold_innings": list(pattern[1]) if pattern else "bad",
        "hold_min_lead": post.get("adv_hold_min_lead"),
        "hold_max_lead": post.get("adv_hold_max_lead"),
    })


def posted_form_values(post):
    """Whatever the form posted, so a refused save can show the same buttons."""
    return {spec["name"]: post.get(spec["name"]) or "" for spec in ADV_FIELDS}


def adv_fields(values):
    """The advanced rows, with the selected button and the rows the closer mode hides."""
    mode = values.get("adv_closer") or ""
    fields = []
    for spec in ADV_FIELDS:
        show = spec["show"]
        current = str(values.get(spec["name"], ""))
        fields.append({
            "name": spec["name"],
            "legend": spec["legend"],
            "hint": spec["hint"],
            "show": show,
            "hidden": bool(show) and mode not in show.split(),
            "value": current,
            "choices": [
                {"value": value, "label": label, "selected": value == current}
                for value, label in spec["choices"]
            ],
        })
    return fields


def shortcut_rules_json(logic):
    """The shortcut's settings, for the button that fills the advanced form. Empty when it has none."""
    rules = rules_for(logic)
    if rules is None:
        return ""
    return json.dumps(form_values(rules), separators=(",", ":"))


def _lead_word(n):
    return _LEAD_WORD.get(abs(n), str(abs(n)))


def _lead_span(low, high):
    if low == high:
        if low == 0:
            return "tied"
        if low > 0:
            return f"leading by {_lead_word(low)}"
        return f"trailing by {_lead_word(low)}"
    if low == -high and high > 0:
        unit = "run" if high == 1 else "runs"
        return f"the game is within {_lead_word(high)} {unit}"
    if low == 0 and high > 0:
        if high == 1:
            return "tied or leading by one"
        return f"tied or leading by {_lead_word(high)} or fewer"
    if 0 < low < high:
        if high == low + 1:
            return f"leading by {_lead_word(low)} or {_lead_word(high)}"
        parts = [_lead_word(n) for n in range(low, high + 1)]
        if len(parts) > 2:
            return "leading by " + ", ".join(parts[:-1]) + f" or {parts[-1]}"
        return f"leading by {_lead_word(low)} through {_lead_word(high)}"

    def edge(n):
        if n == 0:
            return "a tie"
        if n > 0:
            return f"a {_lead_word(n)}-run lead"
        return f"trailing by {_lead_word(n)}"

    return f"{edge(low)} through {edge(high)}"


def _closer_sentence(rules):
    first = _INNING_NAME[rules["closer_first"]]
    mode = rules["closer"]
    cap = rules["closer_max_lead"]
    floor = rules["closer_min_lead"]
    if mode == "fireman":
        if rules["closer_first"] <= 8:
            return (
                f"The closer is a multi-inning ace. From the {first} on he pitches a tie or a one-run lead, "
                "and from the eighth on a save."
            )
        return (
            f"The closer is a multi-inning ace. From the {first} on he pitches a tie or a one-run lead, or a save."
        )
    if mode == "traffic":
        ninth = "a ninth-inning save" if cap is None else f"a ninth-inning save of {_lead_word(cap)} or fewer"
        return (
            f"The closer comes in from the {first} on for a one- or two-run save, {ninth}, "
            "or a one-run game or a tie with a runner on."
        )
    if mode == "save":
        if cap is None:
            situation = "a save situation"
        elif cap == 1:
            situation = "a one-run save"
        elif cap == 2:
            situation = "a save of one or two runs"
        else:
            situation = f"a save of {_lead_word(cap)} or fewer"
        return f"The closer pitches the {first} or later in {situation}."
    if cap is None:
        span = "the game is tied or his team leads" if floor <= 0 else f"leading by {_lead_word(floor)} or more"
    else:
        span = _lead_span(floor, cap)
    return f"The closer pitches the {first} or later when {span}."


def _hold_sentence(rules):
    hold = "Multi-inning" if rules["hold_role"] == MIRP else "Single-inning"
    rest = "Single-inning" if rules["hold_role"] == MIRP else "Multi-inning"
    code = _hold_code(rules["hold_from"], rules["hold_innings"])
    if code in (None, "never"):
        return f"{rest} relief works every spot the closer doesn't."
    where = {
        "from6": "from the sixth on",
        "678": "the sixth, seventh and eighth",
        "78": "the seventh and eighth",
        "8": "the eighth",
    }[code]
    span = _lead_span(rules["hold_min_lead"], rules["hold_max_lead"])
    return (
        f"{hold} relief pitches {where} when {span} and the closer stays in the pen. "
        f"{rest} relief works the rest."
    )


def describe_rules(rules):
    """The sentence for one set of advanced rules."""
    return f"{_closer_sentence(rules)} {_hold_sentence(rules)}"


def _calls_closer(window, inning, lead, runners_on, outs):
    if inning < window["closer_first"]:
        return False
    mode = window["closer"]
    save = is_save_situation(lead, runners_on, outs)
    if mode == "save":
        cap = window["closer_max_lead"]
        return save and (cap is None or lead <= cap)
    if mode == "lead":
        if lead < window["closer_min_lead"]:
            return False
        cap = window["closer_max_lead"]
        return cap is None or lead <= cap
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


def bullpen_role(inning, lead, runners_on, outs, logic=None, rules=None):
    """
    The role the situation calls for under a bullpen usage. lead is the
    fielding side's, negative when it trails. An unknown usage reads as
    traditional: the closer in a save from the 9th on, single-inning relief
    from the 6th on when the game is within three runs, and multi-inning
    relief otherwise. Advanced rules are the same settings a shortcut is
    filled in with, including which group pitches the innings the closer
    does not take. The other of single-inning and multi-inning relief
    pitches the rest.
    """
    window = _resolve_window(logic, rules)
    if _calls_closer(window, inning, lead, runners_on, outs):
        return CLOSER
    hold = window.get("hold_role", SIRP)
    if _calls_sirp(window, inning, lead):
        return hold
    return SIRP if hold == MIRP else MIRP


def sirp_pull_reason(outs, inning_unfinished):
    """
    Why a single-inning reliever comes out before the next batter, or None
    when he stays to face him. The outing runs to 1.2 innings whether or
    not the half inning he started is still going, and it ends there. Two
    innings is too many. inning_unfinished is the half inning's state; it
    does not shorten the outing.
    """
    if outs >= SIRP_MAX_OUTS:
        return "he has pitched 1.2 innings, and a single-inning outing ends there."
    return None


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


def reliever_stays(group, role, game_outs_left):
    """
    A multi-inning reliever who has entered finishes his own relief outing.
    He is not lifted when the situation flips to single-inning relief. He
    yields when the closer is called, and he leaves when the outing has no
    outs left. A single-inning reliever is not kept this way.
    """
    return group == MIRP and role != CLOSER and game_outs_left > 0


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


def designated_then_bench(designated, bench, problem):
    """
    The first legal player on the designated list, then the first legal
    player left on the bench order. A player named on both is considered
    once, where the designated list names him.
    """
    return _first_legal([*(designated or ()), *(bench or ())], problem)


def pinch_hitters(vs, pinch_vs_rhp, pinch_vs_lhp):
    """
    The pinch-hitter list for the opposing starter's throwing hand. A lefty
    uses the LHP list. A righty, or a hand that isn't known, uses the RHP list.
    """
    if vs == "L":
        return list(pinch_vs_lhp or [])
    return list(pinch_vs_rhp or [])
