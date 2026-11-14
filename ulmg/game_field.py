# ABOUTME: The top-down field on the game page: the park drawn from its real dimensions, fielders with ratings, runners with speed.
# ABOUTME: Also the last plate appearance as the page animates it: the ball's path, the banner, and each runner's move.

import math
import re

# The SVG's frame. Home plate is at HOME; the field opens upward.
HOME = (300.0, 492.0)
VIEWBOX = "20 62 560 482"
# The infield is drawn larger than scale so names fit; past INFIELD_FT the outfield is compressed to match.
INFIELD_FT = 130
INFIELD_SCALE = 1.7
OUTFIELD_SCALE = 0.72
# The five measured points of a fence, from the left-field line around to the right-field line.
ANGLES = {"lf_line": -45.0, "left_center": -22.5, "center": 0.0, "right_center": 22.5, "rf_line": 45.0}
# A wall at least this tall is drawn thick and named beside its distance.
TALL_WALL_FT = 17
# Distance labels sit this far inside the fence, and the two at the lines this many degrees inside fair territory.
LABEL_INSET_FT = 24
LINE_LABEL_INSET_DEG = 5
# Outfielders play at their usual depth, or this far in from a nearer fence.
OUTFIELD_GAP_FT = 75
BASE_FEET = {"first": (127, 45), "second": (180, 0), "third": (127, -45)}
# Where each fielder stands: feet from home and degrees off the line to center (first base side positive).
FIELDER_FEET = {
    "P": (60, 0),
    "C": (-12, 0),
    "1B": (122, 29),
    "2B": (158, 19),
    "SS": (158, -19),
    "3B": (122, -29),
    "LF": (285, -27),
    "CF": (320, 0),
    "RF": (285, 27),
}
FIELDER_ORDER = ("P", "C", "1B", "2B", "SS", "3B", "LF", "CF", "RF")
MOUND_FT = 60
MINUS = "−"
# The engine starts each line of its log with the half inning and the count: "Top 3, 2-1: ".
LOG_PREFIX = re.compile(r"^(Top|Bottom) \d+, (\d-\d): ")

# World landing spots of batted balls, in feet: +x is toward first base, +z toward center field.
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
    "reached_on_error": [(40, 95), (-36, 100), (70, 78)],
}
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
    "reached_on_error": "ground",
}
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
    "reached_on_error": "ERROR",
}


# Geometry


def warp(feet):
    """Feet from home to SVG units: the infield enlarged so names fit, the outfield compressed."""
    if feet <= INFIELD_FT:
        return feet * INFIELD_SCALE
    return INFIELD_FT * INFIELD_SCALE + (feet - INFIELD_FT) * OUTFIELD_SCALE


def point(feet, degrees):
    """SVG x, y of a spot `feet` from home, `degrees` off the line to center (first base side positive)."""
    angle = math.radians(degrees - 90)
    radius = warp(feet)
    return (round(HOME[0] + radius * math.cos(angle), 1), round(HOME[1] + radius * math.sin(angle), 1))


def world_point(x, z):
    """SVG x, y of a world spot in feet (+x toward first, +z toward center)."""
    return point(math.hypot(x, z), math.degrees(math.atan2(x, z)))


def _xy(points):
    return " ".join(f"{x},{y}" for x, y in points)


def base_spots():
    spots = {base: point(feet, degrees) for base, (feet, degrees) in BASE_FEET.items()}
    spots["home"] = HOME
    return spots


def park_drawing(rules):
    """Every shape of the park, from its rules (see ulmg.park): fair territory, walls, dirt, bases and distance labels."""
    distances = rules["distances_ft"]
    walls = rules["wall_ft"]
    keys = list(ANGLES)
    corners = [point(distances[key], ANGLES[key]) for key in keys]
    turf = rules.get("surface") == "turf"

    fence = f"M {HOME[0]} {HOME[1]} L {corners[0][0]} {corners[0][1]}"
    segments = []
    for i in range(1, len(keys)):
        control = point((distances[keys[i - 1]] + distances[keys[i]]) / 2 + 6, (ANGLES[keys[i - 1]] + ANGLES[keys[i]]) / 2)
        fence += f" Q {control[0]} {control[1]} {corners[i][0]} {corners[i][1]}"
        segments.append((i - 1, i, control))
    fence += " Z"

    tall = []
    for start, end, control in segments:
        if max(walls[keys[start]], walls[keys[end]]) >= TALL_WALL_FT:
            a, b = corners[start], corners[end]
            tall.append(f"M {a[0]} {a[1]} Q {control[0]} {control[1]} {b[0]} {b[1]}")

    labels = []
    for key in keys:
        angle = ANGLES[key]
        if abs(angle) == 45:
            angle -= math.copysign(LINE_LABEL_INSET_DEG, angle)
        x, y = point(distances[key] - LABEL_INSET_FT, angle)
        text = _feet(distances[key])
        if walls[key] >= TALL_WALL_FT:
            text += f" · {_feet(walls[key])}′ wall"
        labels.append({"x": x, "y": y, "text": text})

    arc = [point(158, -45), point(215, 0), point(158, 45)]
    dirt = f"M {HOME[0]} {HOME[1]} L {arc[0][0]} {arc[0][1]} Q {arc[1][0]} {round(arc[1][1] - 70, 1)} {arc[2][0]} {arc[2][1]} Z"
    bases = base_spots()
    mound = point(MOUND_FT, 0)
    hx, hy = HOME
    return {
        "viewbox": VIEWBOX,
        "turf": turf,
        "fence": fence,
        "tall_walls": tall,
        "dirt": dirt,
        "infield_grass": _xy([point(16, 0), point(112, 45), point(158, 0), point(112, -45)]),
        "baselines": _xy([bases["home"], bases["first"], bases["second"], bases["third"]]),
        "foul_lines": [corners[0], corners[-1]],
        "mound": mound,
        "labels": labels,
        "bases": [
            {"x": x, "y": y, "left": round(x - 8, 1), "top": round(y - 8, 1)}
            for x, y in (bases["first"], bases["second"], bases["third"])
        ],
        "home": HOME,
        "plate": _xy([(hx - 8, hy - 6), (hx + 8, hy - 6), (hx + 8, hy + 2), (hx, hy + 9), (hx - 8, hy + 2)]),
    }


def split_log_text(text):
    """An engine log line as (count, the play): "Top 3, 2-1: Reyes singled." is ("2-1", "Reyes singled.")."""
    match = LOG_PREFIX.match(text or "")
    if not match:
        return "", text or ""
    return match.group(2), text[match.end():]


def _feet(value):
    return f"{value:g}"


# Labels


def rating_runs(rating):
    """The engine stores a fielder's slotted card runs divided by 10. This is the runs again."""
    return round(float(rating or 0) * 10, 1) + 0.0


def rating_label(runs):
    """Signed runs with a real minus sign: +3.8, −2.0, 0.0."""
    if runs > 0:
        return f"+{runs:.1f}"
    if runs < 0:
        return f"{MINUS}{abs(runs):.1f}"
    return "0.0"


def last_name(player):
    label = (getattr(player, "last_name", None) or "").strip()
    if label:
        return label
    parts = (getattr(player, "name", "") or "").split()
    return parts[-1] if parts else ""


def speed_label(card):
    spd = getattr(card, "spd", None) if card is not None else None
    return "Speed —" if spd is None else f"Speed {spd:.1f}"


# The field now


def fence_at(distances, degrees):
    """The fence's distance at an angle, between the two measured points around it."""
    keys = list(ANGLES)
    for left, right in zip(keys, keys[1:]):
        a, b = ANGLES[left], ANGLES[right]
        if a <= degrees <= b:
            share = (degrees - a) / (b - a)
            return distances[left] + (distances[right] - distances[left]) * share
    return distances["center"]


def fielder_spot(position, distances=None):
    """Feet and degrees for a fielder; an outfielder comes in when the fence is near."""
    feet, degrees = FIELDER_FEET[position]
    if distances is not None and position in ("LF", "CF", "RF"):
        feet = min(feet, fence_at(distances, degrees) - OUTFIELD_GAP_FT)
    return feet, degrees


def fielders(play, state, side, distances=None):
    """The defense at its spots: position, name, rating tag, and whether the rating is below average."""
    club = state[side]
    by_position = {}
    for entry in club["lineup"]:
        position = entry.get("position")
        if position not in FIELDER_FEET or position == "P":
            continue
        player = play.player(entry["id"])
        runs = rating_runs((entry.get("defense") or {}).get("rating"))
        by_position[position] = _fielder(position, player, runs, distances)
    if club.get("pitcher_slot"):
        by_position["P"] = _fielder("P", play.player(club["pitcher_slot"]), None)
    return [by_position[position] for position in FIELDER_ORDER if position in by_position]


def _fielder(position, player, runs, distances=None):
    x, y = point(*fielder_spot(position, distances))
    tag = position if runs is None else f"{position} {rating_label(runs)}"
    width = len(tag) * 8 + 12
    if position == "C":
        name_at = {"x": round(x + width / 2 + 8, 1), "y": round(y + 17, 1), "anchor": "start"}
        tag_y = y + 12
    elif position == "P":
        name_at = {"x": x, "y": round(y + 27, 1), "anchor": "middle"}
        tag_y = y
    else:
        name_at = {"x": x, "y": round(y - 17, 1), "anchor": "middle"}
        tag_y = y
    return {
        "position": position,
        "player": player,
        "name": last_name(player),
        "runs": runs,
        "rating": None if runs is None else rating_label(runs),
        "tag": tag,
        "below": runs is not None and runs < 0,
        "x": x,
        "y": y,
        "box": {"x": round(x - width / 2, 1), "y": round(tag_y - 11, 1), "width": width, "text_y": round(tag_y + 4.5, 1)},
        "name_at": name_at,
    }


def runner_label(base):
    """Where a runner's name sits beside his base: right of first, left of third, above second and home."""
    if base == "first":
        return {"dx": 20, "dy": 0, "anchor": "start"}
    if base == "third":
        return {"dx": -20, "dy": 0, "anchor": "end"}
    return {"dx": 0, "dy": -36, "anchor": "middle"}


def runners(play, bases):
    """Who is on base now, with his name and his card's speed."""
    spots = base_spots()
    shown = []
    for base in ("first", "second", "third"):
        runner_id = (bases or {}).get(base)
        if not runner_id:
            continue
        player = play.player(runner_id)
        x, y = spots[base]
        shown.append(
            {
                "base": base,
                "player": player,
                "name": last_name(player),
                "speed": speed_label(play.card(player)),
                "x": x,
                "y": y,
                "label": runner_label(base),
            }
        )
    return shown


def describe(fielding_team, defense, on_base):
    """The field in words, for a screen reader: who is on base, then the fielders."""
    if on_base:
        bases = "; ".join(f"{r['player'].name} on {r['base']} ({r['speed'].lower()})" for r in on_base)
    else:
        bases = "Bases empty"
    fielders_text = ", ".join(
        f"{f['position']} {f['player'].name}" + (f" {f['rating']}" if f["rating"] else "") for f in defense
    )
    return f"{bases}. {fielding_team.abbreviation} in the field: {fielders_text}."


# The last plate appearance


def ball_track(result):
    """World landing of one batted ball, or None when the plate appearance was not in play."""
    if not result:
        return None
    outcome = result.get("outcome")
    spots = LANDINGS.get(outcome)
    if not spots:
        return None
    x, z = _pick(spots, result)
    return {"outcome": outcome, "kind": KINDS[outcome], "label": banner_label(outcome), "x": x, "z": z}


def banner_label(outcome):
    return BANNERS.get(outcome, (outcome or "").replace("_", " ").upper())


def runner_moves(before_bases, result):
    """
    Each runner's move in one plate appearance: from a base (or home, for the batter)
    to a base, to home when he scored, or out. Bases are engine id maps.
    """
    after = result["change"]["bases"]
    scored = [str(body["runner"]) for kind, body in _events(result) if kind == "Scored"]
    where_after = {str(pid): base for base, pid in after.items() if pid}
    moves = []
    for base in ("third", "second", "first"):
        pid = before_bases.get(base)
        if not pid:
            continue
        pid = str(pid)
        if pid in scored:
            moves.append((pid, base, "home"))
        elif pid in where_after:
            moves.append((pid, base, where_after[pid]))
        else:
            moves.append((pid, base, "out"))
    batter = str(result.get("batter_id"))
    if batter in scored:
        moves.append((batter, "home", "home"))
    elif batter in where_after and batter not in {m[0] for m in moves}:
        moves.append((batter, "home", where_after[batter]))
    return moves


def last_play(play, event):
    """The plate appearance a page animates: the ball's path, the banner and each runner's move, in SVG units."""
    payload = event.payload
    result = payload["result"]
    before = payload["before"]
    track = ball_track(result)
    mound = point(MOUND_FT, 0)
    ball = [mound, (HOME[0], HOME[1] - 8)]
    if track:
        ball.append(world_point(track["x"], track["z"]))
    spots = base_spots()
    moved = []
    for pid, start, end in runner_moves(before["bases"], result):
        player = play.player(pid)
        moved.append(
            {
                "name": last_name(player),
                "speed": speed_label(play.card(player)),
                "from": spots[start],
                "to": spots.get(end, spots[start]),
                "end": end,
                "label_from": runner_label(start),
                "label_to": runner_label(end if end in spots else start),
            }
        )
    runs = result["change"]["runs_scored"]
    return {
        "sequence": event.sequence,
        "outcome": result["outcome"],
        "banner": banner_label(result["outcome"]),
        "text": split_log_text(event.text)[1],
        "ball": [list(spot) for spot in ball],
        "runners": moved,
        "runs": runs,
        "side": payload["batting"],
        "inning": before["inning"],
    }


def recent_plate_appearance(events, plate_appearance):
    """The plate appearance just played: the last event, or the last one a person made, when the computer only followed it."""
    for event in reversed(events):
        if event.kind == plate_appearance:
            return event
        if not event.computer:
            return None
    return None


def _events(result):
    for event in result.get("baserunning") or []:
        (kind, body), = event.items()
        yield kind, body


def _pick(options, result):
    count = result.get("count") or {}
    key = f"{result.get('batter_id')}|{result.get('outcome')}|{count.get('balls')}|{count.get('strikes')}"
    total = 0
    for char in key:
        total = (total * 33 + ord(char)) & 0xFFFFFFFF
    return options[total % len(options)]
