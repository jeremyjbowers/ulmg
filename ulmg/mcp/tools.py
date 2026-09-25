# ABOUTME: FastMCP tool registration shared by HTTP and stdio transports.
# ABOUTME: Local backend uses Django services; remote backend uses the JSON API.
from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx
from asgiref.sync import sync_to_async
from mcp.server.fastmcp import FastMCP

from ulmg.mcp import services
from ulmg.mcp.context import get_current_owner, require_current_owner


INSTRUCTIONS = (
    "Read-only ULMG league tools for roster review, draft prep, and trade "
    "analysis. Roster terms: on_mlb_30man = Major League active roster; "
    "on_40man_protect = Open Draft protected V/A list (site field "
    "is_ulmg_35man_roster). Use get_constitution / search_constitution (or the "
    "ulmg://constitution resource) for league rules. Phase 1 is read-only — "
    "no writes or trade execution."
)


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _http_get(path: str, params: Optional[dict] = None) -> Any:
    base = (os.environ.get("ULMG_API_URL") or "").rstrip("/")
    token = os.environ.get("ULMG_API_TOKEN") or ""
    if not base or not token:
        raise RuntimeError(
            "Stdio mode requires ULMG_API_URL and ULMG_API_TOKEN"
        )
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(f"{base}{path}", params=params or {}, headers=headers)
        if resp.status_code == 401:
            raise RuntimeError("ULMG API token rejected (401)")
        resp.raise_for_status()
        return resp.json()


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
        data = await sync_to_async(services.get_season_context)(owner=owner)
        return _dump(data)

    @mcp.tool()
    async def list_teams() -> str:
        """List all ULMG teams (abbreviation, city, nickname, division)."""
        data = await sync_to_async(services.list_teams)()
        return _dump(data)

    @mcp.tool()
    async def get_team_roster(abbreviation: Optional[str] = None) -> str:
        """Full team roster split into mlb (30-man), aaa, and aa. Omitting abbreviation uses your team."""
        owner = get_current_owner()
        data = await sync_to_async(services.get_team_roster)(
            abbreviation=abbreviation, owner=owner
        )
        return _dump(data)

    @mcp.tool()
    async def get_roster_compliance(abbreviation: Optional[str] = None) -> str:
        """Counts vs constitutional limits (30-man, 40-man protect, 75/76 org, 20 B-floor)."""
        owner = get_current_owner()
        data = await sync_to_async(services.get_roster_compliance)(
            abbreviation=abbreviation, owner=owner
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
        data = await sync_to_async(services.search_players)(
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
        data = await sync_to_async(services.list_draft_picks)(
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
        data = await sync_to_async(services.list_trades)(
            team=team, season=season, limit=limit
        )
        return _dump(data)

    @mcp.tool()
    async def list_trade_block() -> str:
        """Players currently marked on the league trade block."""
        data = await sync_to_async(services.list_trade_block)()
        return _dump(data)

    @mcp.tool()
    async def list_draft_pool(pool: str = "unprotected") -> str:
        """Draft pools: unprotected | offseason_available | midseason_available."""
        data = await sync_to_async(services.list_draft_pool)(pool=pool)
        return _dump(data)

    @mcp.tool()
    async def get_my_wishlist() -> str:
        """Authenticated owner's wishlist with tier, rank, notes, and tags."""
        owner = require_current_owner()
        data = await sync_to_async(services.get_my_wishlist)(owner)
        return _dump(data)

    @mcp.tool()
    async def get_constitution() -> str:
        """Full ULMG constitution text from the server cache (not live-scraped)."""
        data = await sync_to_async(services.get_constitution)()
        return _dump(data)

    @mcp.tool()
    async def search_constitution(
        query: str,
        context_chars: int = 180,
        limit: int = 40,
    ) -> str:
        """Search the cached ULMG constitution; returns excerpts with surrounding context."""
        data = await sync_to_async(services.search_constitution)(
            query, context_chars=context_chars, limit=limit
        )
        return _dump(data)

    @mcp.resource("ulmg://constitution")
    async def constitution_resource() -> str:
        """Cached plain-text ULMG constitution (refresh via django-admin refresh_constitution)."""
        data = await sync_to_async(services.get_constitution)()
        return data["text"]


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
        """Your wishlist with tiers and notes."""
        return _dump(_http_get("/api/mcp/v1/wishlist/"))

    @mcp.tool()
    def get_constitution() -> str:
        """Full ULMG constitution text from the server cache."""
        return _dump(_http_get("/api/mcp/v1/constitution/"))

    @mcp.tool()
    def search_constitution(
        query: str,
        context_chars: int = 180,
        limit: int = 40,
    ) -> str:
        """Search the cached ULMG constitution for excerpts."""
        return _dump(
            _http_get(
                "/api/mcp/v1/constitution/search/",
                params={
                    "q": query,
                    "context_chars": context_chars,
                    "limit": limit,
                },
            )
        )

    @mcp.resource("ulmg://constitution")
    def constitution_resource() -> str:
        """Cached plain-text ULMG constitution."""
        return _http_get("/api/mcp/v1/constitution/")["text"]
