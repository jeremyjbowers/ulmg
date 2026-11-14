# ABOUTME: The club's home field: park scores for the sim, and the dimensions the game page draws the park from.
# ABOUTME: A missing score plays at 100. Dimensions come from data/parks/dimensions.json through load_park_dimensions.

"""Home field for one club.

The field is a Venue. Team.home_field is the park that club plays in. A venue
that still points at the team is used when the team has no home field.

Scores are the integer indexes on the venue, and 100 is an average park.
The sim reads singles (pf_1b), doubles (pf_2b), triples (pf_3b) and home runs
(pf_hr). An event with no index uses park_factor, then pf_runs, then 100.
Those event scores are how a game at Coors Field scores more runs than a game
at Tropicana Field. The runs index is not applied on top of the event scores.

`rules` is what the game page draws the park from. Missing keys are filled
from DEFAULT_RULES, the generic park. load_park_dimensions writes them from
data/parks/dimensions.json, keyed by MLB venue id.

    distances_ft and wall_ft: lf_line, left_center, center, right_center, rf_line, in feet
    foul_ft: feet of foul ground outside each foul line
    surface: grass or turf
    roof: open, retractable, or dome
    ground_rules: short text

Venue.sprites is still a column, but nothing reads it.
"""

import copy
import json
from pathlib import Path

from ulmg import models

DISTANCE_KEYS = ("lf_line", "left_center", "center", "right_center", "rf_line")
SURFACES = ("grass", "turf")
ROOFS = ("open", "retractable", "dome")

DIMENSION_FILE = Path(__file__).resolve().parent.parent / "data" / "parks" / "dimensions.json"

# The generic park: 330 down the lines, 380 in the alleys, 400 to center.
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
    return clean_rules(stored)


def clean_rules(stored):
    """Stored rules made whole: each key that is a park rule is kept, and the generic park fills the rest."""
    stored = stored if isinstance(stored, dict) else {}
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


def rule_problems(stored):
    """The rules clean_rules would drop from stored, by name, such as "surface" or "wall_ft.center"."""
    cleaned = clean_rules(stored)
    problems = []
    for key in ("distances_ft", "wall_ft"):
        points = stored.get(key)
        if points is None:
            continue
        if not isinstance(points, dict):
            problems.append(key)
            continue
        for point, value in points.items():
            if cleaned[key].get(point) != value:
                problems.append(f"{key}.{point}")
    for key in ("foul_ft", "surface", "roof", "ground_rules"):
        if key in stored and cleaned[key] != stored[key]:
            problems.append(key)
    return problems


def dimension_file(path=None):
    """The parks in the dimension file, keyed by MLB venue id. Raises ValueError when it is not that map."""
    payload = json.loads(Path(path or DIMENSION_FILE).read_text())
    if not isinstance(payload, dict) or not all(isinstance(entry, dict) for entry in payload.values()):
        raise ValueError("The dimension file is not a map of MLB venue ids to parks.")
    return payload


RULE_KEYS = ("distances_ft", "wall_ft", "foul_ft", "surface", "roof", "ground_rules")


def load_dimensions(parks, dry_run=False):
    """
    Write each park's dimensions onto the Venue with its MLB venue id, through clean_rules.
    A rule the file does not set keeps what the venue had. Returns (stored venues,
    unmatched (venue id, name) pairs, problems as "Park: rule" text).
    """
    stored, unmatched, problems = [], [], []
    venues = {v.mlb_venue_id: v for v in models.Venue.objects.filter(mlb_venue_id__in=list(parks))}
    for venue_id, entry in parks.items():
        venue = venues.get(str(venue_id))
        name = entry.get("name") or str(venue_id)
        if venue is None:
            unmatched.append((str(venue_id), name))
            continue
        given = {key: entry[key] for key in RULE_KEYS if key in entry}
        problems.extend(f"{name}: {problem}" for problem in rule_problems(given))
        current = venue.rules if isinstance(venue.rules, dict) else {}
        merged = {**current, **given}
        for key in ("distances_ft", "wall_ft"):
            if isinstance(current.get(key), dict) and isinstance(given.get(key), dict):
                merged[key] = {**current[key], **given[key]}
        stored.append(venue)
        if not dry_run:
            venue.rules = clean_rules(merged)
            venue.save(update_fields=["rules", "last_modified"])
    return stored, unmatched, problems


def art(team):
    """The home field as the game page draws it: its name, scores and rules."""
    venue = home_venue(team)
    return {
        "name": venue.name if venue is not None else "",
        "scores": scores(venue),
        "rules": rules(venue),
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
