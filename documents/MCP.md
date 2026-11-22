# ABOUTME: Owner guide for connecting any MCP client to ULMG over HTTPS.
# ABOUTME: Primary path is URL + Bearer token; stdio bridge is optional fallback.

# ULMG MCP

Agents look up rosters, draft history, trades, draft pools, and wishlists for you.
A read-write key can also follow and unfollow players and set wishlist tiers and notes.
**No roster writes or trade execution.**

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

# Draft prep (follow, unfollow, tiers, notes) needs a read-write key.
django-admin create_owner_api_token --email OWNER@EMAIL --label "draft agent" --scope read_write
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

## Tools

Read tools work with any key. The wishlist write tools need `--scope read_write`
(or a read-write key from `/my/api-keys/`). A read-only key is refused.

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
| `get_my_wishlist` | Your full wishlist: tiers, ranks, notes |
| `get_draft_board` | Your prep board for `open` or `aa`: your picks, the order, tiers, watched |
| `follow_player` | **Write.** Add a player to your wishlist as watched |
| `unfollow_player` | **Write.** Remove a player from your wishlist |
| `set_wishlist_tier` | **Write.** Tier 1–5 (20 players max) or `0` for watched. Optional `rank` |
| `set_wishlist_note` | **Write.** Set the note. Follows the player if you have not yet |
| `list_games` | Sim scores in day order. `status` is `final` (default), `in_progress`, `scheduled` or `all`; filter by `team`, `day_from`, `day_to` |
| `get_box_score` | One game's box score: line score, batting and pitching lines, W/L/S/holds, notes |
| `get_standings` | Sim standings by division with games behind, runs scored and allowed, and the wild-card race |
| `get_team_season` | A club's record, standing, team totals and every final. Omit `abbreviation` for your team |
| `list_sim_stats` | Players' 6-ulmg sim lines. `kind` is `batting` or `pitching`; `sort` any stat key, `order` `desc` or `asc`; `min_pa`, `min_ip` |
| `get_sim_leaders` | Leaders in each counting stat the leaders page shows |
| `get_usage` | PA, starts and innings against each player's caps, for the league or one `team` |

`get_draft_board` uses the same eligibility as the draft-prep pages. AA is unowned
B-level players. Offseason Open is unowned V and A. Midseason Open is unowned
players with a card from the prior season. Pass `list_type` of `offseason` or
`midseason` when you want the other board. Players the site's + button followed
land in tier 6, which this board shows under watched, same as a tier of `0`.

The JSON twin of the write tools is `POST /api/mcp/v1/wishlist/follow/`,
`/unfollow/`, `/tier/`, and `/note/` with a JSON body (`player_id`, and `tier`
/ `rank` / `note` when that call needs them). The board is
`GET /api/mcp/v1/draft-board/?draft_type=open`.

The sim-result tools read the same stored record as the standings, results,
leaders and usage pages. Their `season` defaults to the league season, which
turns over on November 1, so pass `season` to read the year before. The JSON
twins are `GET /api/mcp/v1/games/`, `/games/<id>/box-score/`, `/standings/`,
`/team-season/` (your team) or `/teams/<abbr>/season/`, `/sim-stats/`,
`/sim-leaders/` and `/usage/`, with the same arguments as query parameters.

Every player object includes a `stats` block when a `PlayerStatSeason` exists:

- `war`, `position_display`, `defense`, `fg_positions`
- `hit` — PA, AVG/OBP/SLG, HR, SB, K%/BB%, wRC+, WAR, **xAVG / xwOBA / xSLG**, …
- `pitch` — IP, ERA, WHIP, K/9, BB/9, FIP, **xFIP / SIERA**, WAR, …
- `xstats` — expected-stat fields collected in one place
- `hit_stats_raw` / `pitch_stats_raw` — full FanGraphs JSON if agents need anything else

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
