# ABOUTME: Builds the roster index the trade builder hands to the browser.
# ABOUTME: Clubs are alphabetical by city, and each side draws a roster only after one is picked.

from django.conf import settings

from ulmg import models


def _player_label(row):
    parts = [bit for bit in (row["position"], row["name"]) if bit]
    label = " ".join(parts)
    if row["level"]:
        label = f"{label} · {row['level']}"
    if row["is_ulmg_trade_block"]:
        label = f"{label} · block"
    return label


def _pick_label(row):
    return " ".join(bit for bit in (row["year"], row["season"], row["slug"]) if bit)


def trade_builder_assets():
    """Owned players and unused picks, grouped by club, for the trade builder."""
    teams = list(models.Team.objects.all())
    teams.sort(
        key=lambda team: (
            (team.city or "").casefold(),
            (team.nickname or "").casefold(),
            (team.abbreviation or "").casefold(),
        )
    )

    rosters = {
        team.abbreviation.lower(): {"hitters": [], "pitchers": [], "picks": []}
        for team in teams
        if team.abbreviation
    }

    players = models.Player.objects.filter(is_owned=True, team__isnull=False).order_by(
        "position", "last_name", "first_name", "id"
    ).values(
        "id",
        "name",
        "position",
        "level",
        "is_ulmg_trade_block",
        "team__abbreviation",
    )
    for row in players:
        abbr = (row["team__abbreviation"] or "").lower()
        roster = rosters.get(abbr)
        if roster is None:
            continue
        kind = "pitchers" if row["position"] == "P" else "hitters"
        roster[kind].append(
            {"id": f"player-{row['id']}", "label": _player_label(row)}
        )

    picks = models.DraftPick.objects.filter(
        year__gte=str(settings.CURRENT_SEASON),
        player__isnull=True,
        team__isnull=False,
    ).order_by(
        "year", "season", "draft_type", "draft_round", "pick_number", "id"
    ).values("id", "year", "season", "slug", "team__abbreviation")
    for row in picks:
        abbr = (row["team__abbreviation"] or "").lower()
        roster = rosters.get(abbr)
        if roster is None:
            continue
        roster["picks"].append({"id": f"pick-{row['id']}", "label": _pick_label(row)})

    return {
        "teams": [
            {
                "abbr": team.abbreviation.lower(),
                "label": f"{team.city} {team.nickname} ({team.abbreviation})",
            }
            for team in teams
            if team.abbreviation
        ],
        "rosters": rosters,
    }
