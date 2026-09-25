# ABOUTME: JSON serializers for MCP read responses.
# ABOUTME: Uses constitution-friendly roster field names for agent clarity.
from ulmg import models


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


def player_brief(player):
    """Compact player dict for search / roster / pools."""
    return {
        "id": player.id,
        "name": player.name,
        "position": player.position,
        "level": player.level,
        "age": player.age,
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
        "player": (
            {
                "id": pick.player.id,
                "name": pick.player.name,
                "position": pick.player.position,
            }
            if pick.player
            else None
        ),
        "player_name": pick.player_name,
    }


def _players_payload(players_qs):
    return [
        {"id": p.id, "name": p.name, "position": p.position, "level": p.level}
        for p in players_qs
    ]


def _picks_payload(picks_qs):
    out = []
    for pick in picks_qs.select_related("original_team", "player"):
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
                "player": (
                    {
                        "id": pick.player.id,
                        "name": pick.player.name,
                        "position": pick.player.position,
                    }
                    if pick.player
                    else None
                ),
            }
        )
    return out


def trade_brief(trade):
    receipts = list(
        trade.reciepts()
        .select_related("team")
        .prefetch_related("players", "picks__original_team", "picks__player")
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
