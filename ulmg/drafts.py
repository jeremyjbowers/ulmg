# ABOUTME: Draft boards for the nav and the /draft/ index, read from DraftPick.
# ABOUTME: The nav keeps the three newest draft events plus any after the current season.

from ulmg import league, models

NAV_EVENT_COUNT = 3
SEASON_RANK = {"offseason": 0, "midseason": 1}


def _type_label(draft_type):
    if draft_type == "aa":
        return "AA"
    return (draft_type or "").replace("_", " ").title()


def board_title(year, season, draft_type):
    """Title used in the nav."""
    season_label = (season or "").title()
    return f"{year} {season_label} {_type_label(draft_type)}".strip()


def board_label(season, draft_type):
    """Season and draft, without the year. The index puts the year on its own heading."""
    season_label = (season or "").title()
    return f"{season_label} {_type_label(draft_type)}".strip()


def board_url(year, season, draft_type):
    return f"/draft/{year}/{season}/{draft_type}/"


def _event_key(year, season):
    try:
        year_number = int(year)
    except (TypeError, ValueError):
        year_number = 0
    return (year_number, SEASON_RANK.get(season, -1))


def all_boards():
    """Every distinct draft, newest year first. A year's boards stay together."""
    rows = (
        models.DraftPick.objects.exclude(year__isnull=True)
        .exclude(year="")
        .exclude(season__isnull=True)
        .exclude(season="")
        .exclude(draft_type__isnull=True)
        .exclude(draft_type="")
        .order_by()
        .values_list("year", "season", "draft_type")
        .distinct()
    )
    boards = [
        {
            "year": year,
            "season": season,
            "draft_type": draft_type,
            "title": board_title(year, season, draft_type),
            "label": board_label(season, draft_type),
            "url": board_url(year, season, draft_type),
        }
        for year, season, draft_type in rows
    ]
    boards.sort(
        key=lambda board: (
            -_event_key(board["year"], board["season"])[0],
            -_event_key(board["year"], board["season"])[1],
            board["draft_type"] or "",
        )
    )
    return boards


def nav_boards():
    """Future draft events, then the three most recent current or past events."""
    current = _event_key(league.current_season(), league.current_season_type())
    selected = []
    kept_events = []
    for board in all_boards():
        key = _event_key(board["year"], board["season"])
        if key > current:
            selected.append(board)
            continue
        if key not in kept_events:
            if len(kept_events) >= NAV_EVENT_COUNT:
                continue
            kept_events.append(key)
        selected.append(board)
    return selected
