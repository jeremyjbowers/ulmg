# ABOUTME: Logic for merging duplicate players or marking as not duplicates.
# ABOUTME: Transfers references from stub to keeper, then deletes stub.
from django.db import transaction
from django.utils import timezone

from ulmg import models


def player_info_dict(player):
    """Return a dict of key info for display."""
    if not player:
        return {}
    ids = []
    if player.fg_id:
        ids.append(f"FG:{player.fg_id}")
    if player.mlbam_id:
        ids.append(f"MLB:{player.mlbam_id}")
    if player.bref_id:
        ids.append(f"BRef:{player.bref_id}")
    return {
        "id": player.id,
        "name": player.name,
        "position": player.position or "-",
        "birthdate": str(player.birthdate) if player.birthdate else "no DOB",
        "ids": ", ".join(ids) if ids else "no IDs",
        "level": player.level or "-",
        "team": str(player.team) if player.team else "-",
        "is_owned": player.is_owned,
    }


def merge_delete_stub(keep_player, delete_player, user=None, candidate=None):
    """
    Merge: transfer all references from delete_player (stub) to keep_player, then delete stub.
    If candidate is provided, marks it as MERGED_DELETED_STUB before delete.
    Returns (success: bool, message: str).
    """
    if keep_player.id == delete_player.id:
        return False, "Cannot merge a player with themselves."

    with transaction.atomic():
        _transfer_playerstatseason(delete_player, keep_player)
        _transfer_draftpicks(delete_player, keep_player)
        _transfer_prospectratings(delete_player, keep_player)
        _transfer_transactions(delete_player, keep_player)
        _transfer_wishlistplayers(delete_player, keep_player)
        _transfer_tradereceipt_players(delete_player, keep_player)

        if candidate:
            candidate.status = models.DuplicatePlayerCandidate.MERGED_DELETED_STUB
            candidate.resolved_at = timezone.now()
            candidate.resolved_by = user
            candidate.save()

        delete_player.delete()
    return True, f"Merged and deleted stub {delete_player.name} (id={delete_player.id})."


def _transfer_playerstatseason(from_player, to_player):
    models.PlayerStatSeason.objects.filter(player=from_player).update(player=to_player)


def _transfer_draftpicks(from_player, to_player):
    models.DraftPick.objects.filter(player=from_player).update(player=to_player)


def _transfer_prospectratings(from_player, to_player):
    models.ProspectRating.objects.filter(player=from_player).update(player=to_player)


def _transfer_transactions(from_player, to_player):
    models.Transaction.objects.filter(player=from_player).update(player=to_player)


def _transfer_wishlistplayers(from_player, to_player):
    for wp in models.WishlistPlayer.objects.filter(player=from_player):
        existing = models.WishlistPlayer.objects.filter(
            wishlist=wp.wishlist, player=to_player
        ).first()
        if existing:
            wp.delete()
        else:
            wp.player = to_player
            wp.save()


def _transfer_tradereceipt_players(from_player, to_player):
    for receipt in models.TradeReceipt.objects.filter(players=from_player):
        receipt.players.remove(from_player)
        if to_player not in receipt.players.all():
            receipt.players.add(to_player)


def mark_not_duplicate(candidate, user=None):
    """
    Mark a DuplicatePlayerCandidate as NOT_DUPLICATE (disambiguated).
    """
    candidate.status = models.DuplicatePlayerCandidate.NOT_DUPLICATE
    candidate.resolved_at = timezone.now()
    candidate.resolved_by = user
    candidate.save()
    return True, "Marked as not duplicate."
