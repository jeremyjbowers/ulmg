# ABOUTME: Per-request owner and API token for in-process MCP tool calls.
# ABOUTME: Set by Bearer auth middleware when serving Streamable HTTP.
from __future__ import annotations

from contextvars import ContextVar

from ulmg.models import Owner, OwnerAPIToken

_current_owner: ContextVar[Owner | None] = ContextVar("ulmg_mcp_owner", default=None)
_current_token: ContextVar[OwnerAPIToken | None] = ContextVar(
    "ulmg_mcp_token", default=None
)


def set_current_owner(owner: Owner | None):
    return _current_owner.set(owner)


def reset_current_owner(token):
    _current_owner.reset(token)


def get_current_owner() -> Owner | None:
    return _current_owner.get()


def require_current_owner() -> Owner:
    owner = get_current_owner()
    if owner is None:
        raise RuntimeError("MCP call is not authenticated to an owner")
    return owner


def set_current_token(token: OwnerAPIToken | None):
    return _current_token.set(token)


def reset_current_token(token):
    _current_token.reset(token)


def get_current_token() -> OwnerAPIToken | None:
    return _current_token.get()


def current_token_allows_write() -> bool:
    token = get_current_token()
    return token is not None and token.allows_write
