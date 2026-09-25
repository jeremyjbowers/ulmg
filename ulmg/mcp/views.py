# ABOUTME: Django JSON views for the Phase 1 read-only MCP API.
# ABOUTME: All endpoints require an OwnerAPIToken Bearer credential.
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from ulmg.mcp.auth import require_owner_api_token
from ulmg.mcp import services


@require_GET
@require_owner_api_token
def season_context(request):
    return JsonResponse(services.get_season_context(owner=request.mcp_owner))


@require_GET
@require_owner_api_token
def teams_list(request):
    return JsonResponse(services.list_teams())


@require_GET
@require_owner_api_token
def my_roster(request):
    try:
        return JsonResponse(
            services.get_team_roster(owner=request.mcp_owner)
        )
    except Exception:
        return JsonResponse(
            {"error": "No team linked to this owner"}, status=404
        )


@require_GET
@require_owner_api_token
def team_roster(request, abbreviation):
    return JsonResponse(
        services.get_team_roster(
            abbreviation=abbreviation, owner=request.mcp_owner
        )
    )


@require_GET
@require_owner_api_token
def team_compliance(request, abbreviation):
    return JsonResponse(
        services.get_roster_compliance(
            abbreviation=abbreviation, owner=request.mcp_owner
        )
    )


@require_GET
@require_owner_api_token
def my_compliance(request):
    try:
        return JsonResponse(
            services.get_roster_compliance(owner=request.mcp_owner)
        )
    except Exception:
        return JsonResponse(
            {"error": "No team linked to this owner"}, status=404
        )


@require_GET
@require_owner_api_token
def players_search(request):
    params = request.GET
    return JsonResponse(
        services.search_players(
            season=params.get("season"),
            level=params.get("level"),
            position=params.get("position"),
            owned=params.get("owned"),
            classification=params.get("classification"),
            carded=params.get("carded"),
            name=params.get("name"),
            team=params.get("team"),
            on_40man=params.get("on_40man"),
            on_mlb=params.get("on_mlb"),
            on_aaa=params.get("on_aaa"),
            trade_block=params.get("trade_block"),
            pa_cutoff=params.get("pa_cutoff"),
            ip_cutoff=params.get("ip_cutoff"),
            gs_cutoff=params.get("gs_cutoff"),
            qualified_at=params.get("qualified_at"),
            limit=params.get("limit", 100),
        )
    )


@require_GET
@require_owner_api_token
def draft_picks(request):
    params = request.GET
    return JsonResponse(
        services.list_draft_picks(
            team=params.get("team"),
            year=params.get("year"),
            season=params.get("season"),
            draft_type=params.get("draft_type"),
            original_team=params.get("original_team"),
            limit=params.get("limit", 500),
        )
    )


@require_GET
@require_owner_api_token
def trades_list(request):
    params = request.GET
    return JsonResponse(
        services.list_trades(
            team=params.get("team"),
            season=params.get("season"),
            limit=params.get("limit", 200),
        )
    )


@require_GET
@require_owner_api_token
def trade_block(request):
    return JsonResponse(services.list_trade_block())


@require_GET
@require_owner_api_token
def draft_pool(request):
    return JsonResponse(
        services.list_draft_pool(pool=request.GET.get("pool", "unprotected"))
    )


@require_GET
@require_owner_api_token
def my_wishlist(request):
    return JsonResponse(services.get_my_wishlist(request.mcp_owner))
