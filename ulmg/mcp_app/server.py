# ABOUTME: Stdio MCP entry point for clients that cannot use remote HTTPS MCP.
# ABOUTME: Proxies to the site's token-auth JSON API via ULMG_API_URL + token.
"""ULMG MCP server — stdio transport.

Preferred for most owners: connect over HTTPS to https://YOUR-HOST/mcp
with Authorization: Bearer <token> (see documents/MCP.md).

This stdio bridge is for clients that only support local MCP processes.
Wishlist writes need a read-write token. Roster and trade changes stay off.
"""
from __future__ import annotations

import sys
from typing import Optional

from ulmg.mcp_app.tools import build_mcp


def main(argv: Optional[list] = None) -> None:
    mcp = build_mcp(mode="remote")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main(sys.argv[1:])
