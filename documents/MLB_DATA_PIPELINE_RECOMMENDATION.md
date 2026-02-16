# MLB Data Pipeline Recommendation

## Current State (Archived)

### (A) Scripts that hit MLB APIs

| Command | API / Source | What it does |
|---------|--------------|--------------|
| `archive_mlb_live_download_depthcharts` | `statsapi.mlb.com/api/v1/teams/`, `roster/40Man` | Fetches 40-man rosters for MLB + MiLB teams. Updates existing players in DB. Writes untracked players to `untracked_players.json`. Does **not** write `all_mlb_rosters.json`. |
| `archive_mlb_load_stats` | `python-mlb-statsapi` (Stats API) | Fetches hitting/pitching stats for players with `mlbam_id`. Populates `PlayerStatSeason`. |
| `archive_mlb_scrape_data` | `player.mlb_api_url` (per-player) | Fetches birthdate, position, `mlb_org` for players missing those fields. |
| `archive_mlb_load_prospects_draft` | `mlb.com/milb/prospects/draft/` (scrape) | Scrapes draft prospects, writes `data/2025/mlb_draft_prospects.json`, creates/updates players. |
| `old/load_mlb` | `statsapi.mlb.com/api/v1/people/search` | Finds `mlbam_id` for players without one. |
| `load_mlb_rosters` | `statsapi.mlb.com/api/v1/teams/`, `roster/40Man` | **RESTORED** – Fetches rosters for MLB + MiLB (AAA, AA, High-A, A, Short-A, Rookie including FCL, AZL, DSL). Writes `all_mlb_rosters.json`. |
| `old/load_mlb_rosters` | mlb.com depth chart, milb.com | Legacy skeleton; methods never implemented. |

### (B) Scripts that load MLB data from files

| Command | File | Issue |
|---------|------|-------|
| `archive_mlb_update_status_from_depthcharts` | `all_mlb_rosters.json` | File produced by `load_mlb_rosters`. |
| `archive_mlb_load_players_from_depthcharts` | `all_mlb_rosters.json` | Same; stub that does nothing. |

### Gaps

1. **`all_mlb_rosters.json`** – Produced by `load_mlb_rosters`. Read by `live_update_status_from_mlb_depthcharts` and `load_players_from_mlb_depthcharts`.
2. **FG roster coverage** – FanGraphs rosters may omit some players (e.g., recent call-ups, international signings).
3. **Split responsibilities** – Download vs. load are separate; no single pipeline that both fetches and ingests MLB data.
4. **Untracked players** – `untracked_players.json` is written but not used to create players in the main flow; `evaluate_untracked_players` is a separate manual step.

---

## Recommendation

### (A) How to pull down data from MLB

**1. Use MLB Stats API as the primary source**

- Base URL: `https://statsapi.mlb.com/api/v1/`
- No auth required for public endpoints.
- Prefer Stats API over scraping mlb.com.

**2. Single download command: `live_download_mlb_rosters`**

Responsibilities:

- Fetch 40-man rosters for all MLB orgs (MLB + MiLB affiliates).
- Build a unified roster list (equivalent of the old `all_mlb_rosters.json`).
- Write to `data/rosters/all_mlb_rosters.json` (and optionally S3).
- Use the same structure as `archive_mlb_live_download_depthcharts` (e.g. `mlbam_id`, `name`, `position`, `mlb_org`, `roster_status`).

**3. Endpoints to use**

- `GET /teams/` – team list.
- `GET /teams/{id}/roster/40Man` – 40-man roster per team.
- Optionally `GET /people/{id}` for birthdate/position when missing.

**4. Stats loading**

- Keep `load_mlb_stats` (or equivalent) for stats.
- Use `python-mlb-statsapi` or direct `statsapi.mlb.com` calls.
- Run after roster/player creation so all relevant players have `mlbam_id`.

---

### (B) How to update existing players and create new ones

**1. One pipeline: download → ingest**

```
live_download_mlb_rosters   →  writes all_mlb_rosters.json
live_update_status_from_mlb_rosters  →  reads all_mlb_rosters.json, updates/creates players
```

**2. Ingest logic (update or create)**

For each row in `all_mlb_rosters.json`:

1. **Lookup** by `mlbam_id`.
2. **If found**  
   - Update: `name`, `position`, `current_mlb_org`, birthdate (if missing).  
   - Update or create `PlayerStatSeason` with `roster_status`, `mlb_org`.
3. **If not found**  
   - Create player when `mlbam_id` and `name` are present (same rules as current `live_update_status_from_mlb_depthcharts`).  
   - Set `level='B'` for new players.

**3. Order of operations**

1. FG rosters (create/update from FG IDs).
2. MLB rosters (create/update from MLB IDs; fills gaps FG may miss).
3. Crosswalk (FG ↔ MLB IDs).
4. Stats (FG stats, then MLB stats for current season).

**4. Merge with `live_update`**

- `live_download_mlb_rosters` – download.
- `live_update_status_from_mlb_rosters` – ingest (replacing the old depthcharts-based command).
- Remove dependency on `all_mlb_rosters.json` being produced elsewhere; the download command produces it.

---

## Implementation Checklist

- [ ] Refactor `live_download_mlb_depthcharts` (or `archive_mlb_live_download_depthcharts`) into `live_download_mlb_rosters` that:
  - Fetches all 40-man rosters.
  - Aggregates into one list.
  - Writes `data/rosters/all_mlb_rosters.json`.
  - Optionally keeps `untracked_players.json` for reporting.
- [ ] Refactor `live_update_status_from_mlb_depthcharts` into `live_update_status_from_mlb_rosters` that:
  - Reads `all_mlb_rosters.json`.
  - Updates existing players.
  - Creates new players when `mlbam_id` + `name` exist.
- [ ] Update `live_update` to call the new commands.
- [ ] Keep `load_mlb_stats` as-is for stats (uses python-mlb-statsapi); ensure it runs after roster ingest.
- [ ] Integrate `evaluate_untracked_players` or fold its logic into the main pipeline so untracked players are created automatically when appropriate.
