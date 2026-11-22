# ABOUTME: FastMCP tool registration shared by HTTP and stdio transports.
# ABOUTME: Local backend uses Django services; remote backend uses the JSON API.
from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP

from ulmg.mcp_app import games as game_reads
from ulmg.mcp_app import services
from ulmg.mcp_app import wishlist as wishlist_ops
from ulmg.mcp_app.context import (
    current_token_allows_write,
    get_current_owner,
    require_current_owner,
)
from ulmg.mcp_app.db import db_sync
from ulmg.mcp_app.wishlist import WishlistError


INSTRUCTIONS = (
    "ULMG league tools for roster review, draft prep, and trade analysis. "
    "Roster terms: on_mlb_30man = Major League active roster; "
    "on_40man_protect = Open Draft protected V/A list (site field "
    "is_ulmg_35man_roster). Sim results: list_games (scores), get_box_score, "
    "get_standings, get_team_season, list_sim_stats (6-ulmg sim lines), "
    "get_sim_leaders, and get_usage (PA, starts and innings against caps). "
    "Their season defaults to the league season, which turns over on "
    "November 1. Wishlist follow, unfollow, tier, and note tools "
    "write the authenticated owner's board and need a read-write API key. "
    "There are no roster writes and no trade execution."
)


_READ_ONLY = {
    "error": "Forbidden",
    "detail": "This API key is read-only",
    "status": 403,
}


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _http_json(
    method: str,
    path: str,
    params: Optional[dict] = None,
    body: Optional[dict] = None,
) -> Any:
    base = (os.environ.get("ULMG_API_URL") or "").rstrip("/")
    token = os.environ.get("ULMG_API_TOKEN") or ""
    if not base or not token:
        raise RuntimeError(
            "Stdio mode requires ULMG_API_URL and ULMG_API_TOKEN"
        )
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=60.0) as client:
        resp = client.request(
            method,
            f"{base}{path}",
            params=params or {},
            json=body,
            headers=headers,
        )
        if resp.status_code == 401:
            raise RuntimeError("ULMG API token rejected (401)")
        if resp.status_code >= 500:
            resp.raise_for_status()
        payload = resp.json()
        if resp.status_code >= 400 and isinstance(payload, dict):
            payload = {**payload, "status": resp.status_code}
        return payload


def _http_get(path: str, params: Optional[dict] = None) -> Any:
    return _http_json("GET", path, params=params)


def _wishlist_error(exc: WishlistError) -> dict:
    return {"error": exc.message, "status": exc.status}


async def _game_read(func, /, **kwargs) -> str:
    """Run a game_reads function; a missing game or team and a bad argument come back as JSON errors."""
    try:
        data = await db_sync(func, **kwargs)
    except game_reads.GameReadError as exc:
        return _dump({"error": exc.message, "status": exc.status})
    return _dump(data)


def _params(**values) -> dict:
    return {k: v for k, v in values.items() if v is not None and v != ""}


def build_mcp(*, mode: str = "local") -> FastMCP:
    """
    mode=local  — in-process Django ORM (used by HTTPS /mcp on the website)
    mode=remote — HTTP client to ULMG_API_URL (used by stdio bridge)
    """
    mcp = FastMCP("ulmg", instructions=INSTRUCTIONS)

    if mode == "remote":
        _register_remote_tools(mcp)
    else:
        _register_local_tools(mcp)
    return mcp


def _register_local_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_season_context() -> str:
        """Current ULMG season, half, roster limits, and the authenticated owner's team."""
        owner = get_current_owner()
        data = await db_sync(services.get_season_context, owner=owner)
        return _dump(data)

    @mcp.tool()
    async def list_teams() -> str:
        """List all ULMG teams (abbreviation, city, nickname, division)."""
        data = await db_sync(services.list_teams)
        return _dump(data)

    @mcp.tool()
    async def get_team_roster(abbreviation: Optional[str] = None) -> str:
        """Full team roster split into mlb (30-man), aaa, and aa. Omitting abbreviation uses your team."""
        owner = get_current_owner()
        data = await db_sync(
            services.get_team_roster,
            abbreviation=abbreviation,
            owner=owner,
        )
        return _dump(data)

    @mcp.tool()
    async def get_roster_compliance(abbreviation: Optional[str] = None) -> str:
        """Counts vs constitutional limits (30-man, 40-man protect, 75/76 org, 20 B-floor)."""
        owner = get_current_owner()
        data = await db_sync(
            services.get_roster_compliance,
            abbreviation=abbreviation,
            owner=owner,
        )
        return _dump(data)

    @mcp.tool()
    async def search_players(
        name: Optional[str] = None,
        level: Optional[str] = None,
        position: Optional[str] = None,
        owned: Optional[str] = None,
        team: Optional[str] = None,
        season: Optional[int] = None,
        classification: Optional[str] = None,
        carded: Optional[str] = None,
        on_40man: Optional[str] = None,
        on_mlb: Optional[str] = None,
        on_aaa: Optional[str] = None,
        trade_block: Optional[str] = None,
        pa_cutoff: Optional[int] = None,
        ip_cutoff: Optional[int] = None,
        gs_cutoff: Optional[int] = None,
        qualified_at: Optional[str] = None,
        limit: int = 100,
    ) -> str:
        """Search/filter players (level V/A/B, position, owned, stats cutoffs, roster flags)."""
        data = await db_sync(
            services.search_players,
            name=name,
            level=level,
            position=position,
            owned=owned,
            team=team,
            season=season,
            classification=classification,
            carded=carded,
            on_40man=on_40man,
            on_mlb=on_mlb,
            on_aaa=on_aaa,
            trade_block=trade_block,
            pa_cutoff=pa_cutoff,
            ip_cutoff=ip_cutoff,
            gs_cutoff=gs_cutoff,
            qualified_at=qualified_at,
            limit=limit,
        )
        return _dump(data)

    @mcp.tool()
    async def list_draft_picks(
        team: Optional[str] = None,
        year: Optional[str] = None,
        season: Optional[str] = None,
        draft_type: Optional[str] = None,
        original_team: Optional[str] = None,
        limit: int = 500,
    ) -> str:
        """List draft picks. season: offseason|midseason. draft_type: open|aa|balance."""
        data = await db_sync(
            services.list_draft_picks,
            team=team,
            year=year,
            season=season,
            draft_type=draft_type,
            original_team=original_team,
            limit=limit,
        )
        return _dump(data)

    @mcp.tool()
    async def list_trades(
        team: Optional[str] = None,
        season: Optional[int] = None,
        limit: int = 200,
    ) -> str:
        """List trades as structured JSON (players and picks each side received)."""
        data = await db_sync(
            services.list_trades, team=team, season=season, limit=limit
        )
        return _dump(data)

    @mcp.tool()
    async def list_trade_block() -> str:
        """Players currently marked on the league trade block."""
        data = await db_sync(services.list_trade_block)
        return _dump(data)

    @mcp.tool()
    async def list_draft_pool(pool: str = "unprotected") -> str:
        """Draft pools: unprotected | offseason_available | midseason_available."""
        data = await db_sync(services.list_draft_pool, pool=pool)
        return _dump(data)

    @mcp.tool()
    async def get_my_wishlist() -> str:
        """Authenticated owner's full wishlist with tier, rank, notes, and tags."""
        owner = require_current_owner()
        data = await db_sync(services.get_my_wishlist, owner)
        return _dump(data)

    @mcp.tool()
    async def get_draft_board(
        draft_type: str = "open",
        list_type: Optional[str] = None,
    ) -> str:
        """Your draft-prep board: picks, draft order, tiers 1-5, and watched players. draft_type: open|aa. list_type: offseason|midseason."""
        owner = require_current_owner()
        try:
            data = await db_sync(
                wishlist_ops.get_draft_board,
                owner,
                draft_type=draft_type,
                list_type=list_type,
            )
        except WishlistError as exc:
            return _dump(_wishlist_error(exc))
        return _dump(data)

    @mcp.tool()
    async def follow_player(player_id: int) -> str:
        """Follow a player: add them to your wishlist as watched, with no tier. Leaves an existing tier in place. Needs a read-write API key."""
        if not current_token_allows_write():
            return _dump(_READ_ONLY)
        owner = require_current_owner()
        try:
            data = await db_sync(
                wishlist_ops.follow_player, owner, player_id=player_id
            )
        except WishlistError as exc:
            return _dump(_wishlist_error(exc))
        return _dump(data)

    @mcp.tool()
    async def unfollow_player(player_id: int) -> str:
        """Unfollow a player: remove them from your wishlist. Needs a read-write API key."""
        if not current_token_allows_write():
            return _dump(_READ_ONLY)
        owner = require_current_owner()
        try:
            data = await db_sync(
                wishlist_ops.unfollow_player, owner, player_id=player_id
            )
        except WishlistError as exc:
            return _dump(_wishlist_error(exc))
        return _dump(data)

    @mcp.tool()
    async def set_wishlist_tier(
        player_id: int,
        tier: int,
        rank: Optional[int] = None,
    ) -> str:
        """Set a wishlist tier. tier is 1-5 (max 20 players) or 0 for watched. rank is the slot in that tier; omit it to append. Follows the player when needed. Needs a read-write API key."""
        if not current_token_allows_write():
            return _dump(_READ_ONLY)
        owner = require_current_owner()
        try:
            data = await db_sync(
                wishlist_ops.set_wishlist_tier,
                owner,
                player_id=player_id,
                tier=tier,
                rank=rank,
            )
        except WishlistError as exc:
            return _dump(_wishlist_error(exc))
        return _dump(data)

    @mcp.tool()
    async def set_wishlist_note(player_id: int, note: str) -> str:
        """Set the note on a wishlist player. Follows them first when they are not on the list. Needs a read-write API key."""
        if not current_token_allows_write():
            return _dump(_READ_ONLY)
        owner = require_current_owner()
        try:
            data = await db_sync(
                wishlist_ops.set_wishlist_note,
                owner,
                player_id=player_id,
                note=note,
            )
        except WishlistError as exc:
            return _dump(_wishlist_error(exc))
        return _dump(data)

    @mcp.tool()
    async def list_games(
        season: Optional[int] = None,
        team: Optional[str] = None,
        day_from: Optional[int] = None,
        day_to: Optional[int] = None,
        status: str = "final",
        limit: int = 200,
    ) -> str:
        """Sim game scores in day order. status: final|in_progress|scheduled|all. day is the game number, 1-162. Each game's id feeds get_box_score."""
        return await _game_read(
            game_reads.list_games,
            season=season,
            team=team,
            day_from=day_from,
            day_to=day_to,
            status=status,
            limit=limit,
        )

    @mcp.tool()
    async def get_box_score(game_id: int) -> str:
        """One sim game's box score: line score, batting and pitching lines, W/L/S/holds, and notes (2B, HR, SB, LOB...)."""
        return await _game_read(game_reads.get_box_score, game_id=game_id)

    @mcp.tool()
    async def get_standings(season: Optional[int] = None) -> str:
        """Sim standings by conference and division: W-L, pct, games behind, runs scored and allowed, and the wild-card race."""
        return await _game_read(game_reads.get_standings, season=season)

    @mcp.tool()
    async def get_team_season(
        abbreviation: Optional[str] = None,
        season: Optional[int] = None,
    ) -> str:
        """A club's sim season: record, standing, team batting/pitching totals, and every final game. Omitting abbreviation uses your team."""
        owner = get_current_owner()
        return await _game_read(
            game_reads.get_team_season,
            abbreviation=abbreviation,
            season=season,
            owner=owner,
        )

    @mcp.tool()
    async def list_sim_stats(
        season: Optional[int] = None,
        team: Optional[str] = None,
        player_id: Optional[int] = None,
        kind: Optional[str] = None,
        sort: Optional[str] = None,
        order: str = "desc",
        min_pa: Optional[int] = None,
        min_ip: Optional[float] = None,
        limit: int = 100,
    ) -> str:
        """Players' sim (6-ulmg) season lines. kind: batting|pitching. sort is a stat key such as hr, ops, era, so, gs; order: desc|asc."""
        return await _game_read(
            game_reads.list_sim_stats,
            season=season,
            team=team,
            player_id=player_id,
            kind=kind,
            sort=sort,
            order=order,
            min_pa=min_pa,
            min_ip=min_ip,
            limit=limit,
        )

    @mcp.tool()
    async def get_sim_leaders(season: Optional[int] = None, limit: int = 10) -> str:
        """Sim league leaders in hits, homers, RBI, steals, wins, saves, holds, strikeouts, innings, starts and more."""
        return await _game_read(game_reads.get_sim_leaders, season=season, limit=limit)

    @mcp.tool()
    async def get_usage(season: Optional[int] = None, team: Optional[str] = None) -> str:
        """Sim usage against caps: plate appearances, starts and innings per player, with each cap. Omitting team lists the league."""
        return await _game_read(game_reads.get_usage, season=season, team=team)


def _register_remote_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_season_context() -> str:
        """Current ULMG season, half, roster limits, and the authenticated owner's team."""
        return _dump(_http_get("/api/mcp/v1/season/"))

    @mcp.tool()
    def list_teams() -> str:
        """List all ULMG teams."""
        return _dump(_http_get("/api/mcp/v1/teams/"))

    @mcp.tool()
    def get_team_roster(abbreviation: Optional[str] = None) -> str:
        """Full team roster. Omitting abbreviation uses your team."""
        if abbreviation:
            return _dump(_http_get(f"/api/mcp/v1/teams/{abbreviation}/roster/"))
        return _dump(_http_get("/api/mcp/v1/roster/"))

    @mcp.tool()
    def get_roster_compliance(abbreviation: Optional[str] = None) -> str:
        """Counts vs constitutional roster limits."""
        if abbreviation:
            return _dump(
                _http_get(f"/api/mcp/v1/teams/{abbreviation}/compliance/")
            )
        return _dump(_http_get("/api/mcp/v1/compliance/"))

    @mcp.tool()
    def search_players(
        name: Optional[str] = None,
        level: Optional[str] = None,
        position: Optional[str] = None,
        owned: Optional[str] = None,
        team: Optional[str] = None,
        season: Optional[int] = None,
        classification: Optional[str] = None,
        carded: Optional[str] = None,
        on_40man: Optional[str] = None,
        on_mlb: Optional[str] = None,
        on_aaa: Optional[str] = None,
        trade_block: Optional[str] = None,
        pa_cutoff: Optional[int] = None,
        ip_cutoff: Optional[int] = None,
        gs_cutoff: Optional[int] = None,
        qualified_at: Optional[str] = None,
        limit: int = 100,
    ) -> str:
        """Search/filter players."""
        params = {
            k: v
            for k, v in {
                "name": name,
                "level": level,
                "position": position,
                "owned": owned,
                "team": team,
                "season": season,
                "classification": classification,
                "carded": carded,
                "on_40man": on_40man,
                "on_mlb": on_mlb,
                "on_aaa": on_aaa,
                "trade_block": trade_block,
                "pa_cutoff": pa_cutoff,
                "ip_cutoff": ip_cutoff,
                "gs_cutoff": gs_cutoff,
                "qualified_at": qualified_at,
                "limit": limit,
            }.items()
            if v is not None and v != ""
        }
        return _dump(_http_get("/api/mcp/v1/players/search/", params=params))

    @mcp.tool()
    def list_draft_picks(
        team: Optional[str] = None,
        year: Optional[str] = None,
        season: Optional[str] = None,
        draft_type: Optional[str] = None,
        original_team: Optional[str] = None,
        limit: int = 500,
    ) -> str:
        """List draft picks."""
        params = {
            k: v
            for k, v in {
                "team": team,
                "year": year,
                "season": season,
                "draft_type": draft_type,
                "original_team": original_team,
                "limit": limit,
            }.items()
            if v is not None and v != ""
        }
        return _dump(_http_get("/api/mcp/v1/draft-picks/", params=params))

    @mcp.tool()
    def list_trades(
        team: Optional[str] = None,
        season: Optional[int] = None,
        limit: int = 200,
    ) -> str:
        """List trades as structured JSON."""
        params = {
            k: v
            for k, v in {
                "team": team,
                "season": season,
                "limit": limit,
            }.items()
            if v is not None and v != ""
        }
        return _dump(_http_get("/api/mcp/v1/trades/", params=params))

    @mcp.tool()
    def list_trade_block() -> str:
        """Players on the trade block."""
        return _dump(_http_get("/api/mcp/v1/trade-block/"))

    @mcp.tool()
    def list_draft_pool(pool: str = "unprotected") -> str:
        """Draft pools: unprotected | offseason_available | midseason_available."""
        return _dump(_http_get("/api/mcp/v1/draft-pool/", params={"pool": pool}))

    @mcp.tool()
    def get_my_wishlist() -> str:
        """Your full wishlist with tiers and notes."""
        return _dump(_http_get("/api/mcp/v1/wishlist/"))

    @mcp.tool()
    def get_draft_board(
        draft_type: str = "open",
        list_type: Optional[str] = None,
    ) -> str:
        """Your draft-prep board: picks, draft order, tiers 1-5, and watched players."""
        params = {"draft_type": draft_type}
        if list_type:
            params["list_type"] = list_type
        return _dump(_http_get("/api/mcp/v1/draft-board/", params=params))

    @mcp.tool()
    def follow_player(player_id: int) -> str:
        """Follow a player on your wishlist as watched. Needs a read-write API key."""
        return _dump(
            _http_json(
                "POST",
                "/api/mcp/v1/wishlist/follow/",
                body={"player_id": player_id},
            )
        )

    @mcp.tool()
    def unfollow_player(player_id: int) -> str:
        """Remove a player from your wishlist. Needs a read-write API key."""
        return _dump(
            _http_json(
                "POST",
                "/api/mcp/v1/wishlist/unfollow/",
                body={"player_id": player_id},
            )
        )

    @mcp.tool()
    def set_wishlist_tier(
        player_id: int,
        tier: int,
        rank: Optional[int] = None,
    ) -> str:
        """Set a wishlist tier (1-5, or 0 for watched). Needs a read-write API key."""
        body = {"player_id": player_id, "tier": tier}
        if rank is not None:
            body["rank"] = rank
        return _dump(
            _http_json("POST", "/api/mcp/v1/wishlist/tier/", body=body)
        )

    @mcp.tool()
    def set_wishlist_note(player_id: int, note: str) -> str:
        """Set the note on a wishlist player. Needs a read-write API key."""
        return _dump(
            _http_json(
                "POST",
                "/api/mcp/v1/wishlist/note/",
                body={"player_id": player_id, "note": note},
            )
        )

    @mcp.tool()
    def list_games(
        season: Optional[int] = None,
        team: Optional[str] = None,
        day_from: Optional[int] = None,
        day_to: Optional[int] = None,
        status: str = "final",
        limit: int = 200,
    ) -> str:
        """Sim game scores in day order. status: final|in_progress|scheduled|all."""
        params = _params(
            season=season,
            team=team,
            day_from=day_from,
            day_to=day_to,
            status=status,
            limit=limit,
        )
        return _dump(_http_get("/api/mcp/v1/games/", params=params))

    @mcp.tool()
    def get_box_score(game_id: int) -> str:
        """One sim game's box score."""
        return _dump(_http_get(f"/api/mcp/v1/games/{game_id}/box-score/"))

    @mcp.tool()
    def get_standings(season: Optional[int] = None) -> str:
        """Sim standings by conference and division, with the wild-card race."""
        return _dump(
            _http_get("/api/mcp/v1/standings/", params=_params(season=season))
        )

    @mcp.tool()
    def get_team_season(
        abbreviation: Optional[str] = None,
        season: Optional[int] = None,
    ) -> str:
        """A club's sim season. Omitting abbreviation uses your team."""
        params = _params(season=season)
        if abbreviation:
            return _dump(
                _http_get(f"/api/mcp/v1/teams/{abbreviation}/season/", params=params)
            )
        return _dump(_http_get("/api/mcp/v1/team-season/", params=params))

    @mcp.tool()
    def list_sim_stats(
        season: Optional[int] = None,
        team: Optional[str] = None,
        player_id: Optional[int] = None,
        kind: Optional[str] = None,
        sort: Optional[str] = None,
        order: str = "desc",
        min_pa: Optional[int] = None,
        min_ip: Optional[float] = None,
        limit: int = 100,
    ) -> str:
        """Players' sim (6-ulmg) season lines."""
        params = _params(
            season=season,
            team=team,
            player_id=player_id,
            kind=kind,
            sort=sort,
            order=order,
            min_pa=min_pa,
            min_ip=min_ip,
            limit=limit,
        )
        return _dump(_http_get("/api/mcp/v1/sim-stats/", params=params))

    @mcp.tool()
    def get_sim_leaders(season: Optional[int] = None, limit: int = 10) -> str:
        """Sim league leaders in each counting stat."""
        params = _params(season=season, limit=limit)
        return _dump(_http_get("/api/mcp/v1/sim-leaders/", params=params))

    @mcp.tool()
    def get_usage(season: Optional[int] = None, team: Optional[str] = None) -> str:
        """Sim usage against caps per player."""
        params = _params(season=season, team=team)
        return _dump(_http_get("/api/mcp/v1/usage/", params=params))
