# ABOUTME: Crosswalk and loader for the 2012-2018 draft history file.
# ABOUTME: Historical club names become the current abbreviation, then DraftPick rows.

import csv
import re
from collections import defaultdict
from pathlib import Path

from django.db import transaction

from ulmg import models


# Names as they appear in the history file, and the club that name is now.
CLUB_ABBREV = {
    "Anaheim": "ABQ",
    "Austin": "PEN",
    "Boston": "ATL",
    "Carolina": "CAR",
    "Chicago": "CHI",
    "Cincinnati": "CIN",
    "Cleveland": "CLE",
    "Detroit": "DET",
    "Heartland": "HCH",
    "High Desert": "HCH",
    "Long Island": "LNG",
    "Louisville": "LOU",
    "New York": "NYH",
    "Northwest": "DCM",
    "Peninsula": "PEN",
    "Philadelphia": "KCB",
    "Pittsburgh": "PIT",
    "San Diego": "LNG",
    "St. Louis": "DEL",
    "Washington": "CAR",
    "Windy City": "HCH",
}

DRAFT_TYPES = {
    "AA": models.DraftPick.AA_TYPE,
    "Open": models.DraftPick.OPEN_TYPE,
    # The midseason Bonus B draft is the AA draft.
    "Bonus B": models.DraftPick.AA_TYPE,
    "Competitive Balance": models.DraftPick.BALANCE_TYPE,
}

HISTORY_PATH = Path(__file__).resolve().parents[1] / "data" / "ulmg" / "draft-history.csv"

_OWNER_SPLIT = re.compile(r"\s+(?:via|through|and)\s+", re.IGNORECASE)


def original_club_name(owner):
    """The club that owned the pick before it changed hands."""
    text = (owner or "").strip()
    if not text:
        return ""
    return _OWNER_SPLIT.split(text)[0].strip()


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def prepare(rows):
    """Turn file rows into pick values, including a number for each compensation pick."""
    if rows and "27_club_abbrev" not in rows[0]:
        raise ValueError("Draft history is missing the 27_club_abbrev column")

    groups = {}
    for row in rows:
        raw_type = (row.get("draft_type") or "").strip()
        draft_type = DRAFT_TYPES.get(raw_type)
        if not draft_type:
            raise ValueError(f"Unknown draft type {raw_type!r}")
        season = (row.get("draft_season") or "").strip()
        if season not in (models.DraftPick.OFFSEASON, models.DraftPick.MIDSEASON):
            raise ValueError(f"Unknown draft season {season!r}")
        round_raw = (row.get("round") or "").strip()
        draft_round = int(round_raw) if round_raw else 1
        key = ((row.get("year") or "").strip(), season, draft_type, draft_round)
        groups.setdefault(key, []).append(row)

    prepared = []
    for key, group in groups.items():
        prepared.extend(_number_group(key, group))
    return prepared


def load_history(path, *, dry_run=False, replace=False):
    """Create DraftPick rows from the history file.

    A pick already stored for the same year, season, draft, round, and number
    is left as it is. Pass replace=True to delete those drafts and load the
    file's version. A player is linked when exactly one player has that name.
    The player's current club is not changed.
    """
    prepared = prepare(read_rows(path))
    teams = {team.abbreviation: team for team in models.Team.objects.all()}
    _require_teams(prepared, teams)

    file_events = {(item["year"], item["season"], item["draft_type"]) for item in prepared}
    existing_keys = set() if replace else _existing_pick_keys(prepared)
    skipped_events = set()
    to_create = []
    for item in prepared:
        if _pick_key(item) in existing_keys:
            skipped_events.add((item["year"], item["season"], item["draft_type"]))
            continue
        to_create.append(item)
    by_name, by_strat = _player_index()

    linked = 0
    unlinked = 0
    if dry_run:
        for item in to_create:
            if _resolve(item["player_name"], by_name, by_strat):
                linked += 1
            else:
                unlinked += 1
        return _result(len(to_create), len(prepared) - len(to_create), linked, unlinked, skipped_events)

    with transaction.atomic():
        if replace:
            for year, season, draft_type in file_events:
                models.DraftPick.objects.filter(
                    year=year, season=season, draft_type=draft_type
                ).delete()
        for item in to_create:
            player = _resolve(item["player_name"], by_name, by_strat)
            pick = models.DraftPick(
                year=item["year"],
                season=item["season"],
                draft_type=item["draft_type"],
                draft_round=item["draft_round"],
                pick_number=item["pick_number"],
                team=teams[item["abbrev"]],
                original_team=teams.get(item["original_abbrev"]),
                team_name=item["team_name"],
                player_name=item["player_name"],
                pick_notes=item["pick_notes"],
            )
            # Save without a player so DraftPick.save does not move him onto the drafting club.
            pick.save()
            if player:
                pick.player = player
                pick.slugify()
                models.DraftPick.objects.filter(pk=pick.pk).update(
                    player_id=player.id, slug=pick.slug
                )
                linked += 1
            else:
                unlinked += 1

    return _result(len(to_create), len(prepared) - len(to_create), linked, unlinked, skipped_events)


def describe(result, *, dry_run=False):
    verb = "Would create" if dry_run else "Created"
    count = result["created"]
    noun = "pick" if count == 1 else "picks"
    lines = [f"{verb} {count} {noun}."]
    if result["linked"]:
        noun = "player" if result["linked"] == 1 else "players"
        lines.append(f"Linked {result['linked']} {noun}.")
    if result["unlinked"]:
        lines.append(f"{result['unlinked']} picks keep the name from the file.")
    if result["skipped"]:
        events = ", ".join(result["skipped_events"])
        lines.append(f"Skipped {result['skipped']} picks already in the league ({events}).")
    return "\n".join(lines)


def _number_group(key, group):
    year, season, draft_type, draft_round = key
    assigned = []
    used = set()
    comps = []
    for row in group:
        raw = (row.get("pick_in_round") or "").strip()
        if raw.isdigit():
            number = int(raw)
            used.add(number)
            assigned.append((row, number, False))
        elif raw == "comp":
            comps.append(row)
        else:
            raise ValueError(f"Bad pick number {raw!r} for {row.get('player_name')}")
    next_number = max(used, default=0)
    for row in comps:
        next_number += 1
        while next_number in used:
            next_number += 1
        used.add(next_number)
        assigned.append((row, next_number, True))

    prepared = []
    for row, number, compensatory in assigned:
        abbrev = (row.get("27_club_abbrev") or "").strip()
        if not abbrev:
            raise ValueError(f"{row.get('player_name')} has no 27_club_abbrev")
        owner = original_club_name(row.get("original_pick_owner"))
        if owner and owner not in CLUB_ABBREV:
            raise ValueError(f"No current club for {owner!r}")
        prepared.append(
            {
                "year": year,
                "season": season,
                "draft_type": draft_type,
                "draft_round": draft_round,
                "pick_number": number,
                "abbrev": abbrev,
                "original_abbrev": CLUB_ABBREV[owner] if owner else "",
                "team_name": (row.get("drafting_team") or "").strip(),
                "player_name": (row.get("player_name") or "").strip(),
                "pick_notes": _notes(row, compensatory),
            }
        )
    return prepared


def _notes(row, compensatory):
    note = (row.get("notes") or "").strip()
    parts = []
    if compensatory and "compensation" not in note.casefold():
        parts.append("Compensation pick")
    if note:
        parts.append(note)
    via = (row.get("via_chain") or "").strip()
    if via:
        parts.append(via)
    source = (row.get("source_url") or "").strip()
    if source:
        parts.append(source)
    return "\n".join(parts)


def _require_teams(prepared, teams):
    missing = []
    for item in prepared:
        for label, abbrev in (
            ("drafting club", item["abbrev"]),
            ("original club", item["original_abbrev"]),
        ):
            if abbrev and abbrev not in teams:
                missing.append(f"{item['year']} {item['player_name']}: {label} {abbrev}")
    if missing:
        shown = "; ".join(missing[:8])
        extra = len(missing) - 8
        if extra > 0:
            shown = f"{shown}; and {extra} more"
        raise ValueError(f"No team for {shown}")


def _pick_key(item):
    return (
        item["year"],
        item["season"],
        item["draft_type"],
        item["draft_round"],
        item["pick_number"],
    )


def _existing_pick_keys(prepared):
    years = {item["year"] for item in prepared}
    if not years:
        return set()
    return set(
        models.DraftPick.objects.filter(year__in=years).values_list(
            "year", "season", "draft_type", "draft_round", "pick_number"
        )
    )


def _player_index():
    by_name = defaultdict(list)
    by_strat = defaultdict(list)
    for player in models.Player.objects.all():
        if player.name:
            by_name[player.name.casefold()].append(player)
        if player.strat_name:
            by_strat[player.strat_name.casefold()].append(player)
    return by_name, by_strat


def _resolve(name, by_name, by_strat):
    hits = by_name.get((name or "").casefold(), [])
    if len(hits) == 1:
        return hits[0]
    if hits:
        return None
    hits = by_strat.get((name or "").casefold(), [])
    if len(hits) == 1:
        return hits[0]
    return None


def _result(created, skipped, linked, unlinked, skipped_events):
    return {
        "created": created,
        "skipped": skipped,
        "linked": linked,
        "unlinked": unlinked,
        "skipped_events": sorted(
            f"{year} {season} {draft_type}" for year, season, draft_type in skipped_events
        ),
    }
