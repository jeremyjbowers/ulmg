# ABOUTME: Per-request owner context for in-process MCP tool calls.
# ABOUTME: Set by Bearer auth middleware when serving Streamable HTTP.
from __future__ import annotations

from contextvars import ContextVar

from ulmg.models import Owner

_current_owner: ContextVar[Owner | None] = ContextVar("ulmg_mcp_owner", default=None)


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
