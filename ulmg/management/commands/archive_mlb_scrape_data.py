# ABOUTME: ARCHIVED - Original scrape_mlb_data. See documents/MLB_DATA_PIPELINE_RECOMMENDATION.md
# ABOUTME: Uses player.mlb_api_url to fetch birthdate, position, current_mlb_org from MLB API.
import time
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
import requests
from ulmg import models, utils
from ulmg.management.commands.load_mlb_rosters import Command as LoadMlbRostersCommand


class Command(BaseCommand):
    MLB_ORG_LOOKUP = LoadMlbRostersCommand.MLB_ORG_LOOKUP

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help=(
                "Process all players with mlbam_id. Refreshes org and position "
                "from MLB; fills missing birthdates."
            ),
        )

    def _mlb_org_from_parent_name(self, parent_org_name):
        if not parent_org_name:
            return None
        parts = parent_org_name.split()
        if not parts:
            return None
        lookup = getattr(settings, "MLB_URL_TO_ORG_NAME", {})
        candidates = [parts[-1].lower()]
        if len(parts) >= 2:
            candidates.insert(0, "".join(parts[-2:]).lower())
        for candidate in candidates:
            org = lookup.get(candidate)
            if org:
                return org
        return None

    def _mlb_org_from_current_team(self, current_team):
        if not current_team:
            return None
        sport_id = (current_team.get("sport") or {}).get("id")
        if sport_id == 1:
            return current_team.get("abbreviation")
        parent_org_id = current_team.get("parentOrgId")
        if parent_org_id:
            return self.MLB_ORG_LOOKUP.get(parent_org_id)
        return self._mlb_org_from_parent_name(current_team.get("parentOrgName"))

    def _set_player_mlb_org(self, player, mlb_org):
        if not mlb_org:
            return
        current_season = settings.CURRENT_SEASON
        pss = models.PlayerStatSeason.objects.filter(
            player=player,
            season=current_season,
            is_career=False,
        ).first()
        if pss:
            if pss.mlb_org != mlb_org:
                pss.mlb_org = mlb_org
                pss.save(update_fields=["mlb_org"])
            return
        models.PlayerStatSeason.objects.create(
            player=player,
            season=current_season,
            classification="2-milb",
            owned=player.is_owned,
            carded=False,
            mlb_org=mlb_org,
        )

    def handle(self, *args, **options):
        players = models.Player.objects.exclude(mlbam_id__isnull=True)
        if not options.get("all"):
            players = players.filter(
                Q(position__isnull=True) | Q(birthdate__isnull=True)
            )
        players = players.order_by("id")
        total = players.count()
        scope = "all players with mlbam_id" if options.get("all") else "players missing birthdate or position"
        self.stdout.write(f"Found {total} {scope}")

        updated = 0
        skipped = 0
        errors = 0

        for idx, p in enumerate(players, 1):
            if not p.mlb_api_url:
                self.stdout.write(
                    f"[{idx}/{total}] SKIP {p.name} (id={p.id}): no mlb_api_url"
                )
                skipped += 1
                continue

            self.stdout.write(
                f"[{idx}/{total}] Fetching {p.name} "
                f"(id={p.id}, mlbam={p.mlbam_id}, birthdate={p.birthdate or 'none'}, "
                f"position={p.position or 'none'}, org={p.current_mlb_org or 'none'})..."
            )

            try:
                r = requests.get(
                    p.mlb_api_url + "?hydrate=currentTeam,team",
                    timeout=30,
                )
                r.raise_for_status()
                data = r.json()
            except requests.RequestException as exc:
                self.stdout.write(self.style.ERROR(f"  ERROR: request failed: {exc}"))
                errors += 1
                time.sleep(1)
                continue

            people = data.get("people") or []
            if not people:
                self.stdout.write("  SKIP: no people data in API response")
                skipped += 1
                time.sleep(1)
                continue

            player = people[0]
            changes = []
            org_changed = False

            birth_date = player.get("birthDate")
            if birth_date and not p.birthdate:
                p.birthdate = birth_date
                changes.append(f"birthdate -> {birth_date}")

            primary_pos = (player.get("primaryPosition") or {}).get("abbreviation")
            if primary_pos:
                new_pos = utils.normalize_pos(primary_pos)
                if p.position != new_pos:
                    old_pos = p.position or "none"
                    p.position = new_pos
                    changes.append(f"position {old_pos} -> {new_pos} (MLB: {primary_pos})")

            scraped_mlb_org = self._mlb_org_from_current_team(player.get("currentTeam"))
            if scraped_mlb_org and scraped_mlb_org != p.current_mlb_org:
                old_org = p.current_mlb_org or "none"
                self._set_player_mlb_org(p, scraped_mlb_org)
                org_changed = True
                changes.append(f"current_mlb_org {old_org} -> {scraped_mlb_org}")

            if changes:
                p.save()
                if org_changed:
                    p.refresh_from_db()
                updated += 1
                self.stdout.write(f"  UPDATED: {', '.join(changes)}")
            else:
                self.stdout.write("  OK: nothing to update")

            time.sleep(1)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. updated={updated}, skipped={skipped}, errors={errors}, total={total}"
            )
        )
