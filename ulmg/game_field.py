# ABOUTME: The top-down field on the game page: the park drawn from its real dimensions, fielders with ratings, runners with speed.
# ABOUTME: Also the last plate appearance as the page animates it: the ball's path, the banner, and each runner's move.

import hashlib
import json
import math
import random
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
# Mowing stripes, foul ground and the mound. Turf is a cooler cut of the same shapes.
GRASS_COLORS = {
    "mow": "#3a8648",
    "mow_alt": "#4c9a5c",
    "infield": "#348044",
    "infield_alt": "#469658",
    "foul": "#6e8a46",
    "foul_alt": "#7d9854",
    "speck": "#5c7438",
    "mound_hi": "#e6b86e",
    "mound_mid": "#c58a4d",
    "mound_lo": "#8a5524",
    "shadow": "#0c2816",
}
TURF_COLORS = {
    "mow": "#2a8564",
    "mow_alt": "#38a67c",
    "infield": "#267a5e",
    "infield_alt": "#339978",
    "foul": "#3c5160",
    "foul_alt": "#486070",
    "speck": "#2c404c",
    "mound_hi": "#d7b07a",
    "mound_mid": "#b98c5a",
    "mound_lo": "#7a5a38",
    "shadow": "#101820",
}
# Foul ground is a band this many SVG units wide per foot of the park's foul_ft, along each line and around behind home.
FOUL_SCALE = 1.2
# The foul ground's mottle: one square tile of this size, scattered with this many marks.
FOUL_TILE = 120
FOUL_MARKS = 44
# Seats and bleachers. Each park draws one seat color and one bleacher color, its own row depth and aisle spacing.
SEAT_COLORS = [
    ("#2b4c7e", "#1d3557"),
    ("#8c2f2f", "#5e1f1f"),
    ("#1f5d4a", "#143e31"),
    ("#4a4a55", "#2e2e36"),
    ("#2f6f8f", "#1f4a60"),
    ("#6b3a6e", "#472649"),
]
BLEACHER_COLORS = ["#a9b1b5", "#b8a988", "#8e979c", "#c2b8a0"]
STAND_GAP = "#1b1f24"
AISLE = "#cfc8b8"
# The stands reach this far out from the field, so they fill the frame's corners.
STANDS_DEPTH = 300
# Behind the foul lines: a lower deck, a concourse walkway, then an upper deck to the back of the frame. SVG units from the edge of the field.
LOWER_DECK = 72
CONCOURSE_WIDTH = 9
CONCOURSE = "#9b968a"
# The facade line along the front of each deck.
FACADE = "#141619"
# Behind the outfield wall: bleachers this deep, a back wall, and the ground beyond it.
BLEACHER_DEPTH = 64
BACK_WALL = "#2b2f33"
GROUND = "#3a3f3a"
# Every other section between aisles is shaded this much darker.
SECTION_SHADE = 0.1
# Tunnels into the lower deck: every this many aisles, this far into the deck.
TUNNEL_EVERY = 2
TUNNEL_DEPTH = 0.5
# Dugouts sit in foul ground this many feet up each line from home, this far out across the foul band (a share of its width).
DUGOUT_FEET = 58
DUGOUT_OUT = 0.6
DUGOUT_LENGTH = 62
DUGOUT_DEPTH = 15
# Distance labels sit this far inside the fence, and the two at the lines this many degrees inside fair territory.
LABEL_INSET_FT = 24
LINE_LABEL_INSET_DEG = 5
# Outfielders play at their usual depth, or this far in from a nearer fence.
OUTFIELD_GAP_FT = 75
# Second base, in feet from home. The other bases square the diamond around it.
SECOND_BASE_FT = 180
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
# The dirt basepath between each baseline and the infield grass, in SVG units.
BASEPATH_WIDTH = 12
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
    """
    Home and the three bases as a true square in SVG units.

    The field's scale is not linear, so placing each base by its feet would
    pull second toward home. Second is placed by its feet and first and third
    are the square's other corners.
    """
    hx, hy = HOME
    half = warp(SECOND_BASE_FT) / 2
    return {
        "home": HOME,
        "first": (round(hx + half, 1), round(hy - half, 1)),
        "second": point(SECOND_BASE_FT, 0),
        "third": (round(hx - half, 1), round(hy - half, 1)),
    }


def mound_spot():
    """The middle of the diamond: as far from home as from second, and from first as from third."""
    hx, hy = HOME
    return (hx, round(hy - warp(SECOND_BASE_FT) / 2, 1))


def inset(corners, distance):
    """
    A convex polygon pulled in by `distance` on every side.

    Each side moves straight toward the middle and stays parallel to where it
    was, so the band between the two polygons is the same width all the way along.
    """
    middle_x = sum(x for x, _ in corners) / len(corners)
    middle_y = sum(y for _, y in corners) / len(corners)
    sides = []
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
        length = math.hypot(bx - ax, by - ay)
        nx, ny = (ay - by) / length, (bx - ax) / length
        if nx * (middle_x - ax) + ny * (middle_y - ay) < 0:
            nx, ny = -nx, -ny
        sides.append(((ax + nx * distance, ay + ny * distance), (bx - ax, by - ay)))
    pulled = []
    for i in range(len(sides)):
        (px, py), (dx, dy) = sides[i - 1]
        (qx, qy), (ex, ey) = sides[i]
        share = ((qx - px) * ey - (qy - py) * ex) / (dx * ey - dy * ex)
        pulled.append((round(px + dx * share, 1), round(py + dy * share, 1)))
    return pulled


def park_random(rules):
    """A random source seeded by the park's rules, so a park looks the same every game and another park looks different."""
    keys = ("distances_ft", "wall_ft", "foul_ft", "surface", "roof")
    text = json.dumps({key: rules.get(key) for key in keys}, sort_keys=True)
    return random.Random(int(hashlib.sha256(text.encode()).hexdigest()[:16], 16))


def foul_band(rules):
    """
    Foul ground: a band along each foul line, the park's foul_ft wide, rounded behind home.

    Returns the band's outline (with fair territory inside it) and the band's outer
    corners at the two foul poles.
    """
    distances = rules["distances_ft"]
    width = rules["foul_ft"] * FOUL_SCALE
    left_pole = point(distances["lf_line"], -45)
    right_pole = point(distances["rf_line"], 45)
    hx, hy = HOME
    out = width / math.sqrt(2)
    # Outward from each line: down and to the left of the left-field line, down and to the right of the right-field line.
    left = (round(left_pole[0] - out, 1), round(left_pole[1] + out, 1))
    right = (round(right_pole[0] + out, 1), round(right_pole[1] + out, 1))
    beside_left = (round(hx - out, 1), round(hy + out, 1))
    beside_right = (round(hx + out, 1), round(hy + out, 1))
    behind = (hx, round(hy + width * math.sqrt(2), 1))
    path = (
        f"M {left_pole[0]} {left_pole[1]} L {left[0]} {left[1]} L {beside_left[0]} {beside_left[1]}"
        f" Q {behind[0]} {behind[1]} {beside_right[0]} {beside_right[1]}"
        f" L {right[0]} {right[1]} L {right_pole[0]} {right_pole[1]}"
    )
    return {"path": path, "left": left, "right": right, "beside_left": beside_left, "beside_right": beside_right, "behind": behind}


def foul_marks(rng):
    """
    The scuffs and patches of the foul ground's mottle, inside one tile.

    _tiled copies the marks near an edge across it for drawing.
    """
    marks = []
    for _ in range(FOUL_MARKS):
        mark = {
            "x": round(rng.uniform(0, FOUL_TILE), 1),
            "y": round(rng.uniform(0, FOUL_TILE), 1),
            "rx": round(rng.uniform(2, 11), 1),
            "ry": round(rng.uniform(1, 5), 1),
            "turn": rng.randrange(0, 180),
            "shade": rng.choice(("foul_alt", "foul_alt", "speck")),
            "opacity": round(rng.uniform(0.2, 0.5), 2),
        }
        marks.append(mark)
    return marks


def _tiled(marks):
    """Each mark, plus its copies across the tile's edges, so a repeating tile has no seam."""
    reach = 12
    tiled = []
    for mark in marks:
        for dx in (-FOUL_TILE, 0, FOUL_TILE):
            for dy in (-FOUL_TILE, 0, FOUL_TILE):
                x, y = mark["x"] + dx, mark["y"] + dy
                if -reach <= x <= FOUL_TILE + reach and -reach <= y <= FOUL_TILE + reach:
                    tiled.append({**mark, "x": round(x, 1), "y": round(y, 1)})
    return tiled


def _rows(start, end, depth, seat, gap):
    """Rows of seats from `end` back in to `start` (SVG units from the field's edge), as bands to stroke from widest to narrowest."""
    rows = []
    count = math.floor((end - start) / depth)
    for row in range(count, 0, -1):
        reach = start + row * depth
        rows.append({"width": round(2 * reach, 1), "color": gap})
        rows.append({"width": round(2 * reach - 1.6, 1), "color": seat})
    return rows


def _shade(color, share):
    """A color darkened toward black by `share` (0 to 1)."""
    red, green, blue = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(c * (1 - share)):02x}" for c in (red, green, blue))


def _outline_points(band):
    """The outer edge of the foul ground as points: from the left-field pole down the line, around behind home, and up to the right-field pole."""
    (lx, ly), (rx, ry) = band["left"], band["right"]
    bl, br, behind = band["beside_left"], band["beside_right"], band["behind"]
    points = [(lx, ly), bl]
    for step in range(1, 12):
        t = step / 12
        points.append((
            (1 - t) ** 2 * bl[0] + 2 * (1 - t) * t * behind[0] + t ** 2 * br[0],
            (1 - t) ** 2 * bl[1] + 2 * (1 - t) * t * behind[1] + t ** 2 * br[1],
        ))
    points += [br, (rx, ry)]
    return points


def _ray_hit(points, angle):
    """Where a ray from home at `angle` (degrees off the line to center) crosses the outline, or None."""
    hx, hy = HOME
    dx, dy = math.sin(math.radians(angle)), -math.cos(math.radians(angle))
    best = None
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        ex, ey = bx - ax, by - ay
        cross = dx * ey - dy * ex
        if abs(cross) < 1e-9:
            continue
        reach = ((ax - hx) * ey - (ay - hy) * ex) / cross
        share = ((ax - hx) * dy - (ay - hy) * dx) / cross
        if reach > 0 and 0 <= share <= 1 and (best is None or reach < best):
            best = reach
    return None if best is None else (hx + dx * best, hy + dy * best, dx, dy)


def stands(rng, fence_back, band):
    """
    The stadium around the field, all following the edge of the playing field:
    behind the foul lines a lower deck, a concourse and an upper deck, cut into
    sections by aisles with tunnels into the lower deck; behind the outfield wall
    bleachers to a back wall, with the ground beyond.
    """
    seat, seat_gap = rng.choice(SEAT_COLORS)
    bleacher = rng.choice(BLEACHER_COLORS)
    upper = _shade(seat, 0.28)
    depth = round(rng.uniform(5, 7.5), 1)
    concourse_back = LOWER_DECK + CONCOURSE_WIDTH
    grandstand = _rows(concourse_back + 2, STANDS_DEPTH, depth, upper, STAND_GAP)
    grandstand.append({"width": round(2 * concourse_back + 2, 1), "color": FACADE})
    grandstand.append({"width": round(2 * concourse_back, 1), "color": CONCOURSE})
    grandstand.append({"width": round(2 * LOWER_DECK + 2, 1), "color": FACADE})
    grandstand += _rows(0, LOWER_DECK, depth, seat, seat_gap)
    bleachers = [{"width": round(2 * BLEACHER_DEPTH + 6, 1), "color": BACK_WALL}]
    bleachers += _rows(0, BLEACHER_DEPTH, depth, bleacher, STAND_GAP)

    spacing = rng.choice((8, 9, 10, 11, 12))
    offset = rng.uniform(0, spacing)
    aisles, sections, tunnels = [], [], []
    outline = _outline_points(band)
    angle = -180 + offset
    index = 0
    while angle < 180:
        far = point(1000, angle)
        aisles.append({"x1": HOME[0], "y1": HOME[1], "x2": far[0], "y2": far[1]})
        if index % 2:
            following = point(1000, angle + spacing)
            sections.append(_xy([HOME, far, following]))
        hit = _ray_hit(outline, angle) if abs(angle) > 45 and index % TUNNEL_EVERY == 0 else None
        if hit is not None:
            x, y, dx, dy = hit
            reach = LOWER_DECK * TUNNEL_DEPTH
            tunnels.append({"x": round(x + dx * reach, 1), "y": round(y + dy * reach, 1), "turn": round(angle, 1)})
        angle += spacing
        index += 1
    left_far, right_far = point(1000, -45), point(1000, 45)
    return {
        "edge": band["path"] + fence_back + " Z",
        "seat": seat,
        "seat_gap": seat_gap,
        "upper": upper,
        "bleacher": bleacher,
        "gap": STAND_GAP,
        "ground": GROUND,
        "aisle": AISLE,
        "grandstand": grandstand,
        "bleachers": bleachers,
        "lower_deck": round(2 * LOWER_DECK, 1),
        "concourse_back": round(2 * concourse_back + 2, 1),
        "bleacher_depth": round(2 * BLEACHER_DEPTH, 1),
        "section_shade": SECTION_SHADE,
        "aisles": aisles,
        "sections": sections,
        "tunnels": tunnels,
        "bleacher_clip": _xy([HOME, left_far, (left_far[0], -2000), (right_far[0], -2000), right_far]),
        "grandstand_clip": _xy([HOME, left_far, (left_far[0], 3000), (right_far[0], 3000), right_far]),
    }


def dugouts(band_width):
    """Each team's dugout in foul ground, up the third- and first-base lines from home, turned along its line."""
    reach = band_width * DUGOUT_OUT / math.sqrt(2)
    third = point(DUGOUT_FEET, -45)
    first = point(DUGOUT_FEET, 45)
    shown = []
    for (x, y), side, turn in ((third, -1, 45), (first, 1, -45)):
        shown.append({
            "x": round(x + side * reach, 1),
            "y": round(y + reach, 1),
            "turn": turn,
            "length": DUGOUT_LENGTH,
            "depth": DUGOUT_DEPTH,
            "left": -DUGOUT_LENGTH / 2,
            "top": -DUGOUT_DEPTH / 2,
            # The open front of the dugout, on the side facing the field.
            "bench": DUGOUT_DEPTH / 2 - 5,
        })
    return shown


def curved_wall(rules):
    """
    The wall of a park with no traced fence: a curve bowed slightly outward
    through its five measured points. Returns the wall from home out along the
    left-field line and around (closed), the same wall from the right-field pole
    back to the left-field pole, and each tall stretch between measured points.
    """
    distances = rules["distances_ft"]
    walls = rules["wall_ft"]
    keys = list(ANGLES)
    corners = [point(distances[key], ANGLES[key]) for key in keys]
    fence = f"M {HOME[0]} {HOME[1]} L {corners[0][0]} {corners[0][1]}"
    segments = []
    for i in range(1, len(keys)):
        control = point((distances[keys[i - 1]] + distances[keys[i]]) / 2 + 6, (ANGLES[keys[i - 1]] + ANGLES[keys[i]]) / 2)
        fence += f" Q {control[0]} {control[1]} {corners[i][0]} {corners[i][1]}"
        segments.append((i - 1, i, control))
    fence += " Z"
    fence_back = ""
    for start, end, control in reversed(segments):
        fence_back += f" Q {control[0]} {control[1]} {corners[start][0]} {corners[start][1]}"
    tall = []
    for start, end, control in segments:
        if max(walls[keys[start]], walls[keys[end]]) >= TALL_WALL_FT:
            a, b = corners[start], corners[end]
            tall.append(f"M {a[0]} {a[1]} Q {control[0]} {control[1]} {b[0]} {b[1]}")
    return fence, fence_back, tall, (corners[0], corners[-1])


def traced_wall(rules):
    """
    The wall of a park with a traced fence: straight runs between the traced
    points, so a corner in the real wall is a corner on the page. Returns the
    same four parts as curved_wall.
    """
    walls = rules["wall_ft"]
    fence = fence_points(rules)
    corners = [point(feet, degrees) for degrees, feet in fence]
    path = f"M {HOME[0]} {HOME[1]}" + "".join(f" L {x} {y}" for x, y in corners) + " Z"
    fence_back = "".join(f" L {x} {y}" for x, y in reversed(corners))
    keys = list(ANGLES)
    tall = []
    for left, right in zip(keys, keys[1:]):
        if max(walls[left], walls[right]) < TALL_WALL_FT:
            continue
        a, b = ANGLES[left], ANGLES[right]
        stretch = [point(fence_at(fence, a), a)]
        stretch += [point(feet, degrees) for degrees, feet in fence if a < degrees < b]
        stretch.append(point(fence_at(fence, b), b))
        tall.append(f"M {stretch[0][0]} {stretch[0][1]}" + "".join(f" L {x} {y}" for x, y in stretch[1:]))
    return path, fence_back, tall, (corners[0], corners[-1])


def park_drawing(rules):
    """Every shape of the park, from its rules (see ulmg.park): fair territory, walls, dirt, bases, distance labels, foul ground, stands and the colors."""
    distances = rules["distances_ft"]
    walls = rules["wall_ft"]
    keys = list(ANGLES)
    turf = rules.get("surface") == "turf"
    fence, fence_back, tall, poles = traced_wall(rules) if rules.get("fence_ft") else curved_wall(rules)
    outline = fence_points(rules)
    rng = park_random(rules)
    band = foul_band(rules)
    marks = foul_marks(rng)

    labels = []
    for key in keys:
        angle = ANGLES[key]
        if abs(angle) == 45:
            angle -= math.copysign(LINE_LABEL_INSET_DEG, angle)
        # Inside the wall where it was measured, and inside it where the label sits, should the wall come in there.
        x, y = point(min(distances[key], fence_at(outline, angle)) - LABEL_INSET_FT, angle)
        text = _feet(distances[key])
        if walls[key] >= TALL_WALL_FT:
            text += f" · {_feet(walls[key])}′ wall"
        labels.append({"x": x, "y": y, "text": text})

    arc = [point(158, -45), point(215, 0), point(158, 45)]
    dirt = f"M {HOME[0]} {HOME[1]} L {arc[0][0]} {arc[0][1]} Q {arc[1][0]} {round(arc[1][1] - 70, 1)} {arc[2][0]} {arc[2][1]} Z"
    bases = base_spots()
    mound = mound_spot()
    hx, hy = HOME
    return {
        "viewbox": VIEWBOX,
        "turf": turf,
        "fence": fence,
        "foul_ground": band["path"] + " Z",
        "foul_tile": FOUL_TILE,
        "foul_marks": marks,
        "foul_tiled": _tiled(marks),
        "stands": stands(rng, fence_back, band),
        "dugouts": dugouts(rules["foul_ft"] * FOUL_SCALE),
        "tall_walls": tall,
        "dirt": dirt,
        "infield_grass": _xy(inset([bases["home"], bases["first"], bases["second"], bases["third"]], BASEPATH_WIDTH)),
        "baselines": _xy([bases["home"], bases["first"], bases["second"], bases["third"]]),
        "foul_lines": list(poles),
        "mound": mound,
        "labels": labels,
        "bases": [
            {"x": x, "y": y, "left": round(x - 8, 1), "top": round(y - 8, 1)}
            for x, y in (bases["first"], bases["second"], bases["third"])
        ],
        "home": HOME,
        "plate": _xy([(hx - 8, hy - 6), (hx + 8, hy - 6), (hx + 8, hy + 2), (hx, hy + 9), (hx - 8, hy + 2)]),
        "colors": TURF_COLORS if turf else GRASS_COLORS,
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


def fence_points(rules):
    """The wall as (degrees, feet) from the left-field line to the right-field line: the traced fence, or the five measured points."""
    if rules.get("fence_ft"):
        return [(float(degrees), feet) for degrees, feet in rules["fence_ft"]]
    distances = rules["distances_ft"]
    return [(ANGLES[key], distances[key]) for key in ANGLES]


def fence_at(fence, degrees):
    """The fence's distance at an angle, between the two points of the fence around it."""
    for (a, left), (b, right) in zip(fence, fence[1:]):
        if a <= degrees <= b:
            share = (degrees - a) / (b - a)
            return left + (right - left) * share
    return min(fence, key=lambda spot: abs(spot[0]))[1]


def fielder_spot(position, fence=None):
    """Feet and degrees for a fielder; an outfielder comes in when the fence is near."""
    feet, degrees = FIELDER_FEET[position]
    if fence is not None and position in ("LF", "CF", "RF"):
        feet = min(feet, fence_at(fence, degrees) - OUTFIELD_GAP_FT)
    return feet, degrees


def fielders(play, state, side, fence=None):
    """The defense at its spots: position, name, rating tag, and whether the rating is below average."""
    club = state[side]
    by_position = {}
    for entry in club["lineup"]:
        position = entry.get("position")
        if position not in FIELDER_FEET or position == "P":
            continue
        player = play.player(entry["id"])
        runs = rating_runs((entry.get("defense") or {}).get("rating"))
        by_position[position] = _fielder(position, player, runs, fence)
    if club.get("pitcher_slot"):
        by_position["P"] = _fielder("P", play.player(club["pitcher_slot"]), None)
    return [by_position[position] for position in FIELDER_ORDER if position in by_position]


def _fielder(position, player, runs, fence=None):
    x, y = mound_spot() if position == "P" else point(*fielder_spot(position, fence))
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


def batted_ball_origin(bats=None):
    """
    Where a batted ball leaves, in SVG units. Home plate.

    A left-handed batter and a right-handed batter stand on opposite sides of
    the plate. `bats` is that hand, and it does not move the point.
    """
    return HOME


def ball_path(track, bats=None):
    """The ball on the field: the mound, home plate, and where a ball in play landed."""
    path = [mound_spot(), batted_ball_origin(bats)]
    if track:
        path.append(world_point(track["x"], track["z"]))
    return path


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


def bases_touched(start, end):
    """
    The bases a runner touches, in order.

    Two or more bases go around the diamond. A runner who stays, or who is out,
    has only the base he left: the out fades there.
    """
    if end == "out" or (start == end and end != "home"):
        return (start,)
    if start == "home" and end == "home":
        return ("home", "first", "second", "third", "home")
    cycle = ("home", "first", "second", "third", "home")
    begin = cycle.index(start)
    for index in range(begin + 1, len(cycle)):
        if cycle[index] == end:
            return cycle[begin : index + 1]
    return (start, end)


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
    batter_id = result.get("batter_id")
    bats = None
    if batter_id:
        bats = getattr(play.player(batter_id), "bats", None)
    ball = ball_path(track, bats)
    spots = base_spots()
    moved = []
    for pid, start, end in runner_moves(before["bases"], result):
        player = play.player(pid)
        touched = bases_touched(start, end)
        finish = end if end in spots else start
        moved.append(
            {
                "name": last_name(player),
                "speed": speed_label(play.card(player)),
                "from": spots[start],
                "to": spots[finish],
                "path": [list(spots[base]) for base in touched],
                "labels": [runner_label(base) for base in touched],
                "end": end,
                "label_from": runner_label(start),
                "label_to": runner_label(finish),
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
