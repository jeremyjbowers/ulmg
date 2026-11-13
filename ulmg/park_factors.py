# ABOUTME: Reads the Statcast park-factor leaderboard and turns each park into Venue columns.
# ABOUTME: The page embeds the table as JSON. 100 is an average park. A blank index stays unscored.

import json
from pathlib import Path

import requests

LEADERBOARD = "https://baseballsavant.mlb.com/leaderboard/statcast-park-factors"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
ROLLING_WINDOWS = (1, 2, 3)

# Venue column, then the leaderboard key. pf_wobacon is wOBA on contact.
_COLUMNS = (
    ("park_factor", "index_woba"),
    ("pf_wobacon", "index_wobacon"),
    ("pf_bacon", "index_bacon"),
    ("pf_runs", "index_runs"),
    ("pf_obp", "index_obp"),
    ("pf_h", "index_hits"),
    ("pf_1b", "index_1b"),
    ("pf_2b", "index_2b"),
    ("pf_3b", "index_3b"),
    ("pf_hr", "index_hr"),
    ("pf_bb", "index_bb"),
    ("pf_so", "index_so"),
    ("pf_pa", "n_pa"),
)


def index(value):
    """A Savant index as an int. Blank, null, and non-numbers stay unscored."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if text == "" or text.lower() == "null":
        return None
    try:
        number = int(text)
    except ValueError:
        return None
    return number


def parks_from_html(html):
    """The leaderboard rows embedded in the Statcast page."""
    marker = "var data ="
    start = html.find(marker)
    if start < 0:
        raise ValueError("The park-factor page has no data table.")
    bracket = html.find("[", start)
    if bracket < 0:
        raise ValueError("The park-factor page has no data table.")
    try:
        payload, _end = json.JSONDecoder().raw_decode(html[bracket:])
    except json.JSONDecodeError as error:
        raise ValueError("The park-factor table could not be read.") from error
    if not isinstance(payload, list):
        raise ValueError("The park-factor table is not a list of parks.")
    return payload


def venue_defaults(row):
    """Score columns for one park. Rules, sprites, and the ULMG club stay as they are."""
    venue_id = str(row["venue_id"])
    defaults = {
        "name": row.get("venue_name") or "",
        "mlb_team": row.get("name_display_club") or "",
        "mlb_venue_url": (
            "https://baseballsavant.mlb.com/leaderboard/statcast-venue"
            f"?venueId={venue_id}"
        ),
        "pf_years": row.get("year_range") or "",
    }
    for column, key in _COLUMNS:
        defaults[column] = index(row.get(key))
    return defaults


def leaderboard_url(year, rolling=3, bat_side="", condition="All"):
    return (
        f"{LEADERBOARD}?type=year&year={year}&batSide={bat_side}"
        f"&stat=index_wOBA&condition={condition}&rolling={rolling}"
    )


def fetch_parks(year, rolling=3, bat_side="", condition="All"):
    response = requests.get(
        leaderboard_url(year, rolling, bat_side, condition),
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=30,
    )
    response.raise_for_status()
    return parks_from_html(response.text)


def rows_from_file(path):
    text = Path(path).read_text()
    if str(path).endswith(".json"):
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("The park-factor file is not a list of parks.")
        return payload
    return parks_from_html(text)


def load_parks(rows, dry_run=False):
    """Upsert each park by MLB venue id. A dry run counts the rows and writes nothing."""
    from ulmg import models

    saved = 0
    for row in rows:
        if not row.get("venue_id"):
            continue
        if dry_run:
            saved += 1
            continue
        models.Venue.objects.update_or_create(
            mlb_venue_id=str(row["venue_id"]),
            defaults=venue_defaults(row),
        )
        saved += 1
    return saved
