# ABOUTME: Finds possible duplicate players for admin review.
# ABOUTME: Identifies name matches, stubs vs FG/MLB entries, and disambiguation candidates.
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q
from django.core.management.base import BaseCommand

from ulmg import models, utils


def _normalize_pair(player1, player2):
    """Return (p1, p2) with p1.id < p2.id for consistent ordering."""
    if player1.id <= player2.id:
        return player1, player2
    return player2, player1


def _is_stub(player):
    """Player has no external IDs - likely hand-added."""
    return (
        not player.fg_id
        and not player.mlbam_id
        and not player.bref_id
    )


def _id_count(player):
    """Count of external IDs for ranking (more = more complete)."""
    count = 0
    if player.fg_id:
        count += 1
    if player.mlbam_id:
        count += 1
    if player.bref_id:
        count += 1
    return count


def _clearly_different(player1, player2):
    """True if these are clearly different people (disambiguate)."""
    if player1.birthdate and player2.birthdate and player1.birthdate != player2.birthdate:
        return True
    if player1.fg_id and player2.fg_id and player1.fg_id != player2.fg_id:
        return True
    if player1.mlbam_id and player2.mlbam_id and player1.mlbam_id != player2.mlbam_id:
        return True
    return False


class Command(BaseCommand):
    help = "Find possible duplicate players and create DuplicatePlayerCandidate records for admin review."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print candidates, do not create DuplicatePlayerCandidate records",
        )
        parser.add_argument(
            "--min-similarity",
            type=float,
            default=0.85,
            help="Minimum trigram similarity for name match (default 0.85)",
        )
        parser.add_argument(
            "--exact-name-only",
            action="store_true",
            help="Only consider exact name matches (case-insensitive)",
        )
        parser.add_argument(
            "--clear-pending",
            action="store_true",
            help="Delete existing PENDING candidates before finding (so you can re-run)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        min_similarity = options["min_similarity"]
        exact_name_only = options["exact_name_only"]
        clear_pending = options["clear_pending"]

        if clear_pending and not dry_run:
            deleted, _ = models.DuplicatePlayerCandidate.objects.filter(
                status=models.DuplicatePlayerCandidate.PENDING
            ).delete()
            self.stdout.write(f"Cleared {deleted} pending candidates.")

        seen_pairs = set()
        created_count = 0

        players = list(models.Player.objects.all().order_by("id"))
        self.stdout.write(f"Checking {len(players)} players for duplicates...")

        for i, p1 in enumerate(players):
            if exact_name_only:
                matches = models.Player.objects.filter(
                    name__iexact=p1.name
                ).exclude(id=p1.id)
            else:
                matches = (
                    models.Player.objects.annotate(
                        similarity=TrigramSimilarity("name", p1.name)
                    )
                    .filter(similarity__gte=min_similarity)
                    .exclude(id=p1.id)
                )

            for p2 in matches:
                pair_key = (min(p1.id, p2.id), max(p1.id, p2.id))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                if _clearly_different(p1, p2):
                    continue

                p_lo, p_hi = _normalize_pair(p1, p2)
                match_reason = self._describe_match(p_lo, p_hi)

                if dry_run:
                    self.stdout.write(
                        f"  {p_lo.name} (id={p_lo.id}) <-> {p_hi.name} (id={p_hi.id})"
                    )
                    self.stdout.write(f"    Reason: {match_reason}")
                    self._print_player_info(p_lo)
                    self._print_player_info(p_hi)
                    created_count += 1
                    continue

                obj, created = models.DuplicatePlayerCandidate.objects.get_or_create(
                    player1=p_lo,
                    player2=p_hi,
                    defaults={
                        "status": models.DuplicatePlayerCandidate.PENDING,
                        "match_reason": match_reason,
                    },
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Created: {p_lo.name} (id={p_lo.id}) <-> {p_hi.name} (id={p_hi.id})"
                        )
                    )

        self.stdout.write(f"\nFound {created_count} duplicate candidate pair(s).")
        if not dry_run:
            pending = models.DuplicatePlayerCandidate.objects.filter(
                status=models.DuplicatePlayerCandidate.PENDING
            ).count()
            self.stdout.write(f"Total pending for review: {pending}")

    def _describe_match(self, p1, p2):
        if _is_stub(p1) and not _is_stub(p2):
            return "Stub (no IDs) vs player with IDs"
        if _is_stub(p2) and not _is_stub(p1):
            return "Stub (no IDs) vs player with IDs"
        return "Name match (review for disambiguation)"

    def _print_player_info(self, p):
        ids = []
        if p.fg_id:
            ids.append(f"FG:{p.fg_id}")
        if p.mlbam_id:
            ids.append(f"MLB:{p.mlbam_id}")
        if p.bref_id:
            ids.append(f"BRef:{p.bref_id}")
        id_str = ", ".join(ids) if ids else "no IDs"
        self.stdout.write(
            f"    - id={p.id} {p.name} | {p.position or '-'} | {p.birthdate or 'no DOB'} | {id_str}"
        )
