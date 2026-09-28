# ABOUTME: JSON serializers for MCP read responses.
# ABOUTME: Includes roster flags plus PlayerStatSeason hitting/pitching/xstats for agents.
from django.db.models import Prefetch

from ulmg import models, utils


def team_brief(team):
    if team is None:
        return None
    return {
        "id": team.id,
        "abbreviation": team.abbreviation,
        "city": team.city,
        "nickname": team.nickname,
        "division": team.division,
    }


def _pick(d, *keys):
    if not d:
        return None
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return None


def _hitter_summary(hit):
    if not hit:
        return None
    return {
        "pa": _pick(hit, "pa", "plate_appearances"),
        "ab": _pick(hit, "ab"),
        "g": _pick(hit, "g"),
        "avg": _pick(hit, "avg"),
        "obp": _pick(hit, "obp"),
        "slg": _pick(hit, "slg"),
        "ops": _pick(hit, "ops"),
        "hr": _pick(hit, "hr"),
        "sb": _pick(hit, "sb"),
        "r": _pick(hit, "r"),
        "rbi": _pick(hit, "rbi"),
        "bb": _pick(hit, "bb"),
        "so": _pick(hit, "so", "k"),
        "k_pct": _pick(hit, "k_pct"),
        "bb_pct": _pick(hit, "bb_pct"),
        "woba": _pick(hit, "woba"),
        "wrc_plus": _pick(hit, "wrc_plus"),
        "ops_plus": _pick(hit, "ops_plus"),
        "obp_plus": _pick(hit, "obp_plus"),
        "slg_plus": _pick(hit, "slg_plus"),
        "war": _pick(hit, "war"),
        "xavg": _pick(hit, "xavg", "xba"),
        "xwoba": _pick(hit, "xwoba"),
        "xslg": _pick(hit, "xslg"),
    }


def _pitcher_summary(pit):
    if not pit:
        return None
    return {
        "g": _pick(pit, "g"),
        "gs": _pick(pit, "gs"),
        "ip": _pick(pit, "ip"),
        "w": _pick(pit, "w"),
        "l": _pick(pit, "l"),
        "sv": _pick(pit, "sv"),
        "era": _pick(pit, "era"),
        "whip": _pick(pit, "whip"),
        "k_9": _pick(pit, "k_9", "k9"),
        "bb_9": _pick(pit, "bb_9", "bb9"),
        "hr_9": _pick(pit, "hr_9", "hr9"),
        "fip": _pick(pit, "fip"),
        "xfip": _pick(pit, "xfip"),
        "siera": _pick(pit, "siera"),
        "war": _pick(pit, "war"),
        "so": _pick(pit, "so", "k"),
        "bb": _pick(pit, "bb"),
    }


def _xstats_summary(hit, pit):
    """Pull expected-stat fields agents care about into one place."""
    xstats = {}
    if hit:
        for key, aliases in (
            ("xavg", ("xavg", "xba")),
            ("xwoba", ("xwoba",)),
            ("xslg", ("xslg",)),
            ("xobp", ("xobp",)),
            ("xbabip", ("xbabip",)),
        ):
            val = _pick(hit, *aliases)
            if val is not None:
                xstats[key] = val
    if pit:
        for key, aliases in (
            ("xfip", ("xfip",)),
            ("xera", ("xera",)),
            ("siera", ("siera",)),
        ):
            val = _pick(pit, *aliases)
            if val is not None:
                xstats[key] = val
    return xstats or None


def stat_season_brief(stat_season):
    """Serialize a PlayerStatSeason for MCP responses."""
    if stat_season is None:
        return None
    hit = stat_season.hit_stats or None
    pit = stat_season.pitch_stats or None
    hit_summary = _hitter_summary(hit)
    pit_summary = _pitcher_summary(pit)
    war = None
    if hit_summary and hit_summary.get("war") is not None:
        war = hit_summary["war"]
    elif pit_summary and pit_summary.get("war") is not None:
        war = pit_summary["war"]

    position_display = None
    if hasattr(stat_season, "position_display"):
        position_display = stat_season.position_display()
    defense = None
    if hasattr(stat_season, "defense_display"):
        defense = stat_season.defense_display()
    elif stat_season.defense:
        defense = list(stat_season.defense)

    return {
        "season": stat_season.season,
        "classification": stat_season.classification,
        "level": stat_season.level,
        "mlb_org": getattr(stat_season, "mlb_org", None),
        "position_display": position_display,
        "defense": defense,
        "fg_positions": list(stat_season.fg_positions or []) or None,
        "war": war,
        "hit": hit_summary,
        "pitch": pit_summary,
        "xstats": _xstats_summary(hit, pit),
        # Full JSON blobs for anything beyond the curated summaries.
        "hit_stats_raw": hit,
        "pitch_stats_raw": pit,
    }


def player_stat_season_prefetch(lookup="playerstatseason_set"):
    """Prefetch non-career stat seasons newest-first for get_best_stat_season.

    Use lookup='player__playerstatseason_set' when the root queryset is not Player
    (e.g. WishlistPlayer or DraftPick).
    """
    stats_season = utils.get_stats_display_season_cap()
    return Prefetch(
        lookup,
        queryset=models.PlayerStatSeason.objects.filter(
            is_career=False,
            season__lte=stats_season,
        ).order_by("-season", "classification"),
        to_attr="all_stat_seasons",
    )


def player_brief(player, stat_season=None):
    """Player dict for search / roster / pools, including best available stats."""
    if stat_season is None:
        stat_season = player.get_best_stat_season()

    return {
        "id": player.id,
        "name": player.name,
        "position": player.position,
        "level": player.level,
        "age": player.age,
        "bats": getattr(player, "bats", None),
        "throws": getattr(player, "throws", None),
        "team": player.team.abbreviation if player.team else None,
        "mlb_org": player.current_mlb_org,
        "is_owned": player.is_owned,
        "on_40man_protect": bool(player.is_ulmg_35man_roster),
        "on_mlb_30man": bool(player.is_ulmg_mlb_roster),
        "on_aaa": bool(player.is_ulmg_aaa_roster),
        "is_asr": bool(player.is_ulmg_reserve),
        "is_trade_block": bool(player.is_ulmg_trade_block),
        "is_midseason_unprotected": bool(player.is_ulmg_midseason_unprotected),
        "is_2h_draft": bool(player.is_ulmg_2h_draft),
        "protections": {
            "1h_p": bool(player.is_ulmg_1h_p),
            "1h_c": bool(player.is_ulmg_1h_c),
            "1h_pos": bool(player.is_ulmg_1h_pos),
            "2h_p": bool(player.is_ulmg_2h_p),
            "2h_c": bool(player.is_ulmg_2h_c),
            "2h_pos": bool(player.is_ulmg_2h_pos),
        },
        "ids": {
            "mlbam_id": player.mlbam_id,
            "fg_id": player.fg_id,
        },
        "stats": stat_season_brief(stat_season),
    }


def pick_brief(pick):
    return {
        "id": pick.id,
        "year": pick.year,
        "season": pick.season,
        "draft_type": pick.draft_type,
        "draft_round": pick.draft_round,
        "pick_number": pick.pick_number,
        "overall_pick_number": pick.overall_pick_number,
        "slug": pick.slug,
        "skipped": bool(getattr(pick, "skipped", False)),
        "team": pick.team.abbreviation if pick.team else None,
        "original_team": (
            pick.original_team.abbreviation if pick.original_team else None
        ),
        "player": player_brief(pick.player) if pick.player else None,
        "player_name": pick.player_name,
    }


def _players_payload(players_qs):
    return [player_brief(p) for p in players_qs]


def _picks_payload(picks_qs):
    out = []
    for pick in picks_qs.select_related("original_team", "player", "player__team"):
        # Stats may already be prefetched on pick.player; otherwise queried once.
        out.append(
            {
                "id": pick.id,
                "original_team": (
                    pick.original_team.abbreviation if pick.original_team else None
                ),
                "year": pick.year,
                "season": pick.season,
                "draft_type": pick.draft_type,
                "draft_round": pick.draft_round,
                "player": player_brief(pick.player) if pick.player else None,
            }
        )
    return out


def trade_brief(trade):
    receipts = list(
        trade.reciepts()
        .select_related("team")
        .prefetch_related(
            Prefetch(
                "players",
                queryset=models.Player.objects.select_related("team").prefetch_related(
                    player_stat_season_prefetch()
                ),
            ),
            "picks__original_team",
            "picks__player",
            "picks__player__team",
        )
    )
    if len(receipts) < 2:
        return None
    t1, t2 = receipts[0], receipts[1]
    return {
        "trade_id": trade.id,
        "date": trade.date.isoformat() if trade.date else None,
        "season": trade.season,
        "team_1": t1.team.abbreviation if t1.team else None,
        "team_1_receives": {
            "players": _players_payload(t1.players.all()),
            "picks": _picks_payload(t1.picks.all()),
        },
        "team_2": t2.team.abbreviation if t2.team else None,
        "team_2_receives": {
            "players": _players_payload(t2.players.all()),
            "picks": _picks_payload(t2.picks.all()),
        },
    }


def wishlist_player_brief(wp):
    payload = player_brief(wp.player)
    payload.update(
        {
            "tier": wp.tier,
            "rank": wp.rank,
            "note": wp.note,
            "tags": wp.tags or [],
            "future_value": wp.future_value,
        }
    )
    return payload
