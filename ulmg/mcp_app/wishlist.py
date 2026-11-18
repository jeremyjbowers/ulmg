# ABOUTME: Draft-prep wishlist reads and writes for the owner's MCP key.
# ABOUTME: Follow, unfollow, tiers, and notes stay on that owner's wishlist.
from django.db import transaction
from django.db.models import Q

from ulmg import models, utils
from ulmg.mcp_app import serializers


# The draft board UI caps each numbered tier at 20 players.
TIER_LIMIT = 20
TIER_MIN = 1
TIER_MAX = 5


class WishlistError(Exception):
    """A wishlist change the caller can correct, with an HTTP status."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def _owner_wishlist(owner, *, create):
    wishlist = models.Wishlist.objects.filter(owner=owner).order_by("id").first()
    if wishlist is None and create:
        wishlist = models.Wishlist.objects.create(owner=owner)
    return wishlist


def _player(player_id):
    try:
        pk = int(player_id)
    except (TypeError, ValueError):
        raise WishlistError("player_id must be an integer")
    try:
        return models.Player.objects.get(pk=pk)
    except models.Player.DoesNotExist:
        raise WishlistError(f"No player with id {pk}", status=404)


def _parse_tier(tier):
    """Return 1-5, or None when the player should sit in watched."""
    if tier is None or tier == "" or tier == 0 or tier == "0":
        return None
    try:
        value = int(tier)
    except (TypeError, ValueError):
        raise WishlistError(
            "tier must be an integer from 1 to 5, or 0 to move the player to watched"
        )
    if value < TIER_MIN or value > TIER_MAX:
        raise WishlistError(
            "tier must be an integer from 1 to 5, or 0 to move the player to watched"
        )
    return value


def _parse_rank(rank):
    if rank is None or rank == "":
        return None
    try:
        value = int(rank)
    except (TypeError, ValueError):
        raise WishlistError("rank must be an integer")
    if value < 1:
        raise WishlistError("rank must be 1 or greater")
    return value


def _load_brief(wp):
    loaded = (
        models.WishlistPlayer.objects.filter(pk=wp.pk)
        .select_related("player", "player__team")
        .prefetch_related(
            serializers.player_stat_season_prefetch("player__playerstatseason_set")
        )
        .get()
    )
    return serializers.wishlist_player_brief(loaded)


def _rows(wishlist, tier):
    return list(
        models.WishlistPlayer.objects.select_for_update()
        .filter(wishlist=wishlist, tier=tier)
        .order_by("rank", "id")
    )


def _renumber(wishlist, tier):
    if tier is None or tier < TIER_MIN or tier > TIER_MAX:
        return
    for index, row in enumerate(_rows(wishlist, tier), start=1):
        if row.rank != index:
            row.rank = index
            row.save(update_fields=["rank"])


def _insert(wishlist, wp, tier, rank):
    already = wp.tier == tier
    previous_rank = wp.rank
    siblings = [row for row in _rows(wishlist, tier) if row.pk != wp.pk]
    if rank is None and already:
        index = len(siblings)
        my_key = (
            previous_rank if previous_rank is not None else 10**9,
            wp.id or 0,
        )
        for i, row in enumerate(siblings):
            row_key = (row.rank if row.rank is not None else 10**9, row.id)
            if row_key > my_key:
                index = i
                break
        siblings.insert(index, wp)
    elif rank is None:
        siblings.append(wp)
    else:
        siblings.insert(max(0, min(rank - 1, len(siblings))), wp)

    for index, row in enumerate(siblings, start=1):
        dirty = []
        if row.tier != tier:
            row.tier = tier
            dirty.append("tier")
        if row.rank != index:
            row.rank = index
            dirty.append("rank")
        if dirty:
            row.save(update_fields=dirty)


def follow_player(owner, player_id):
    """Put a player on the wishlist as watched. An existing tier is left alone."""
    player = _player(player_id)
    with transaction.atomic():
        wishlist = _owner_wishlist(owner, create=True)
        existing = (
            models.WishlistPlayer.objects.select_for_update()
            .filter(wishlist=wishlist, player=player)
            .order_by("id")
            .first()
        )
        created = existing is None
        if created:
            existing = models.WishlistPlayer.objects.create(
                wishlist=wishlist, player=player, tier=None, rank=None
            )
    return {
        "followed": True,
        "created": created,
        "player": _load_brief(existing),
    }


def unfollow_player(owner, player_id):
    """Remove a player from the wishlist. Missing rows are a no-op."""
    player = _player(player_id)
    with transaction.atomic():
        wishlist = _owner_wishlist(owner, create=False)
        if wishlist is None:
            removed = []
        else:
            removed = list(
                models.WishlistPlayer.objects.select_for_update().filter(
                    wishlist=wishlist, player=player
                )
            )
        tiers = {
            row.tier
            for row in removed
            if row.tier is not None and TIER_MIN <= row.tier <= TIER_MAX
        }
        for row in removed:
            row.delete()
        for tier in tiers:
            _renumber(wishlist, tier)
    return {
        "followed": False,
        "removed": bool(removed),
        "player_id": player.id,
        "name": player.name,
    }


def set_wishlist_tier(owner, player_id, tier, rank=None):
    """
    Move a player onto a numbered tier or back to watched.

    tier 1-5 places them on the board. tier 0 or null clears the tier.
    A tier already holding 20 other players is rejected. Passing rank
    inserts at that slot and renumbers the tier. Omitting rank appends.
    """
    player = _player(player_id)
    target = _parse_tier(tier)
    slot = _parse_rank(rank)
    with transaction.atomic():
        wishlist = _owner_wishlist(owner, create=True)
        wp = (
            models.WishlistPlayer.objects.select_for_update()
            .filter(wishlist=wishlist, player=player)
            .order_by("id")
            .first()
        )
        created = wp is None
        if created:
            wp = models.WishlistPlayer.objects.create(
                wishlist=wishlist, player=player, tier=None, rank=None
            )
        old_tier = wp.tier
        if target is None:
            if wp.tier is not None or wp.rank is not None:
                wp.tier = None
                wp.rank = None
                wp.save(update_fields=["tier", "rank"])
            if old_tier is not None and TIER_MIN <= old_tier <= TIER_MAX:
                _renumber(wishlist, old_tier)
        else:
            others = (
                models.WishlistPlayer.objects.select_for_update()
                .filter(wishlist=wishlist, tier=target)
                .exclude(pk=wp.pk)
                .count()
            )
            if old_tier != target and others >= TIER_LIMIT:
                raise WishlistError(
                    (
                        f"Tier {target} is full ({TIER_LIMIT}/{TIER_LIMIT}). "
                        "Move someone to watched or another tier first."
                    ),
                    status=409,
                )
            _insert(wishlist, wp, target, slot)
            if (
                old_tier is not None
                and old_tier != target
                and TIER_MIN <= old_tier <= TIER_MAX
            ):
                _renumber(wishlist, old_tier)
        tier_count = (
            models.WishlistPlayer.objects.filter(wishlist=wishlist, tier=target).count()
            if target is not None
            else None
        )
        payload = _load_brief(wp)
    return {
        "followed": True,
        "created": created,
        "tier": target,
        "tier_count": tier_count,
        "tier_limit": TIER_LIMIT,
        "player": payload,
    }


def set_wishlist_note(owner, player_id, note):
    """Set the wishlist note. Follows the player first when they are not on it."""
    if note is None:
        raise WishlistError("note is required")
    player = _player(player_id)
    text = str(note)
    with transaction.atomic():
        wishlist = _owner_wishlist(owner, create=True)
        wp = (
            models.WishlistPlayer.objects.select_for_update()
            .filter(wishlist=wishlist, player=player)
            .order_by("id")
            .first()
        )
        created = wp is None
        if created:
            wp = models.WishlistPlayer.objects.create(
                wishlist=wishlist,
                player=player,
                tier=None,
                rank=None,
                note=text,
            )
        else:
            wp.note = text
            wp.save(update_fields=["note"])
    return {
        "followed": True,
        "created": created,
        "player": _load_brief(wp),
    }


def _eligibility_text(draft_type, season):
    if draft_type == "aa":
        return "Unowned B-level players."
    if season == "offseason":
        return "Unowned V and A players."
    return "Unowned players with a card from the prior season."


def _board_rows(owner, filters):
    wishlist = _owner_wishlist(owner, create=False)
    if wishlist is None:
        return models.WishlistPlayer.objects.none()
    player_filters = {f"player__{key}": value for key, value in filters.items()}
    return (
        models.WishlistPlayer.objects.filter(wishlist=wishlist, **player_filters)
        .select_related("player", "player__team")
        .prefetch_related(
            serializers.player_stat_season_prefetch("player__playerstatseason_set")
        )
    )


def get_draft_board(owner, draft_type="open", list_type=None):
    """
    The owner's draft-prep board: their picks, the draft order, and the
    wishlist split into tiers 1-5 plus watched. Same eligibility as the site.
    """
    draft_type = (draft_type or "open").strip().lower()
    if list_type is not None:
        list_type = str(list_type).strip().lower() or None
    if draft_type not in ("open", "aa"):
        raise WishlistError("draft_type must be open or aa")
    if list_type not in (None, "offseason", "midseason"):
        raise WishlistError("list_type must be offseason or midseason")

    year, season = utils.get_draft_prep_year_season(draft_type, list_type=list_type)
    team = owner.team()
    order_qs = (
        models.DraftPick.objects.filter(
            year=str(year), season=season, draft_type=draft_type
        )
        .select_related("team", "original_team", "player", "player__team")
        .prefetch_related(
            serializers.player_stat_season_prefetch("player__playerstatseason_set")
        )
        .order_by("overall_pick_number", "draft_round", "pick_number", "id")
    )
    my_picks = []
    order = []
    for pick in order_qs:
        brief = serializers.pick_brief(pick)
        mine = team is not None and pick.team_id == team.id
        if mine:
            my_picks.append(brief)
        order.append(
            {
                "id": pick.id,
                "overall_pick_number": pick.overall_pick_number,
                "draft_round": pick.draft_round,
                "pick_number": pick.pick_number,
                "team": pick.team.abbreviation if pick.team else None,
                "player_name": pick.player_name
                or (pick.player.name if pick.player else None),
                "mine": mine,
            }
        )

    rows = _board_rows(
        owner, utils.get_draft_prep_player_filters(draft_type, list_type=season)
    )
    tiers = []
    for tier_num in range(TIER_MIN, TIER_MAX + 1):
        tier_rows = rows.filter(tier=tier_num).order_by("rank", "player__last_name")
        players = [serializers.wishlist_player_brief(wp) for wp in tier_rows]
        tiers.append(
            {
                "tier": tier_num,
                "count": len(players),
                "limit": TIER_LIMIT,
                "players": players,
            }
        )
    watched_rows = rows.filter(
        Q(tier__isnull=True) | Q(tier__lt=TIER_MIN) | Q(tier__gt=TIER_MAX)
    ).order_by("rank", "player__last_name")
    watched = [serializers.wishlist_player_brief(wp) for wp in watched_rows]
    return {
        "draft_type": draft_type,
        "year": year,
        "season": season,
        "eligibility": _eligibility_text(draft_type, season),
        "tier_limit": TIER_LIMIT,
        "my_team": serializers.team_brief(team),
        "my_picks": my_picks,
        "order": order,
        "tiers": tiers,
        "watched": watched,
        "watched_count": len(watched),
    }
