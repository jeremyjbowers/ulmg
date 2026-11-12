# ABOUTME: The view of one live game drawn as a field: nine fielders, the mound, the batter's box and the last batted ball.
# ABOUTME: The screen is 16:9, seen from the second deck behind home plate, so the plate is large and the outfield shrinks.

from ulmg import cards, usage

# A 16:9 screen about 900 pixels tall. The marquee is the bottom strip, under every landing.
WIDTH = 1600
HEIGHT = 900
PLAY_HEIGHT = 848
MARQUEE_HEIGHT = HEIGHT - PLAY_HEIGHT
BANNER_Y = 884

# Feet on the ground, in feet. +x is toward first base. +z is toward center field. Home is (0, 0).
# The camera sits behind the plate and a little above it, far enough that the tilt stays mild.
Z_NEAR = -40
Z_FAR = 360
SHRINK = 0.36
SY0 = 810
VDROP = 640
SPREAD = 4.6
# Foreground sprites are this many times the symbol's own size. Center field stays above half of that.
SPRITE = 2.15

GROUND = {
    "CF": (0, 310),
    "LF": (-145, 250),
    "RF": (150, 248),
    "SS": (-70, 142),
    "2B": (74, 140),
    "3B": (-80, 76),
    "1B": (80, 76),
    "P": (0, 60.5),
    "C": (0, -22),
}
BASE_GROUND = {
    "first": (63.6, 63.6),
    "second": (0, 127.3),
    "third": (-63.6, 63.6),
}
# Off the bag, in foul ground or past second, so a runner's name clears the fielder.
RUNNER_GROUND = {
    "first": (112, 36),
    "second": (86, 160),
    "third": (-112, 36),
}
# A right-handed batter stands on the third-base side of the plate, which is the left of this view.
BATTER_GROUND = {
    "left": (-52, 16),
    "right": (52, 16),
}
# The nameplate sits beside the body. Under the feet, the infield stacks and the marquee covers the catcher.
LABELS = {
    "CF": (0, 22, "middle"),
    "LF": (0, 22, "middle"),
    "RF": (0, 22, "middle"),
    "SS": (-96, -72, "end"),
    "2B": (96, -72, "start"),
    "3B": (-100, -48, "end"),
    "1B": (100, -48, "start"),
    "C": (140, -150, "start"),
}
BATTER_LABEL = {
    "left": (0, -160, "middle"),
    "right": (0, -160, "middle"),
}

# Far players are painted first. The catcher is nearest the camera, so he is last.
DRAW_ORDER = ["CF", "LF", "RF", "SS", "2B", "3B", "1B", "C"]

# Where a batted ball comes down, in the same ground feet. The index is chosen from the result.
LANDINGS = {
    "ground_out": [(48, 100), (-42, 105), (78, 82), (-74, 80)],
    "grounded_into_double_play": [(36, 120), (-32, 118)],
    "line_out": [(-90, 190), (0, 210), (96, 188), (-40, 160)],
    "fly_out": [(-120, 270), (0, 300), (130, 268)],
    "sacrifice_fly": [(-110, 280), (120, 276)],
    "single": [(-70, 175), (80, 170), (20, 200), (110, 145)],
    "double": [(-130, 240), (140, 236), (-60, 270), (70, 265)],
    "triple": [(-150, 300), (155, 295)],
    "home_run": [(-160, 345), (0, 350), (165, 345)],
    "bunt_single": [(-28, 36), (30, 34)],
    "bunt_out": [(-8, 28), (10, 26)],
    "bunt_sacrifice": [(-12, 30), (14, 28)],
    "bip_out": [(0, 150)],
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
LIFTS = {"bunt": 28, "ground": 48, "line": 110, "fly": 220}
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

# Home whites, road grays. The cap and pants keep a white jersey from disappearing into the dirt.
HOME_JERSEY = "#f4f1e8"
AWAY_JERSEY = "#3a4150"
STANCES = ("ready", "stand", "hands")


def project(gx, gz):
    """Screen x, screen y and a raw size for one spot on the ground. Larger y is closer to the camera."""
    t = (gz - Z_NEAR) / (Z_FAR - Z_NEAR)
    raw = 1 - SHRINK * t
    sy = SY0 - VDROP * t
    sx = WIDTH / 2 + gx * SPREAD * raw
    return sx, sy, raw


def place(gx, gz):
    """The same spot as integers, with the sprite scale the field actually draws."""
    x, y, raw = project(gx, gz)
    catcher = project(*GROUND["C"])[2]
    return round(x), round(y), round(raw / catcher * SPRITE, 3)


def _anchors(spots):
    return {name: place(*ground)[:2] for name, ground in spots.items()}


def _scales(spots):
    return {name: place(*ground)[2] for name, ground in spots.items()}


ANCHORS = _anchors(GROUND)
SCALES = _scales(GROUND)
BASE_ANCHORS = _anchors(BASE_GROUND)
RUNNER_ANCHORS = _anchors(RUNNER_GROUND)
RUNNER_SCALES = _scales(RUNNER_GROUND)
BATTER_BOXES = _anchors(BATTER_GROUND)
BATTER_SCALES = _scales(BATTER_GROUND)
HOME = place(0, 0)[:2]
CONTACT = place(0, 12)[:2]


def _ray(origin, through, x_limit):
    """Follow the foul line until it leaves the frame."""
    ox, oy = origin
    tx, ty = through
    dx = tx - ox
    k = (x_limit - ox) / dx
    return (round(ox + dx * k), round(oy + (ty - oy) * k))


FOUL_RIGHT = _ray(HOME, BASE_ANCHORS["first"], WIDTH - 8)
FOUL_LEFT = _ray(HOME, BASE_ANCHORS["third"], 8)


def uniform(side):
    """Home is in white. The road team is in gray, dark enough to read against the grass."""
    if side == "home":
        return {"name": "home", "jersey": HOME_JERSEY, "pants": "#f7f4ec", "cap": "#1b2430", "trim": "#c45c26"}
    return {"name": "away", "jersey": AWAY_JERSEY, "pants": "#2a303a", "cap": "#141820", "trim": "#d5d8e0"}


def stance(position, player_id):
    """
    Two or three poses, stable for one player, so the defense is not nine copies of one drawing.
    The middle infielders are down and ready. The others share the rest.
    """
    if position in ("SS", "2B", "3B"):
        return "ready"
    if position == "1B":
        return "stand"
    return STANCES[(int(player_id or 0) + ord((position or "P")[:1])) % 3]


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
    gx, gz = _pick(spots, result)
    landing = place(gx, gz)[:2]
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
    fielders = _fielders(play, state[fielding]["lineup"], fielding)
    pitcher = _pitcher(play, state, fielding)
    batter = _batter(play, state, batting, pitcher)
    runners = _runners(play, state, batting)
    bases = state.get("bases") or {}
    banner = result_banner(_recent_result(play, GameEvent.PLATE_APPEARANCE))
    fielding_uniform = uniform(fielding)
    batting_uniform = uniform(batting)
    return {
        "fielders": fielders,
        "pitcher": pitcher,
        "batter": batter,
        "runners": runners,
        "banner": banner,
        "fielding_color": fielding_uniform["jersey"],
        "batting_color": batting_uniform["jersey"],
        "fielding_uniform": fielding_uniform,
        "batting_uniform": batting_uniform,
        "home": {"x": HOME[0], "y": HOME[1]},
        "mound": {"x": ANCHORS["P"][0], "y": ANCHORS["P"][1]},
        "bases": {name: {"x": point[0], "y": point[1]} for name, point in BASE_ANCHORS.items()},
        "foul_left": {"x": FOUL_LEFT[0], "y": FOUL_LEFT[1]},
        "foul_right": {"x": FOUL_RIGHT[0], "y": FOUL_RIGHT[1]},
        "steal_live": bool((bases.get("first") and not bases.get("second")) or (bases.get("second") and not bases.get("third"))),
        "hit_and_run_live": bool(bases.get("first")),
        "width": WIDTH,
        "height": HEIGHT,
        "play_height": PLAY_HEIGHT,
        "marquee_height": MARQUEE_HEIGHT,
        "banner_y": BANNER_Y,
    }


def _actor(player, x, y, scale, kit):
    return {
        "name": player.name,
        "short_name": jersey_name(player),
        "player_id": player.id,
        "x": x,
        "y": y,
        "scale": scale,
        "uniform": kit["name"],
        "jersey": kit["jersey"],
        "pants": kit["pants"],
        "cap": kit["cap"],
        "trim": kit["trim"],
    }


def _fielders(play, lineup, side):
    by_position = {}
    kit = uniform(side)
    for entry in lineup:
        position = entry.get("position")
        if position == "DH" or position not in ANCHORS:
            continue
        player = play.player(entry["id"])
        rating = (entry.get("defense") or {}).get("rating") or 0
        x, y = ANCHORS[position]
        actor = _actor(player, x, y, SCALES[position], kit)
        lx, ly, anchor = LABELS[position]
        actor.update(
            {
                "position": position,
                "fielding": fielding_label(rating),
                "stance": stance(position, player.id),
                "lx": lx,
                "ly": ly,
                "anchor": anchor,
            }
        )
        by_position[position] = actor
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
    width = 0 if not ceiling else max(0, min(150, round(150 * float(effort) / float(ceiling))))
    _hit, pitch = usage.card_stats(player, play.season)
    actor = _actor(player, ANCHORS["P"][0], ANCHORS["P"][1], SCALES["P"], uniform(fielding))
    actor.update(
        {
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
    )
    return actor


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
    actor = _actor(player, x, y, BATTER_SCALES[box], uniform(batting))
    lx, ly, anchor = BATTER_LABEL[box]
    actor.update({"hand": hand, "box": box, "lx": lx, "ly": ly, "anchor": anchor})
    return actor


def _runners(play, state, batting):
    runners = []
    kit = uniform(batting)
    for base, anchor in RUNNER_ANCHORS.items():
        runner_id = (state.get("bases") or {}).get(base)
        if not runner_id:
            continue
        player = play.player(runner_id)
        actor = _actor(player, anchor[0], anchor[1], RUNNER_SCALES[base], kit)
        actor["base"] = base
        runners.append(actor)
    return runners


def _recent_result(play, plate_appearance):
    """The plate appearance just played, including one the computer followed with its own move."""
    for event in reversed(play.events):
        if event.kind == plate_appearance:
            return (play.state or {}).get("last_result")
        if not event.computer:
            return None
    return None


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
