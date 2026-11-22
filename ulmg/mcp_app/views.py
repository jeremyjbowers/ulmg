# ABOUTME: Django JSON views for the MCP API.
# ABOUTME: Reads take any OwnerAPIToken. Wishlist writes require a read-write key.
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from ulmg.mcp_app.auth import require_owner_api_token
from ulmg.mcp_app import games as game_reads
from ulmg.mcp_app import services
from ulmg.mcp_app.wishlist import WishlistError
from ulmg.mcp_app import wishlist as wishlist_ops


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


def _json_body(request):
    raw = request.body.decode("utf-8") if request.body else ""
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _wishlist_response(fn, request, extras=None):
    body = _json_body(request)
    if body is None:
        return JsonResponse({"error": "Body must be a JSON object"}, status=400)
    if "player_id" not in body:
        return JsonResponse({"error": "player_id is required"}, status=400)
    try:
        kwargs = extras(body) if extras else {}
        payload = fn(request.mcp_owner, player_id=body.get("player_id"), **kwargs)
    except WishlistError as exc:
        return JsonResponse(
            {"error": exc.message, "status": exc.status}, status=exc.status
        )
    return JsonResponse(payload)


@require_GET
@require_owner_api_token
def draft_board(request):
    try:
        payload = wishlist_ops.get_draft_board(
            request.mcp_owner,
            draft_type=request.GET.get("draft_type", "open"),
            list_type=request.GET.get("list_type"),
        )
    except WishlistError as exc:
        return JsonResponse(
            {"error": exc.message, "status": exc.status}, status=exc.status
        )
    return JsonResponse(payload)


@csrf_exempt
@require_POST
@require_owner_api_token(write=True)
def wishlist_follow(request):
    return _wishlist_response(wishlist_ops.follow_player, request)


@csrf_exempt
@require_POST
@require_owner_api_token(write=True)
def wishlist_unfollow(request):
    return _wishlist_response(wishlist_ops.unfollow_player, request)


@csrf_exempt
@require_POST
@require_owner_api_token(write=True)
def wishlist_tier(request):
    def extra(body):
        if "tier" not in body:
            raise WishlistError(
                "tier is required (1-5, or 0 to move the player to watched)"
            )
        return {"tier": body.get("tier"), "rank": body.get("rank")}

    return _wishlist_response(wishlist_ops.set_wishlist_tier, request, extras=extra)


@csrf_exempt
@require_POST
@require_owner_api_token(write=True)
def wishlist_note(request):
    def extra(body):
        if "note" not in body:
            raise WishlistError("note is required")
        return {"note": body.get("note")}

    return _wishlist_response(wishlist_ops.set_wishlist_note, request, extras=extra)


def _game_read(func, **kwargs):
    """JSON for a game_reads call: 404 for a missing game or team, 400 for a bad argument."""
    try:
        return JsonResponse(func(**kwargs))
    except game_reads.NotFound as exc:
        return JsonResponse({"error": str(exc)}, status=404)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@require_GET
@require_owner_api_token
def games_list(request):
    params = request.GET
    return _game_read(
        game_reads.list_games,
        season=params.get("season"),
        team=params.get("team"),
        day_from=params.get("day_from"),
        day_to=params.get("day_to"),
        status=params.get("status") or game_reads.FINAL,
        limit=params.get("limit") or 200,
    )


@require_GET
@require_owner_api_token
def game_box_score(request, game_id):
    return _game_read(game_reads.get_box_score, game_id=game_id)


@require_GET
@require_owner_api_token
def standings(request):
    return _game_read(game_reads.get_standings, season=request.GET.get("season"))


@require_GET
@require_owner_api_token
def team_season(request, abbreviation):
    return _game_read(
        game_reads.get_team_season,
        abbreviation=abbreviation,
        season=request.GET.get("season"),
    )


@require_GET
@require_owner_api_token
def my_team_season(request):
    return _game_read(
        game_reads.get_team_season,
        season=request.GET.get("season"),
        owner=request.mcp_owner,
    )


@require_GET
@require_owner_api_token
def sim_stats(request):
    params = request.GET
    return _game_read(
        game_reads.list_sim_stats,
        season=params.get("season"),
        team=params.get("team"),
        player_id=params.get("player_id"),
        kind=params.get("kind"),
        sort=params.get("sort"),
        order=params.get("order") or "desc",
        min_pa=params.get("min_pa"),
        min_ip=params.get("min_ip"),
        limit=params.get("limit") or 100,
    )


@require_GET
@require_owner_api_token
def sim_leaders(request):
    return _game_read(
        game_reads.get_sim_leaders,
        season=request.GET.get("season"),
        limit=request.GET.get("limit") or 10,
    )


@require_GET
@require_owner_api_token
def usage(request):
    return _game_read(
        game_reads.get_usage,
        season=request.GET.get("season"),
        team=request.GET.get("team"),
    )
