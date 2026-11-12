# ABOUTME: The view of one live game drawn as a field: nine fielders, the mound, the batter's box and the last batted ball.
# ABOUTME: Coordinates are a 320x320 view from behind home plate, so first base is to the right and third base is to the left.

from ulmg import cards, usage

# The plate, and where a batted ball leaves the bat. First base grows x.
# The play sits in the top 320. The result word sits on the marquee under it, so a ball never lands on the word.
WIDTH = 320
PLAY_HEIGHT = 320
MARQUEE_HEIGHT = 36
HEIGHT = PLAY_HEIGHT + MARQUEE_HEIGHT
BANNER_Y = PLAY_HEIGHT + 24
HOME = (160, 240)
CONTACT = (160, 226)

# Feet of each defender. The pitcher stands on the mound; the catcher stands behind the plate.
ANCHORS = {
    "CF": (160, 54),
    "LF": (64, 82),
    "RF": (256, 82),
    "SS": (116, 132),
    "2B": (204, 132),
    "3B": (72, 178),
    "1B": (248, 178),
    "P": (160, 188),
    "C": (160, 258),
}
BASE_ANCHORS = {
    "first": (226, 176),
    "second": (160, 118),
    "third": (94, 176),
}
# Runners stand off the bag, in foul ground or above second, so their names clear the fielders.
RUNNER_ANCHORS = {
    "first": (286, 228),
    "second": (188, 104),
    "third": (34, 228),
}
# A right-handed batter stands on the third-base side of the plate, which is the left of this view.
BATTER_BOXES = {
    "left": (118, 232),
    "right": (202, 232),
}

DRAW_ORDER = ["LF", "CF", "RF", "SS", "2B", "3B", "1B", "C"]

# Where a batted ball comes down. The index is chosen from the result, so a refresh draws the same hop.
LANDINGS = {
    "ground_out": [(116, 146), (204, 146), (84, 170), (236, 170)],
    "grounded_into_double_play": [(124, 140), (196, 140)],
    "line_out": [(88, 100), (160, 74), (232, 100), (116, 112)],
    "fly_out": [(70, 56), (160, 40), (250, 56)],
    "sacrifice_fly": [(82, 50), (238, 50)],
    "single": [(98, 104), (222, 104), (160, 90), (186, 154)],
    "double": [(54, 68), (266, 68), (122, 46), (198, 46)],
    "triple": [(46, 42), (274, 42)],
    "home_run": [(36, 18), (160, 14), (284, 18)],
    "bunt_single": [(102, 204), (218, 204)],
    "bunt_out": [(146, 208), (174, 208)],
    "bunt_sacrifice": [(148, 204), (172, 204)],
    "bip_out": [(160, 112)],
}
# How high the ball climbs on the way. A line drive stays low; a fly ball climbs.
KINDS = {
    "ground_out": "ground",
    "grounded_into_double_play": "ground",
    "bunt_out": "bunt",
    "bunt_sacrifice": "bunt",
    "bunt_single": "bunt",
    "line_out": "line",
    "single": "line",
    "double": "line",
    "fly_out": "fly",
    "sacrifice_fly": "fly",
    "triple": "fly",
    "home_run": "fly",
    "bip_out": "line",
}
LIFTS = {"bunt": 8, "ground": 14, "line": 36, "fly": 72}
BANNERS = {
    "strikeout": "STRIKEOUT",
    "walk": "WALK",
    "hit_by_pitch": "HIT BY PITCH",
    "intentional_walk": "INTENTIONAL WALK",
    "single": "SINGLE",
    "double": "DOUBLE",
    "triple": "TRIPLE",
    "home_run": "HOME RUN",
    "ground_out": "GROUND OUT",
    "fly_out": "FLY OUT",
    "line_out": "LINE OUT",
    "grounded_into_double_play": "DOUBLE PLAY",
    "sacrifice_fly": "SAC FLY",
    "bunt_sacrifice": "SAC BUNT",
    "bunt_single": "BUNT HIT",
    "bunt_out": "BUNT OUT",
    "caught_stealing": "CAUGHT STEALING",
    "bip_out": "IN PLAY",
}

# Jerseys that still read against the grass. Two clubs in one game never share a color.
JERSEYS = ["#1d4e89", "#8d1e2f", "#b45309", "#3d348b", "#9a3412", "#155e75", "#6b21a8", "#9f1239"]


def fielding_label(rating):
    """The engine stores fielding runs divided by 10. The field shows the runs, signed."""
    runs = round(float(rating or 0) * 10, 1)
    if runs > 0:
        return f"+{runs:.1f}"
    return f"{runs:.1f}"


def batter_box(bats, throws):
    """
    Which side of the plate he stands on, in this view from behind home.
    Left is the third-base side, where a right-handed batter stands.
    A hand that cannot be known stands there too.
    """
    if cards.batting_side(bats, throws) == "L":
        return "right"
    return "left"


def short_name(name):
    """The last name on a jersey. Long ones keep nine letters and a dot."""
    parts = (name or "").split()
    label = parts[-1] if parts else ""
    if len(label) > 10:
        return label[:9] + "."
    return label


def jersey_name(player):
    """The name on the jersey: the stored last name, or the last word of the full name."""
    label = (getattr(player, "last_name", None) or "").strip()
    if not label:
        label = short_name(getattr(player, "name", "") or "")
    if len(label) > 10:
        return label[:9] + "."
    return label


def ball_track(result):
    """The arc of one batted ball, or None when the plate appearance was not in play."""
    if not result:
        return None
    outcome = result.get("outcome")
    spots = LANDINGS.get(outcome)
    if not spots:
        return None
    landing = _pick(spots, result)
    kind = KINDS[outcome]
    path = _arc(CONTACT, landing, LIFTS[kind])
    return {
        "outcome": outcome,
        "kind": kind,
        "label": BANNERS.get(outcome, outcome.replace("_", " ").upper()),
        "path": path,
        "x": landing[0],
        "y": landing[1],
        "count": _count(result),
    }


def result_banner(result):
    """The banner for the last plate appearance. In-play results also carry their track."""
    if not result or not result.get("outcome"):
        return None
    outcome = result["outcome"]
    banner = {
        "outcome": outcome,
        "label": BANNERS.get(outcome, outcome.replace("_", " ").upper()),
        "count": _count(result),
        "path": None,
    }
    track = ball_track(result)
    if track:
        banner.update(track)
    return banner


def field_view(play):
    """Everything the field draws for a game in progress, or None once it is final."""
    from ulmg import sim_game
    from ulmg.models import GameEvent

    state = play.state
    if not state or sim_game.is_final(state):
        return None
    fielding = sim_game.fielding_side(state)
    batting = sim_game.batting_side(state)
    fielders = _fielders(play, state[fielding]["lineup"])
    pitcher = _pitcher(play, state, fielding)
    batter = _batter(play, state, batting, pitcher)
    runners = _runners(play, state)
    bases = state.get("bases") or {}
    banner = result_banner(_recent_result(play, GameEvent.PLATE_APPEARANCE))
    fielding_color, batting_color = _jerseys(
        sim_game.team_for(play.game, fielding).abbreviation,
        sim_game.team_for(play.game, batting).abbreviation,
    )
    return {
        "fielders": fielders,
        "pitcher": pitcher,
        "batter": batter,
        "runners": runners,
        "banner": banner,
        "fielding_color": fielding_color,
        "batting_color": batting_color,
        "steal_live": bool((bases.get("first") and not bases.get("second")) or (bases.get("second") and not bases.get("third"))),
        "hit_and_run_live": bool(bases.get("first")),
        "width": WIDTH,
        "height": HEIGHT,
        "play_height": PLAY_HEIGHT,
        "marquee_height": MARQUEE_HEIGHT,
        "banner_y": BANNER_Y,
    }


def _fielders(play, lineup):
    by_position = {}
    for entry in lineup:
        position = entry.get("position")
        if position == "DH" or position not in ANCHORS:
            continue
        player = play.player(entry["id"])
        rating = (entry.get("defense") or {}).get("rating") or 0
        x, y = ANCHORS[position]
        by_position[position] = {
            "name": player.name,
            "short_name": jersey_name(player),
            "position": position,
            "fielding": fielding_label(rating),
            "x": x,
            "y": y,
            "player_id": player.id,
        }
    return [by_position[position] for position in DRAW_ORDER if position in by_position]


def _pitcher(play, state, fielding):
    pitcher_id = state[fielding].get("pitcher_slot")
    if not pitcher_id:
        return None
    player = play.player(pitcher_id)
    fatigue = (state[fielding].get("fatigue") or {}).get(str(pitcher_id), {})
    effort = 0 if fatigue.get("effort") is None else fatigue.get("effort")
    ceiling = 0 if fatigue.get("ceiling") is None else fatigue.get("ceiling")
    pitches = 0 if fatigue.get("pitches") is None else fatigue.get("pitches")
    width = 0 if not ceiling else max(0, min(52, round(52 * float(effort) / float(ceiling))))
    _hit, pitch = usage.card_stats(player, play.season)
    return {
        "name": player.name,
        "short_name": jersey_name(player),
        "player_id": player.id,
        "x": ANCHORS["P"][0],
        "y": ANCHORS["P"][1],
        "xfip": _xfip(pitch),
        "xfip_label": _xfip(pitch) or "—",
        "pitches": pitches,
        "effort": effort,
        "ceiling": ceiling,
        "fatigue_label": f"{round(float(effort))}/{round(float(ceiling))}",
        "fatigue_width": width,
        "fatigue_tone": _fatigue_tone(effort, ceiling),
        "throws": player.throws or "?",
    }


def _batter(play, state, batting, pitcher):
    club = state[batting]
    batter_id = club["lineup"][club["batter_index"]]["id"]
    player = play.player(batter_id)
    throws = pitcher["throws"] if pitcher else None
    if throws == "?":
        throws = None
    box = batter_box(player.bats, throws)
    hand = cards.batting_side(player.bats, throws) or player.bats or "?"
    x, y = BATTER_BOXES[box]
    return {
        "name": player.name,
        "short_name": jersey_name(player),
        "player_id": player.id,
        "hand": hand,
        "box": box,
        "x": x,
        "y": y,
    }


def _runners(play, state):
    runners = []
    for base, anchor in RUNNER_ANCHORS.items():
        runner_id = (state.get("bases") or {}).get(base)
        if not runner_id:
            continue
        player = play.player(runner_id)
        runners.append(
            {
                "base": base,
                "name": player.name,
                "short_name": jersey_name(player),
                "x": anchor[0],
                "y": anchor[1],
            }
        )
    return runners


def _recent_result(play, plate_appearance):
    """The plate appearance just played, including one the computer followed with its own move."""
    for event in reversed(play.events):
        if event.kind == plate_appearance:
            return (play.state or {}).get("last_result")
        if not event.computer:
            return None
    return None


def _jerseys(fielding_abbr, batting_abbr):
    fielding = sum(ord(c) for c in fielding_abbr) % len(JERSEYS)
    batting = sum(ord(c) for c in batting_abbr) % len(JERSEYS)
    if batting == fielding:
        batting = (batting + 3) % len(JERSEYS)
    return JERSEYS[fielding], JERSEYS[batting]


def _fatigue_tone(effort, ceiling):
    if not ceiling:
        return "ok"
    share = float(effort) / float(ceiling)
    if share >= 0.85:
        return "hot"
    if share >= 0.7:
        return "warm"
    return "ok"


def _xfip(pitch):
    if not pitch or pitch.get("xfip") in (None, ""):
        return None
    try:
        return f"{float(pitch['xfip']):.2f}"
    except (TypeError, ValueError):
        return None


def _count(result):
    count = result.get("count") or {}
    if "balls" not in count and "strikes" not in count:
        return ""
    return f"{count.get('balls', 0)}-{count.get('strikes', 0)}"


def _pick(options, result):
    count = result.get("count") or {}
    key = f"{result.get('batter_id')}|{result.get('outcome')}|{count.get('balls')}|{count.get('strikes')}"
    total = 0
    for char in key:
        total = (total * 33 + ord(char)) & 0xFFFFFFFF
    return options[total % len(options)]


def _arc(start, landing, lift):
    sx, sy = start
    lx, ly = landing
    cx = round((sx + lx) / 2)
    cy = max(8, round((sy + ly) / 2 - lift))
    return f"M {sx},{sy} Q {cx},{cy} {lx},{ly}"
