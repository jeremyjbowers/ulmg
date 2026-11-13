# ABOUTME: The club's home field: park scores for the sim, and the dimensions and plate the field art uses.
# ABOUTME: A missing score plays at 100. The plate stays empty until a builder writes the SVG for that park.

"""Home field for one club.

The field is a Venue. Team.home_field is the park that club plays in. A venue
that still points at the team is used when the team has no home field.

Scores are the integer indexes on the venue, and 100 is an average park.
The sim reads singles (pf_1b), doubles (pf_2b), triples (pf_3b) and home runs
(pf_hr). An event with no index uses park_factor, then pf_runs, then 100.
Those event scores are how a game at Coors Field scores more runs than a game
at Tropicana Field. The runs index is not applied on top of the event scores.

`rules` is what a field-art builder reads. Missing keys are filled from
DEFAULT_RULES, the generic park the page draws until a plate exists.

    distances_ft and wall_ft: lf_line, left_center, center, right_center, rf_line, in feet
    foul_ft: feet of foul ground outside each foul line
    surface: grass or turf
    roof: open, retractable, or dome
    ground_rules: short text

`sprites` is what that builder writes back onto the same field.

    version: integer
    plate_svg: inner SVG of the 320 by 180 field plate, the markup pixelkit's
        buildField returns (tile patterns, rects, bases, distance marks).
        No player sprites, no script, no event handlers. A full <svg> wrapper
        is stripped. Leave plate_svg empty and the page draws the generic plate.
"""

import copy
import re

from ulmg import models

DISTANCE_KEYS = ("lf_line", "left_center", "center", "right_center", "rf_line")
SURFACES = ("grass", "turf")
ROOFS = ("open", "retractable", "dome")

# The generic plate pixelkit draws: 330 down the lines, 380 in the alleys, 400 to center.
DEFAULT_RULES = {
    "distances_ft": {
        "lf_line": 330,
        "left_center": 380,
        "center": 400,
        "right_center": 380,
        "rf_line": 330,
    },
    "wall_ft": {
        "lf_line": 8,
        "left_center": 8,
        "center": 8,
        "right_center": 8,
        "rf_line": 8,
    },
    "foul_ft": 52,
    "surface": "grass",
    "roof": "open",
    "ground_rules": "",
}

_SCORE_FIELDS = (
    ("woba", "park_factor"),
    ("runs", "pf_runs"),
    ("single", "pf_1b"),
    ("double", "pf_2b"),
    ("triple", "pf_3b"),
    ("home_run", "pf_hr"),
)
_EVENT_FACTORS = (
    ("single_factor", "pf_1b"),
    ("double_factor", "pf_2b"),
    ("triple_factor", "pf_3b"),
    ("hr_factor", "pf_hr"),
)
_UNSAFE_PLATE = re.compile(r"<\s*script|javascript\s*:|on[a-z]+\s*=", re.IGNORECASE)


def home_venue(team):
    """The park the club plays in. The team's home field wins over a venue that merely points at the team."""
    if team is None:
        return None
    if getattr(team, "home_field_id", None):
        return team.home_field
    if not getattr(team, "pk", None):
        return None
    return models.Venue.objects.filter(team=team).order_by("pk").first()


def scores(venue):
    """Park indexes for one field, 100 meaning average. Missing indexes are left out."""
    if venue is None:
        return {}
    found = {}
    for key, attr in _SCORE_FIELDS:
        value = getattr(venue, attr, None)
        if _index(value) is None:
            continue
        found[key] = value
    return found


def rules(venue):
    """Dimensions and ground rules, with the generic park filling anything the field has not set."""
    stored = venue.rules if venue is not None and isinstance(getattr(venue, "rules", None), dict) else {}
    merged = copy.deepcopy(DEFAULT_RULES)
    merged["distances_ft"] = _points(stored.get("distances_ft"), merged["distances_ft"])
    merged["wall_ft"] = _points(stored.get("wall_ft"), merged["wall_ft"])
    foul = _positive(stored.get("foul_ft"))
    if foul is not None:
        merged["foul_ft"] = foul
    if stored.get("surface") in SURFACES:
        merged["surface"] = stored["surface"]
    if stored.get("roof") in ROOFS:
        merged["roof"] = stored["roof"]
    if isinstance(stored.get("ground_rules"), str):
        merged["ground_rules"] = stored["ground_rules"]
    return merged


def sprites(venue):
    """The plate a builder stored. A missing or unusable plate is null, and the page draws the generic field."""
    stored = venue.sprites if venue is not None and isinstance(getattr(venue, "sprites", None), dict) else {}
    version = stored.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        version = None
    return {"version": version, "plate_svg": _plate(stored.get("plate_svg"))}


def art(team):
    """The home field as the game page hands it to the field composer."""
    venue = home_venue(team)
    return {
        "name": venue.name if venue is not None else "",
        "scores": scores(venue),
        "rules": rules(venue),
        "sprites": sprites(venue),
    }


def engine_park(team):
    """The park block the sim reads. Event factors are omitted when that index has not been scored."""
    venue = home_venue(team)
    run = _index(getattr(venue, "park_factor", None)) if venue is not None else None
    if run is None and venue is not None:
        run = _index(getattr(venue, "pf_runs", None))
    payload = {
        "id": f"park-{team.abbreviation.lower()}",
        "run_factor": run if run is not None else 1.0,
    }
    if venue is None:
        return payload
    for key, attr in _EVENT_FACTORS:
        factor = _index(getattr(venue, attr, None))
        if factor is not None:
            payload[key] = factor
    return payload


def _index(value):
    """An index of 100 is a factor of 1. Zero, blank and non-numbers are unscored."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value <= 0:
        return None
    return value / 100


def _positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value <= 0:
        return None
    return value


def _points(stored, default):
    merged = dict(default)
    if not isinstance(stored, dict):
        return merged
    for key, value in stored.items():
        number = _positive(value)
        if number is not None:
            merged[key] = number
    return merged


def _plate(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or _UNSAFE_PLATE.search(text) or not text.startswith("<"):
        return None
    if text.lower().startswith("<svg"):
        text = re.sub(r"^<svg\b[^>]*>", "", text, count=1, flags=re.IGNORECASE)
        text = re.sub(r"</svg>\s*$", "", text, flags=re.IGNORECASE).strip()
    if not text:
        return None
    return text
