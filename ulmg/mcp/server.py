# ABOUTME: Stdio MCP entry point for clients that cannot use remote HTTPS MCP.
# ABOUTME: Proxies to the site's token-auth JSON API via ULMG_API_URL + token.
"""ULMG read-only MCP server (Phase 1) — stdio transport.

Preferred for most owners: connect over HTTPS to https://YOUR-HOST/mcp
with Authorization: Bearer <token> (see documents/MCP.md).

This stdio bridge is for clients that only support local MCP processes.
"""
from __future__ import annotations

import sys
from typing import Optional

from ulmg.mcp.tools import build_mcp


def main(argv: Optional[list] = None) -> None:
    mcp = build_mcp(mode="remote")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main(sys.argv[1:])
