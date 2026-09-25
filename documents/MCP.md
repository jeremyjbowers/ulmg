# ABOUTME: Owner guide for connecting any MCP client to ULMG over HTTPS.
# ABOUTME: Primary path is URL + Bearer token; stdio bridge is optional fallback.

# ULMG MCP (Phase 1 — read-only)

Agents look up rosters, draft history, trades, draft pools, and wishlists for you.
**No roster writes or trade execution in Phase 1.**

Works with Claude Desktop / Cowork, OpenAI Codex, GitHub Copilot, Cursor, Windsurf,
and any other client that speaks MCP.

## How it works (HTTPS + API key)

Same idea as a normal web API behind SSL:

1. The ULMG website serves MCP at **`https://YOUR-HOST/mcp`** (Streamable HTTP).
2. You authenticate with a long-lived **owner API token** in the
   `Authorization: Bearer ulmg_…` header.
3. Your AI client stores the URL + token once; no magic-link cookies, no OAuth dance.

There is also a JSON REST twin under `/api/mcp/v1/…` (same Bearer auth) if you want
to curl or script against the data without MCP.

## Admin: mint a token

```bash
export DJANGO_SETTINGS_MODULE=config.do_app_platform.settings  # or your prod settings
django-admin create_owner_api_token --list-owners
django-admin create_owner_api_token --email OWNER@EMAIL --label "claude cowork"
```

Copy the `ulmg_…` value and send it privately (1Password / Signal). Revoke anytime in
Django Admin → **Owner API tokens**.

## Owner setup (preferred — remote HTTPS)

In your MCP client config:

```json
{
  "mcpServers": {
    "ulmg": {
      "url": "https://YOUR-ULMG-HOST/mcp",
      "headers": {
        "Authorization": "Bearer ulmg_YOUR_TOKEN_HERE"
      }
    }
  }
}
```

That’s it. No local install required for most clients.

| Client | Where config usually lives |
|--------|----------------------------|
| Claude Desktop / Cowork | Settings → Developer / MCP connectors |
| OpenAI Codex | Codex MCP remote server settings |
| GitHub Copilot | IDE Copilot MCP / agent tools |
| Cursor | Settings → MCP → `mcp.json` |

Exact menus move; look for **remote MCP URL** + **headers** / Authorization.

### Sanity check

```bash
curl -s -H "Authorization: Bearer ulmg_YOUR_TOKEN" \
  https://YOUR-ULMG-HOST/mcp/health | python -m json.tool

curl -s -H "Authorization: Bearer ulmg_YOUR_TOKEN" \
  https://YOUR-ULMG-HOST/api/mcp/v1/season/ | python -m json.tool
```

## Optional: stdio bridge

Only needed if a client cannot do remote HTTPS MCP. Runs a tiny local process that
calls the same JSON API:

```json
{
  "mcpServers": {
    "ulmg": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ulmg", "ulmg-mcp"],
      "env": {
        "ULMG_API_URL": "https://YOUR-ULMG-HOST",
        "ULMG_API_TOKEN": "ulmg_YOUR_TOKEN_HERE"
      }
    }
  }
}
```

## Tools (Phase 1)

| Tool | Purpose |
|------|---------|
| `get_season_context` | Season, half, caps, your team |
| `list_teams` | All teams |
| `get_team_roster` | MLB / AAA / AA split + flags |
| `get_roster_compliance` | 30-man, 40-man protect, 75/76, 20 B-floor |
| `search_players` | Filter (level, pos, owned, stats…) |
| `list_draft_picks` | Picks by year / season / type |
| `list_trades` | Structured trade history |
| `list_trade_block` | Trade block |
| `list_draft_pool` | Unprotected / available pools |
| `get_my_wishlist` | Your tiers, ranks, notes |

Naming for agents:

- `on_mlb_30man` — Major League active roster
- `on_40man_protect` — Open Draft protection list (`is_ulmg_35man_roster` in the DB)

## Deploy note (commissioner)

`/mcp` is ASGI (uvicorn). The JSON API under `/api/mcp/v1/` also works on plain WSGI,
but remote MCP clients need the ASGI app:

```bash
uvicorn config.do_app_platform.asgi:application --host 0.0.0.0 --port 8080
```

Point DigitalOcean App Platform (or your reverse proxy) at that ASGI entry so
`https://YOUR-HOST/mcp` hits the composed Django + MCP application.
