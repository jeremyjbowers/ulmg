# ABOUTME: Token auth helpers for the ULMG MCP JSON API.
# ABOUTME: Extracts Bearer tokens and attaches the OwnerAPIToken to the request.
from functools import wraps

from django.http import JsonResponse

from ulmg import models


def extract_bearer_token(request):
    """Return raw token from Authorization: Bearer ... or X-ULMG-Token."""
    auth = request.META.get("HTTP_AUTHORIZATION", "") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    header = request.META.get("HTTP_X_ULMG_TOKEN", "") or ""
    return header.strip() or None


def require_owner_api_token(view_func):
    """Decorator: require a valid OwnerAPIToken; set request.mcp_token / mcp_owner."""

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        raw = extract_bearer_token(request)
        token = models.OwnerAPIToken.authenticate(raw)
        if token is None:
            return JsonResponse(
                {"error": "Unauthorized", "detail": "Valid ULMG API token required"},
                status=401,
            )
        request.mcp_token = token
        request.mcp_owner = token.owner
        request.mcp_team = token.owner.team()
        return view_func(request, *args, **kwargs)

    return wrapper
