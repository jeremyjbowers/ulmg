import os

from django.core.management.base import BaseCommand

from ulmg import models, utils


class Command(BaseCommand):
    help = (
        "Evaluate data/rosters/untracked_players.json to find existing Player rows "
        "without mlbam_id, report likely matches, and optionally apply updates/create."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help="Apply changes: set mlbam_id on clear matches and create missing players.",
        )
        parser.add_argument(
            "--min-score",
            type=float,
            default=0.8,
            help="Minimum trigram similarity (0-1) to consider a candidate a likely match.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Only process the first N untracked players (useful for spot checks).",
        )

    def handle(self, *args, **options):
        apply_changes = options.get("apply", False)
        min_score = float(options.get("min_score"))
        limit = options.get("limit")

        # Load untracked players list (local first, S3 fallback)
        path = "data/rosters/untracked_players.json"
        untracked = utils.s3_manager.get_file_content(path)
        if not untracked:
            try:
                import ujson as json
            except Exception:
                import json
            if os.path.exists(path):
                with open(path, "r") as f:
                    untracked = json.load(f)

        if not untracked:
            self.stdout.write(self.style.WARNING("No untracked players found to evaluate."))
            return

        if limit:
            untracked = untracked[:limit]

        # Counters
        report = {
            "total": len(untracked),
            "linked": 0,
            "created": 0,
            "skipped_ambiguous": 0,
            "skipped_errors": 0,
            "already_present": 0,
        }

        def normalize_position(pos):
            try:
                return utils.normalize_pos(pos)
            except Exception:
                return None

        for idx, candidate in enumerate(untracked, start=1):
            try:
                mlbam_id = str(candidate.get("mlbam_id") or candidate.get("mlbamid") or "").strip()
                name = candidate.get("name") or candidate.get("player") or ""
                position = normalize_position(candidate.get("position"))
                mlb_org = candidate.get("mlb_org")

                if not name:
                    report["skipped_errors"] += 1
                    self.stdout.write(self.style.WARNING(f"[{idx}/{report['total']}] Missing name, skipping."))
                    continue

                # If player already exists with this mlbam_id, skip
                if mlbam_id:
                    existing_by_id = models.Player.objects.filter(mlbam_id=mlbam_id).first()
                    if existing_by_id:
                        report["already_present"] += 1
                        self.stdout.write(
                            f"[{idx}/{report['total']}] Already present by mlbam_id: {existing_by_id.name} ({mlbam_id})"
                        )
                        continue

                # Try to find likely existing player record by name/org/position that lacks mlbam_id
                # Fuzzy match by name using helper (do not pass mlb_org; Player uses current_mlb_org)
                matches_qs = utils.fuzzy_find_player(
                    name_fragment=name, score=min_score, position=position
                ).filter(mlbam_id__isnull=True)
                if mlb_org:
                    matches_qs = matches_qs.filter(current_mlb_org=mlb_org)

                candidates = list(matches_qs)

                header = f"[{idx}/{report['total']}] {name} {position or ''} {mlb_org or ''}".strip()

                if len(candidates) == 0:
                    # No likely match in DB. Offer to create if we have enough data.
                    if apply_changes:
                        if not mlbam_id:
                            # Creating without mlbam_id can create future duplicates; skip
                            report["skipped_ambiguous"] += 1
                            self.stdout.write(
                                self.style.WARNING(
                                    f"{header} — no match and no mlbam_id; skipping create to avoid dupes"
                                )
                            )
                            continue

                        obj = models.Player(
                            name=name,
                            position=position or "DH",
                            mlbam_id=mlbam_id,
                            current_mlb_org=mlb_org,
                        )
                        obj.save()
                        report["created"] += 1
                        self.stdout.write(self.style.SUCCESS(f"{header} — created new Player id={obj.id}"))
                    else:
                        self.stdout.write(f"{header} — create? mlbam_id={mlbam_id or 'None'}")
                    continue

                if len(candidates) == 1:
                    obj = candidates[0]
                    if apply_changes and mlbam_id:
                        obj.mlbam_id = mlbam_id
                        obj.current_mlb_org = obj.current_mlb_org or mlb_org
                        obj.save()
                        report["linked"] += 1
                        self.stdout.write(self.style.SUCCESS(f"{header} — linked to {obj.name} (id={obj.id})"))
                    else:
                        self.stdout.write(
                            f"{header} — likely match: {obj.name} (id={obj.id}) mlbam_id={mlbam_id or 'None'}"
                        )
                    continue

                # Multiple candidates: print brief list and skip unless apply with zero ambiguity
                self.stdout.write(self.style.WARNING(f"{header} — ambiguous ({len(candidates)} matches):"))
                for c in candidates[:5]:
                    self.stdout.write(f"  - {c.id} {c.name} pos={c.position} org={c.current_mlb_org}")
                report["skipped_ambiguous"] += 1

            except Exception as e:
                report["skipped_errors"] += 1
                self.stdout.write(self.style.ERROR(f"[{idx}/{report['total']}] ERROR: {e}"))

        # Summary
        self.stdout.write("")
        self.stdout.write("=" * 50)
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(f"EVALUATION SUMMARY [{mode}]")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Untracked players processed: {report['total']}")
        self.stdout.write(f"Linked existing players: {report['linked']}")
        self.stdout.write(f"Created new players: {report['created']}")
        self.stdout.write(f"Already present by mlbam_id: {report['already_present']}")
        self.stdout.write(f"Skipped (ambiguous): {report['skipped_ambiguous']}")
        self.stdout.write(f"Skipped (errors): {report['skipped_errors']}")


