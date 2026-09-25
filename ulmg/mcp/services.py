# ABOUTME: Read-only service functions backing the MCP JSON API.
# ABOUTME: Shared by Django views and suitable for in-process tool calls.
from django.conf import settings
from django.db.models import Q
from django.shortcuts import get_object_or_404

from ulmg import models, utils
from ulmg.mcp import serializers


def get_season_context(owner=None):
    team = owner.team() if owner else None
    return {
        "season": settings.CURRENT_SEASON,
        "season_type": settings.CURRENT_SEASON_TYPE,
        "season_half": getattr(settings, "TEAM_SEASON_HALF", None),
        "stats_season": utils.get_current_season(),
        "mlb_roster_size": settings.MLB_ROSTER_SIZE,
        "org_cap": 75,
        "org_cap_midseason_aa": 76,
        "b_level_floor": 20,
        "protect_40man_slots": 40,
        "my_team": serializers.team_brief(team),
        "my_owner": (
            {"name": owner.name, "email": owner.email} if owner else None
        ),
    }


def list_teams():
    teams = models.Team.objects.all().order_by("division", "abbreviation")
    return {"teams": [serializers.team_brief(t) for t in teams]}


def _resolve_team(abbreviation=None, owner=None):
    if abbreviation:
        return get_object_or_404(
            models.Team, abbreviation__iexact=abbreviation.strip()
        )
    if owner:
        team = owner.team()
        if team:
            return team
    raise models.Team.DoesNotExist("No team specified and owner has no team")


def get_team_roster(abbreviation=None, owner=None):
    team = _resolve_team(abbreviation=abbreviation, owner=owner)
    players = list(
        models.Player.objects.filter(team=team)
        .select_related("team")
        .prefetch_related(serializers.player_stat_season_prefetch())
        .order_by("position", "-level_order", "last_name", "first_name")
    )
    mlb = [
        p
        for p in players
        if p.is_ulmg_mlb_roster and not p.is_ulmg_aaa_roster and not p.is_ulmg_reserve
    ]
    aaa = [p for p in players if p.is_ulmg_aaa_roster]
    aa = [
        p
        for p in players
        if not p.is_ulmg_mlb_roster and not p.is_ulmg_aaa_roster
    ]
    return {
        "team": serializers.team_brief(team),
        "counts": {
            "total": len(players),
            "mlb_30man": len(mlb),
            "aaa": len(aaa),
            "aa": len(aa),
            "protect_40man": sum(1 for p in players if p.is_ulmg_35man_roster),
            "b_level": sum(1 for p in players if p.level == "B"),
            "asr": sum(1 for p in players if p.is_ulmg_reserve),
        },
        "mlb": [serializers.player_brief(p) for p in mlb],
        "aaa": [serializers.player_brief(p) for p in aaa],
        "aa": [serializers.player_brief(p) for p in aa],
    }


def get_roster_compliance(abbreviation=None, owner=None):
    roster = get_team_roster(abbreviation=abbreviation, owner=owner)
    counts = roster["counts"]
    season_type = settings.CURRENT_SEASON_TYPE
    org_cap = 76 if season_type == "midseason" else 75
    return {
        "team": roster["team"],
        "season": settings.CURRENT_SEASON,
        "season_type": season_type,
        "counts": counts,
        "limits": {
            "mlb_30man_cap": settings.MLB_ROSTER_SIZE,
            "mlb_30man_ok": counts["mlb_30man"] <= settings.MLB_ROSTER_SIZE,
            "protect_40man_cap": 40,
            "protect_40man_ok": counts["protect_40man"] <= 40,
            "org_cap": org_cap,
            "total_ok": counts["total"] <= org_cap,
            "b_level_floor": 20,
            "b_level_ok": counts["b_level"] >= 20,
        },
    }


def _to_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("y", "yes", "t", "true", "on", "1")


def search_players(
    *,
    season=None,
    level=None,
    position=None,
    owned=None,
    classification=None,
    carded=None,
    name=None,
    team=None,
    on_40man=None,
    on_mlb=None,
    on_aaa=None,
    trade_block=None,
    pa_cutoff=None,
    ip_cutoff=None,
    gs_cutoff=None,
    qualified_at=None,
    limit=100,
):
    """Filter players; prefers PlayerStatSeason when season/stats filters apply."""
    use_stats = any(
        v not in (None, "")
        for v in (season, carded, classification, pa_cutoff, ip_cutoff, gs_cutoff, qualified_at)
    )
    limit = min(int(limit or 100), 500)

    if use_stats:
        search_season = utils.get_current_season()
        if season:
            search_season = int(season)
        elif carded:
            try:
                search_season = int(carded)
            except (TypeError, ValueError):
                pass

        qs = models.PlayerStatSeason.objects.select_related("player", "player__team").filter(
            is_career=False, season=search_season
        )
        if classification:
            qs = qs.filter(classification=classification)
        if carded is not None and str(carded).strip():
            qs = qs.filter(classification="1-mlb").filter(utils.mlb_appearances_q())
        owned_bool = _to_bool(owned) if owned is not None and str(owned) != "" else None
        if owned_bool is True:
            qs = qs.filter(player__team__isnull=False)
        elif owned_bool is False:
            qs = qs.filter(player__team__isnull=True)
        if level:
            qs = qs.filter(player__level=level)
        if position:
            if position.lower() == "h":
                qs = qs.exclude(player__position="P")
            elif position.lower() == "p":
                qs = qs.filter(player__position__icontains="P")
            else:
                qs = qs.filter(player__position__icontains=position)
        if team:
            qs = qs.filter(player__team__abbreviation__iexact=team)
        if name:
            qs = qs.filter(player__name__icontains=name)
        if _to_bool(on_40man) is True:
            qs = qs.filter(player__is_ulmg_35man_roster=True)
        elif _to_bool(on_40man) is False:
            qs = qs.filter(player__is_ulmg_35man_roster=False)
        if _to_bool(on_mlb) is True:
            qs = qs.filter(player__is_ulmg_mlb_roster=True)
        elif _to_bool(on_mlb) is False:
            qs = qs.filter(player__is_ulmg_mlb_roster=False)
        if _to_bool(on_aaa) is True:
            qs = qs.filter(player__is_ulmg_aaa_roster=True)
        elif _to_bool(on_aaa) is False:
            qs = qs.filter(player__is_ulmg_aaa_roster=False)
        if _to_bool(trade_block) is True:
            qs = qs.filter(player__is_ulmg_trade_block=True)
        if pa_cutoff:
            qs = qs.filter(hit_stats__pa__gte=int(pa_cutoff))
        if ip_cutoff:
            qs = qs.filter(pitch_stats__ip__gte=int(ip_cutoff))
        if gs_cutoff:
            qs = qs.filter(pitch_stats__gs__gte=int(gs_cutoff))
        if qualified_at:
            qs = qs.filter(fg_positions__contains=[qualified_at.upper()])

        qs = qs.order_by(
            "player__position",
            "-player__level_order",
            "player__last_name",
            "player__first_name",
        )
        seen = set()
        players = []
        for row in qs[: limit * 3]:
            if row.player_id in seen:
                continue
            seen.add(row.player_id)
            players.append(serializers.player_brief(row.player, stat_season=row))
            if len(players) >= limit:
                break
        return {"season": search_season, "count": len(players), "players": players}

    # Player-only path (no season/stats filters) — still attach best stats.
    qs = models.Player.objects.select_related("team").prefetch_related(
        serializers.player_stat_season_prefetch()
    )
    owned_bool = _to_bool(owned) if owned is not None and str(owned) != "" else None
    if owned_bool is True:
        qs = qs.filter(team__isnull=False)
    elif owned_bool is False:
        qs = qs.filter(team__isnull=True)
    if level:
        qs = qs.filter(level=level)
    if position:
        if position.lower() == "h":
            qs = qs.exclude(position="P")
        elif position.lower() == "p":
            qs = qs.filter(position__icontains="P")
        else:
            qs = qs.filter(position__icontains=position)
    if team:
        qs = qs.filter(team__abbreviation__iexact=team)
    if name:
        qs = qs.filter(name__icontains=name)
    if _to_bool(on_40man) is True:
        qs = qs.filter(is_ulmg_35man_roster=True)
    elif _to_bool(on_40man) is False:
        qs = qs.filter(is_ulmg_35man_roster=False)
    if _to_bool(on_mlb) is True:
        qs = qs.filter(is_ulmg_mlb_roster=True)
    elif _to_bool(on_mlb) is False:
        qs = qs.filter(is_ulmg_mlb_roster=False)
    if _to_bool(on_aaa) is True:
        qs = qs.filter(is_ulmg_aaa_roster=True)
    elif _to_bool(on_aaa) is False:
        qs = qs.filter(is_ulmg_aaa_roster=False)
    if _to_bool(trade_block) is True:
        qs = qs.filter(is_ulmg_trade_block=True)

    qs = qs.order_by("position", "-level_order", "last_name", "first_name")[:limit]
    players = [serializers.player_brief(p) for p in qs]
    return {"season": None, "count": len(players), "players": players}


def list_draft_picks(
    *,
    team=None,
    year=None,
    season=None,
    draft_type=None,
    original_team=None,
    limit=500,
):
    qs = models.DraftPick.objects.select_related(
        "team", "original_team", "player", "player__team"
    ).prefetch_related(
        serializers.player_stat_season_prefetch("player__playerstatseason_set")
    )
    if team:
        qs = qs.filter(team__abbreviation__iexact=team)
    if original_team:
        qs = qs.filter(original_team__abbreviation__iexact=original_team)
    if year:
        qs = qs.filter(year=str(year))
    if season:
        qs = qs.filter(season=season)
    if draft_type:
        qs = qs.filter(draft_type=draft_type)
    qs = qs.order_by("-year", "season", "draft_type", "draft_round", "pick_number")
    picks = [serializers.pick_brief(p) for p in qs[: int(limit or 500)]]
    return {"count": len(picks), "picks": picks}


def list_trades(*, team=None, season=None, limit=200):
    qs = models.Trade.objects.all().order_by("-date", "-id")
    if team:
        qs = qs.filter(teams__abbreviation__iexact=team).distinct()
    if season:
        qs = qs.filter(season=int(season))
    trades = []
    for trade in qs[: int(limit or 200)]:
        payload = serializers.trade_brief(trade)
        if payload:
            trades.append(payload)
    return {"count": len(trades), "trades": trades}


def list_trade_block():
    players = (
        models.Player.objects.filter(team__isnull=False, is_ulmg_trade_block=True)
        .select_related("team")
        .prefetch_related(serializers.player_stat_season_prefetch())
        .order_by("position", "last_name", "first_name")
    )
    return {
        "count": players.count(),
        "players": [serializers.player_brief(p) for p in players],
    }


def list_draft_pool(pool="unprotected"):
    """
    pool: unprotected | offseason_available | midseason_available
    """
    current_season = settings.CURRENT_SEASON
    pool = (pool or "unprotected").lower()

    if pool == "midseason_available":
        players = models.Player.objects.filter(is_owned=False).filter(
            Q(playerstatseason__season=current_season)
            & (
                Q(playerstatseason__hit_stats__pa__gt=0)
                | Q(playerstatseason__pitch_stats__ip__gt=0)
            )
        ).distinct()
    elif pool == "offseason_available":
        players = models.Player.objects.filter(
            is_owned=True, team__isnull=False
        ).exclude(
            playerstatseason__season=current_season,
            playerstatseason__is_ulmg35man_roster=True,
        ).distinct()
    else:
        # unprotected (Open Draftable from other teams)
        if settings.CURRENT_SEASON_TYPE == "midseason":
            carded_season = utils.get_midseason_open_carded_season(current_season)
            players = models.Player.objects.filter(
                is_owned=True,
                level="V",
                team__isnull=False,
                is_ulmg_midseason_unprotected=True,
                carded_seasons__contains=[carded_season],
            ).distinct()
        else:
            players = models.Player.objects.filter(
                is_owned=True,
                level__in=["A", "V"],
                team__isnull=False,
                is_ulmg_35man_roster=False,
            ).distinct()

    players = players.select_related("team").prefetch_related(
        serializers.player_stat_season_prefetch()
    ).order_by(
        "position", "-level_order", "last_name", "first_name"
    )
    return {
        "pool": pool,
        "season": current_season,
        "season_type": settings.CURRENT_SEASON_TYPE,
        "count": players.count(),
        "players": [serializers.player_brief(p) for p in players],
    }


def get_my_wishlist(owner):
    wishlist = models.Wishlist.objects.filter(owner=owner).first()
    if not wishlist:
        return {"players": [], "count": 0}
    rows = (
        models.WishlistPlayer.objects.filter(wishlist=wishlist)
        .select_related("player", "player__team")
        .prefetch_related(
            serializers.player_stat_season_prefetch("player__playerstatseason_set")
        )
        .order_by("tier", "rank", "player__last_name")
    )
    players = [serializers.wishlist_player_brief(wp) for wp in rows]
    return {"count": len(players), "players": players}
