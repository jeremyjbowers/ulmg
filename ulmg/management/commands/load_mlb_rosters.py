# ABOUTME: Fetches MLB/MiLB rosters from MLB Stats API and writes all_mlb_rosters.json.
# ABOUTME: Covers MLB, AAA, AA, High-A, A, Short-A, and Rookie (FCL, AZL, DSL).
from django.core.management.base import BaseCommand
from django.conf import settings
import datetime
import os

import requests
import ujson as json

from ulmg import utils


class Command(BaseCommand):
    help = (
        "Fetch rosters from MLB Stats API for all levels (MLB through DSL) "
        "and write data/rosters/all_mlb_rosters.json for downstream ingest."
    )

    MLB_ORG_LOOKUP = {
        108: "LAA",
        109: "AZ",
        110: "BAL",
        111: "BOS",
        112: "CHC",
        113: "CIN",
        114: "CLE",
        115: "COL",
        116: "DET",
        117: "HOU",
        118: "KC",
        119: "LAD",
        120: "WSH",
        121: "NYM",
        133: "ATH",
        134: "PIT",
        135: "SD",
        136: "SEA",
        137: "SF",
        138: "STL",
        139: "TB",
        140: "TEX",
        141: "TOR",
        142: "MIN",
        143: "PHI",
        144: "ATL",
        145: "CWS",
        146: "MIA",
        147: "NYY",
        158: "MIL",
    }

    SPORT_IDS = (1, 11, 12, 13, 14, 15, 16)

    def _get_mlb_org(self, team):
        if team["sport"]["id"] == 1:
            return team.get("abbreviation")
        parent_id = team.get("parentOrgId")
        return self.MLB_ORG_LOOKUP.get(parent_id) if parent_id else None

    def _roster_status(self, team, status_desc):
        desc = (status_desc or "").lower()
        if "injured" in desc:
            if "60" in desc:
                return "IL-60"
            if "15" in desc:
                return "IL-15"
            if "10" in desc:
                return "IL-10"
            if "7" in desc:
                return "IL-7"
        if team["sport"]["id"] == 1 and "active" in desc:
            return "MLB"
        return "MINORS"

    def _fetch_roster(self, team_id, season):
        url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster/40Man"
        r = requests.get(url, params={"season": season}, timeout=30)
        r.raise_for_status()
        return r.json().get("roster") or []

    def handle(self, *args, **options):
        season = getattr(settings, "CURRENT_SEASON", datetime.datetime.now().year)
        team_list_url = "https://statsapi.mlb.com/api/v1/teams/"
        self.stdout.write(f"Fetching teams from {team_list_url}")
        resp = requests.get(team_list_url, timeout=30)
        resp.raise_for_status()
        teams = [t for t in resp.json().get("teams", []) if t["sport"]["id"] in self.SPORT_IDS]

        all_players = []
        seen_ids = set()
        total = len(teams)
        for idx, team in enumerate(teams, 1):
            name = team.get("name", team.get("id"))
            self.stdout.write(f"[{idx}/{total}] {name}")
            mlb_org = self._get_mlb_org(team)
            roster = self._fetch_roster(team["id"], season)
            for p in roster:
                person = p.get("person", {})
                mlbam_id = person.get("id")
                if not mlbam_id or mlbam_id in seen_ids:
                    continue
                seen_ids.add(mlbam_id)
                pos_abbr = (p.get("position") or {}).get("abbreviation", "")
                status_desc = (p.get("status") or {}).get("description", "")
                all_players.append({
                    "mlbam_id": mlbam_id,
                    "name": person.get("fullName", ""),
                    "position": utils.normalize_pos(pos_abbr) if pos_abbr else "DH",
                    "mlb_org": mlb_org,
                    "roster_status": self._roster_status(team, status_desc),
                })

        out_path = "data/rosters/all_mlb_rosters.json"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            f.write(json.dumps(all_players))
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(all_players)} players to {out_path}"))
