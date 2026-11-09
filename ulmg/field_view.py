# ABOUTME: The pixel-field picture for a half inning played by hand: defenders, runners, pitcher and the last ball path.
# ABOUTME: The engine records the outcome, not a landing spot, so the path is a stable spray drawn from that outcome and the play's seed.

# Broadcast view, home plate at the bottom. Every spot sits on a 4px grid.
SPOTS = {
    "LF": (48, 72),
    "CF": (160, 44),
    "RF": (272, 72),
    "SS": (112, 120),
    "2B": (208, 120),
    "3B": (56, 176),
    "1B": (236, 176),
    "P": (160, 168),
    "C": (160, 252),
}
BASE_SPOTS = {"first": (216, 188), "second": (160, 124), "third": (104, 188)}
HOME = (160, 228)
BATTER_BOX = {"L": (184, 228), "R": (136, 228), "S": (136, 228)}

# Where a batted ball can finish, left to right, so the seed picks a spray and the caption can name it.
INFIELD = ((88, 176), (128, 132), (160, 156), (192, 132), (232, 176))
SHALLOW = ((72, 108), (116, 92), (160, 84), (204, 92), (248, 108))
DEEP = ((56, 68), (108, 56), (160, 48), (212, 56), (264, 68))
OVER = ((40, 28), (100, 20), (160, 16), (220, 20), (280, 28))

GROUND = {"ground_out", "grounded_into_double_play", "bunt_out", "bunt_sacrifice", "bunt_single", "fielders_choice"}
FLY = {"fly_out", "sacrifice_fly", "pop_out"}
NO_CONTACT = {"strikeout", "walk", "intentional_walk", "hit_by_pitch", "caught_stealing"}

CAPTIONS = {
    "single": "Single",
    "double": "Double",
    "triple": "Triple",
    "home_run": "Home run",
    "bunt_single": "Bunt single",
    "ground_out": "Ground out",
    "fly_out": "Fly out",
    "line_out": "Line out",
    "pop_out": "Pop out",
    "bip_out": "Out in play",
    "grounded_into_double_play": "Double play",
    "sacrifice_fly": "Sacrifice fly",
    "bunt_sacrifice": "Sacrifice bunt",
    "bunt_out": "Bunt out",
    "fielders_choice": "Fielder's choice",
    "strikeout": "Strikeout",
    "walk": "Walk",
    "intentional_walk": "Intentional walk",
    "hit_by_pitch": "Hit by pitch",
    "caught_stealing": "Caught stealing",
}


def short_name(name):
    """The last name, short enough to sit beside a sprite. A trailing position or number is skipped."""
    parts = [part for part in (name or "").split() if part]
    if not parts:
        return ""
    last = parts[-1]
    if len(parts) >= 2 and (last in SPOTS or last.isdigit()):
        last = parts[-2]
    return last[:8]


def rating_label(runs):
    """Defensive runs the way the plan page prints them, with a sign when he is above average."""
    if runs is None:
        return ""
    text = f"{runs:.1f}".rstrip("0").rstrip(".")
    if runs > 0:
        return f"+{text}"
    return text


def _pick(spots, seed):
    return spots[seed % len(spots)]


def _path(start, end, lift):
    mid = _snap(((start[0] + end[0]) // 2, (start[1] + end[1]) // 2 - lift))
    return [start, mid, end]


def _snap(point):
    return (point[0] // 4 * 4, point[1] // 4 * 4)


def ball_path(outcome, seed):
    """
    The polyline of the last pitch or batted ball, and its caption.

    A batted ball sprays through a zone that matches the outcome. A strikeout
    or a walk is the pitch, from the mound to the plate. None when there is
    no plate appearance to draw.
    """
    if not outcome:
        return None
    seed = int(seed or 0)
    if outcome in NO_CONTACT:
        return {"points": [SPOTS["P"], HOME], "kind": "pitch", "caption": CAPTIONS.get(outcome, "Pitch")}
    if outcome == "home_run":
        end, kind, lift = _pick(OVER, seed), "fly", 24
    elif outcome == "triple":
        end, kind, lift = _pick((DEEP[0], DEEP[-1]), seed), "line", 12
    elif outcome == "double":
        end, kind, lift = _pick((DEEP[1], DEEP[3]), seed), "line", 12
    elif outcome == "single":
        end, kind, lift = _pick(SHALLOW, seed), "line", 16
    elif outcome in FLY:
        end, kind, lift = _pick(DEEP, seed), "fly", 36
    elif outcome in GROUND:
        end, kind, lift = _pick(INFIELD, seed), "ground", 8
    else:
        end, kind, lift = _pick(DEEP, seed), "line", 16
    points = [_snap(point) for point in _path(HOME, end, lift)]
    side = "left" if end[0] < 130 else "right" if end[0] > 190 else "center"
    label = CAPTIONS.get(outcome, "In play")
    caption = label if outcome in NO_CONTACT else f"{label} to {side}"
    return {"points": points, "kind": kind, "caption": caption}


def _marked(people, spots):
    marked = []
    for person in people:
        spot = spots.get(person["position"])
        if spot is None:
            continue
        marked.append(
            {
                "position": person["position"],
                "name": short_name(person["name"]),
                "rating": rating_label(person.get("rating")),
                "x": spot[0],
                "y": spot[1],
            }
        )
    return marked


def scene(fielders, runners, batter, pitcher, last_play, scoreboard):
    """
    The picture. fielders are {position, name, rating}. runners maps a base
    to a name. last_play is {outcome, seed} for a plate appearance just
    played by hand, or None. scoreboard is {away, home, away_score, home_score, half, inning, outs}.
    """
    ball = ball_path(last_play["outcome"], last_play["seed"]) if last_play else None
    bats = (batter or {}).get("bats") or "R"
    box = BATTER_BOX.get(bats, BATTER_BOX["R"])
    return {
        "fielders": _marked(fielders, SPOTS),
        "runners": [
            {"base": base, "name": short_name(name), "x": spot[0], "y": spot[1]}
            for base, spot in BASE_SPOTS.items()
            if (name := (runners or {}).get(base))
        ],
        "batter": {"name": short_name((batter or {}).get("name")), "x": box[0], "y": box[1]},
        "pitcher": {"name": short_name((pitcher or {}).get("name")), "x": SPOTS["P"][0], "y": SPOTS["P"][1]},
        "bases": [{"base": base, "x": spot[0], "y": spot[1]} for base, spot in BASE_SPOTS.items()],
        "ball": ball,
        "ball_end": {"x": ball["points"][-1][0], "y": ball["points"][-1][1]} if ball else None,
        "ball_points": " ".join(f"{x},{y}" for x, y in ball["points"]) if ball else "",
        "ball_css": "M " + " L ".join(f"{x} {y}" for x, y in ball["points"]) if ball else "",
        "caption": ball["caption"] if ball else "",
        "scoreboard": scoreboard,
        "outs": list(range(scoreboard["outs"])),
    }
