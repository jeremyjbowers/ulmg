ULMG: Strat-O-Matic League Manager for Django

ULMG is a Django application for running a Strat-O-Matic style dynasty league. It models teams, players, drafts, trades, and season-by-season statistics across MLB, MiLB, and international/amateur leagues. This README focuses on the core concepts a Django-savvy developer needs to understand how the app loads data, processes it, and represents it in the UI.

## Core concepts

- **League model in brief**: Teams manage rosters across three tiers (Major League, AAA, AA) with league-specific rules for protections, drafts, and transactions. The league constitution provides the authoritative rules; ULMG enforces and visualizes them.
- **Player levels (V/A/B)**: A `Player` carries a level indicating veteran status or prospect tier. Protection and draft eligibility key off these.
- **Seasons and classification**: Season-by-season stats live in `PlayerStatSeason`, keyed by `(player, season, classification)` where classification is one of `"1-mlb"`, `"2-milb"`, `"3-npb"`, `"4-kbo"`, `"5-college"`.
- **Carded (Strat-O-Matic)**: If a player has MLB appearances in a season, their `PlayerStatSeason.carded` is set true for that year. `Player.is_carded()` reads the current season's status.
- **Defense (Strat-O-Matic)**: `Player.defense` stores the player's Strat defensive ratings; `defense_display()` formats them for templates.
- **Ownership and rosters**: Long-lived ownership lives on `Player` (`team`, `is_owned`). Season-specific roster/role flags (IL, MLB/AAA assignment, role type) live on `PlayerStatSeason`.

These choices keep long-lived identity on `Player` and isolate seasonal, league-classified data on `PlayerStatSeason` for performance and clarity.

## Data model (how we represent the league)

- `ulmg/models.py`
  - `Player`: canonical person; level (V/A/B), position, crosswalk IDs (MLBAM, FanGraphs, BRef, etc.), ownership (`team`, `is_owned`), defense ratings, and derived helpers like `is_carded()`.
  - `PlayerStatSeason`: season- and classification-scoped stats and status. Fields include `hit_stats` and `pitch_stats` (JSON), `carded`, `owned`, roster/role flags (IL, MLB/AAA assignment, role type, `mlb_org`). Unique on `(player, season, classification)` and heavily indexed for common queries.
  - `Team`: owner/identity plus "live" rollups used in dashboards.
  - `DraftPick`: supports AA/Open drafts across offseason/midseason, with helpers to maintain slugs and overall pick numbers; saving a pick updates a player's team when appropriate.
  - `Trade` and `TradeReceipt`: multi-team trades of players and picks, with cached summaries for rendering.

Key invariants:
- Long-lived ownership stays on `Player`; anything that varies by season lives on `PlayerStatSeason`.
- We only create an MLB `PlayerStatSeason` when the player actually appears (PA > 0 for hitters; IP > 0 or G > 0 for pitchers). This prevents phantom MLB rows.

## Data pipeline (how data gets in)

Primary sources
- FanGraphs JSON endpoints for MLB, MiLB, NPB, KBO, and NCAA.
- MLB StatsAPI for current-season stats by MLBAM ID.

Storage and distribution
- Local files under `data/<season>/fg_*.json`.
- Optional S3-compatible cache (DigitalOcean Spaces) managed by `ulmg.utils.S3DataManager`, with local-first reads and best-effort uploads.

Commands (happy path)
- Download FanGraphs data (local-only or local+S3):
  - `python manage.py live_download_fg_stats [--local-only]`
- Ingest FanGraphs data into `PlayerStatSeason` (reads local or S3-hosted FG files):
  - `python manage.py live_update_stats_from_fg_stats`
- Load MLB StatsAPI for players with `mlbam_id`:
  - `python manage.py load_mlb_stats --season 2025`
- Clean up duplicates if any import scripts evolve:
  - `python manage.py deduplicate_playerstatseason`

What the import does
- Matches FG/MLB rows to existing `Player` via `fg_id` or `mlbam_id` (we do not create new players from FG rows; they can be incomplete). If matched, we create/update a `PlayerStatSeason` for `(season, classification)` and attach `hit_stats`/`pitch_stats` JSON.
- For MLB rows, `carded=True` is set when there are appearances. Carded status and roster flags are consumed by team and draft views.

Where to look in code
- `ulmg/management/commands/` for import/update scripts.
- `ulmg/utils.py` for S3 handling, stat thresholds, and helper functions.
- `ulmg/constants.py` for stat field name mappings and thresholds.

## Quickstart (development)

Prereqs
- Python 3.8+ 
- PostgreSQL 12+
- Optional: S3-compatible credentials (DigitalOcean Spaces)

Setup
```bash
git clone https://github.com/jeremyjbowers/ulmg.git
cd ulmg
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r new.requirements.txt

export DJANGO_SETTINGS_MODULE=config.dev.settings
createdb ulmg_dev
python manage.py migrate
python manage.py createsuperuser
```

S3 (optional)
```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_S3_ENDPOINT_URL=https://nyc3.digitaloceanspaces.com
export AWS_STORAGE_BUCKET_NAME=your-bucket
```
See `S3_DATA_SETUP.md` for details.

Load data and run
```bash
python manage.py live_download_fg_stats --local-only
python manage.py live_update_stats_from_fg_stats
python manage.py runserver
```

## Common commands

Data
```bash
python manage.py live_download_fg_stats [--local-only]
python manage.py live_update_stats_from_fg_stats
python manage.py load_mlb_stats --season 2025
python manage.py deduplicate_playerstatseason
```

League ops
```bash
python manage.py draft_generate_picks --year 2025 --season midseason --draft-type open
python manage.py post_offseason_draft
python manage.py offseason
python manage.py midseason
```

Maintenance
```bash
python manage.py analyze_lineups
python manage.py reset_stats --season 2025
python manage.py check
```

## Configuration

Env vars
- `DJANGO_SETTINGS_MODULE` (e.g., `config.dev.settings`)
- `DATABASE_URL` (or equivalent per your setup)
- `SECRET_KEY`, `DEBUG`
- Optional S3: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT_URL`, `AWS_STORAGE_BUCKET_NAME`

Settings modules
- `config/dev/settings.py`
- `config/prd/settings.py`
- `config/do_app_platform/settings.py`

## Testing
```bash
python manage.py test
python manage.py test tests.test_utils
```

## Operations notes

Data integrity
- `PlayerStatSeason` is unique per `(player, season, classification)`; use `deduplicate_playerstatseason` after import changes.
- Extensive indexes exist on `Player` and `PlayerStatSeason` for common filters (season, owned, minors, classification).

Backups
- DB backups via standard PostgreSQL dump/restore.
- FG input files are stored under `data/` and optionally mirrored to S3 for reproducibility.

## Deployment

Requirements
- PostgreSQL
- Optional S3-compatible storage for FG data caching

DigitalOcean App Platform
- See `config/do_app_platform/` for app settings. A typical command is:
  - `gunicorn --worker-tmp-dir /dev/shm config.do_app_platform.asgi:application -k uvicorn.workers.UvicornWorker`

## Code organization

- `ulmg/models.py`: `Player`, `PlayerStatSeason`, `Team`, `DraftPick`, `Trade`, etc.
- `ulmg/management/commands/`: import/update scripts and league ops.
- `ulmg/views/`: site and API views by area.
- `ulmg/templates/`: pages and components.
- `ulmg/utils.py`: S3 data manager and helper functions.
- `ulmg/constants.py`: stat field mapping and thresholds.

## Glossary

- V/A/B: Player level used for protections and eligibility.
- Carded: Eligible for a Strat card this season (derived from MLB appearances in `PlayerStatSeason`).
- Classification: One of `1-mlb`, `2-milb`, `3-npb`, `4-kbo`, `5-college` on `PlayerStatSeason`.
- Owned: `Player.is_owned` derived from `team` assignment.

Refer to the league constitution for official rules; this application enforces and exposes those rules in draft, roster, and report views.