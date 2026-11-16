# ABOUTME: Reads the Statcast sprint-speed leaderboard and stores each runner on his MLB hitting line.
# ABOUTME: The card reads that sprint speed. 27 feet per second is an average runner.

import json
from pathlib import Path

import requests

from ulmg.utils import fangraphs_id

LEADERBOARD = "https://baseballsavant.mlb.com/leaderboard/sprint_speed"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def leaderboard_url(year, minimum=5):
    """The qualified sprint-speed board for one season. `minimum` is competitive runs."""
    return (
        f"{LEADERBOARD}?min_season={year}&max_season={year}"
        f"&position=&team=&min={minimum}"
        f"&sort=r_sprint_speed_top50percent_pretty&sortDir=desc"
    )


def _float(value):
    """A Savant number, or None when the cell is blank."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if text == "" or text.lower() == "null":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _int(value):
    number = _float(value)
    if number is None:
        return None
    return int(number)


def runners_from_html(html):
    """The leaderboard rows embedded in the sprint-speed page."""
    marker = "var data ="
    start = html.find(marker)
    if start < 0:
        raise ValueError("The sprint-speed page has no data table.")
    bracket = html.find("[", start)
    if bracket < 0:
        raise ValueError("The sprint-speed page has no data table.")
    try:
        payload, _end = json.JSONDecoder().raw_decode(html[bracket:])
    except json.JSONDecodeError as error:
        raise ValueError("The sprint-speed table could not be read.") from error
    if not isinstance(payload, list):
        raise ValueError("The sprint-speed table is not a list of runners.")
    return payload


def runner_speed(row):
    """One runner: MLBAM id, sprint speed in feet per second, competitive runs, and bolts."""
    return {
        "mlbam_id": fangraphs_id(row.get("runner_id")),
        "sprint_speed": _float(row.get("r_sprint_speed_top50percent")),
        "sprint_runs": _int(row.get("n")),
        "sprint_bolts": _int(row.get("n_bolts")),
        "name": row.get("name_display_last_first") or "",
    }


def qualified_runners(rows):
    """One row per runner. A repeated id keeps the row with more competitive runs."""
    best = {}
    for row in rows:
        speed = runner_speed(row)
        if not speed["mlbam_id"] or speed["sprint_speed"] is None or speed["sprint_speed"] <= 0:
            continue
        current = best.get(speed["mlbam_id"])
        runs = speed["sprint_runs"] or 0
        if current is None or runs > (current["sprint_runs"] or 0):
            best[speed["mlbam_id"]] = speed
    return best


def rows_from_file(path):
    text = Path(path).read_text()
    if str(path).endswith(".json"):
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("The sprint-speed file is not a list of runners.")
        return payload
    return runners_from_html(text)


def fetch_runners(year, minimum=5):
    response = requests.get(
        leaderboard_url(year, minimum),
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=30,
    )
    response.raise_for_status()
    return runners_from_html(response.text)


def load_sprint_speeds(rows, season, dry_run=False):
    """
    Write sprint speed onto each runner's 1-mlb hitting line for `season`.
    A runner with no such line is counted and skipped. A dry run writes nothing.
    """
    from ulmg import models

    lines = 0
    no_line = 0
    missing = 0
    for speed in qualified_runners(rows).values():
        players = list(models.Player.objects.filter(mlbam_id=speed["mlbam_id"]))
        if not players:
            missing += 1
            continue
        wrote = False
        for player in players:
            stat_seasons = models.PlayerStatSeason.objects.filter(
                player=player,
                season=season,
                classification="1-mlb",
                is_career=False,
            )
            for stat_season in stat_seasons:
                if not stat_season.hit_stats:
                    continue
                wrote = True
                lines += 1
                if dry_run:
                    continue
                stats = dict(stat_season.hit_stats)
                stats["sprint_speed"] = speed["sprint_speed"]
                stats["sprint_runs"] = speed["sprint_runs"]
                stats["sprint_bolts"] = speed["sprint_bolts"]
                stat_season.hit_stats = stats
                stat_season.save()
        if not wrote:
            no_line += 1
    return {"lines": lines, "no_line": no_line, "missing": missing}
