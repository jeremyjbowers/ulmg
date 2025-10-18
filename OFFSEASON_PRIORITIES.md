## Offseason priorities (2025–26)

This document captures technical to-dos for four major epics. Each epic includes concrete tasks, expected outcomes, and decision points. Checklists are intentionally detailed to enable parallel work across contributors.

### Epic 1: Better player data and metadata ETL from MLB sources

Goals
- **Create new players automatically** when encountered in upstream sources.
- **Progressively enrich existing players** with authoritative IDs and metadata (names, DOB, handedness, positions, heights/weights, debuts, team history, country, college, draft info, etc.).
- **Unify ID mapping** across MLBAM, Baseball-Reference, FanGraphs, Savant/Statcast, Retrosheet/Chadwick, and internal IDs.

Scope and constraints
- **Source priority**: Savant/Statcast, MLB API (statsapi), FanGraphs, BRef, Retrosheet/Chadwick Register.
- **Data residence**: durable raw snapshots in `data/` (committed for small files) and optionally S3 for larger archives; normalized models in the DB.
- **Batch + incremental**: nightly backfills + event-driven enrichment when new players appear.

Design/implementation to-dos
- [ ] Inventory current loaders and models
  - [ ] Catalog existing loaders in `ulmg/management/` and any ad hoc scripts in `bin/` and `data/`.
  - [ ] Document current `Player`-like models in `ulmg/models.py` and related migration history.
- [ ] Schema upgrades (IDs + metadata)
  - [ ] Add canonical ID fields (e.g., `mlbam_id`, `fg_id`, `bbref_id`, `retrosheet_id`, `savant_id`).
  - [ ] Add stable slug/`canonical_key` for deterministic merges across sources.
  - [ ] Add metadata fields: `full_name`, `first_name`, `last_name`, `dob`, `bats`, `throws`, `primary_pos`, `height_cm`, `weight_kg`, `debut_date`, `country`, `college`, `draft_overall`.
  - [ ] Add unique constraints + indexes on external IDs and `(last_name, first_name, dob)` for fuzzy resolution.
  - [ ] Create `PlayerIdMap` table if we keep IDs decoupled from core player entity; add FK to player.
  - [ ] Migrations with safe backfill and data validation.
- [ ] ID resolution and deduplication
  - [ ] Build deterministic resolution strategy: prefer MLBAM → Savant → FanGraphs → BRef → Retrosheet.
  - [ ] Implement fuzzy matcher for name + DOB conflicts; log manual review queue.
  - [ ] Create merge tool to combine duplicate players, reassign FKs, and preserve history.
- [ ] Ingestion connectors
  - [ ] Savant/Statcast people endpoint (biographical + IDs).
  - [ ] MLB statsapi people and roster endpoints.
  - [ ] FanGraphs player directory/ID map; scrape or CSV where available.
  - [ ] BRef/Chadwick register imports.
  - [ ] Respect upstream rate limits; implement backoff and caching.
- [ ] Raw data handling
  - [ ] Define raw snapshot layout under `data/{year}/` and optionally S3 (`s3://ulmg/raw/{source}/{date}/`).
  - [ ] Persist fetch responses to disk/S3 with stable filenames and a manifest.
  - [ ] Create integrity checksums and schema version tags for snapshots.
- [ ] Normalization pipeline
  - [ ] Transform raw payloads into normalized records; unify enumerations (positions, handedness).
  - [ ] Upsert logic: create new players; enrich existing players without clobbering higher-priority fields.
  - [ ] Track provenance per field (which source wrote it, when, priority tier).
- [ ] Operationalization
  - [ ] `manage.py` commands under `ulmg/management/commands/` (e.g., `etl_players_fetch`, `etl_players_normalize`, `etl_players_reconcile`).
  - [ ] Add `bin/` shell wrappers for local runs and cron; make idempotent.
  - [ ] Add scheduled jobs (nightly) and on-demand triggers.
  - [ ] Observability: structured logging, metrics (counts of creates/updates/conflicts), and error DLQ.
- [ ] Tests and QA
  - [ ] Unit tests for each connector, normalizer, and resolver.
  - [ ] Property tests for idempotency and determinism.
  - [ ] Golden-sample fixtures to lock formats.
  - [ ] Dry-run mode that reports intended changes without writing.

Decision points
- **Single table vs mapping table** for external IDs.
- **Priority policy** when sources disagree.
- **S3 usage** for large raw archives vs keeping snapshots locally in `data/`.

Milestones
- **M1**: Schema + migrations merged; ID resolution library ready.
- **M2**: Savant and MLB connectors live; nightly job populates IDs/metadata.
- **M3**: FanGraphs + BRef enrichment; duplicate merge tool shipped.
- **M4**: Alerts + dashboards; >99% players enriched with MLBAM + FG IDs.

### Epic 2: Mobile web experience (responsive + PWA-only)

Goals
- **Excellent mobile web UX** on phones; no native app, no thin shells.
- **Focus pages**: homepage, search/filter, team pages, player pages.
- **Readable tables on small screens** with horizontal scroll or stacked cards.
- **Passive experience on mobile**: hide drops/protections and admin flows; reading/browsing first.

Design/implementation to-dos
- [ ] Audit current templates and CSS
  - [ ] Verify `<meta name="viewport">` (present in `base.html`).
  - [ ] Inventory homepage `index.html`, `search.html`, `team.html`, `player_detail.html` for mobile pain points.
- [ ] Responsive tables (per page strategy)
  - [ ] Wrap tables in `.overflow-x-auto` containers; enable inertial horizontal scroll on mobile.
  - [ ] Sticky header row and sticky first column on XS/SM where helpful.
  - [ ] Column-priority collapse on XS/SM; show only key stats; reveal more on MD+.
  - [ ] Optional stacked cards on XS for extremely wide tables (defer if scroll works well).
- [ ] Mobile-only visibility rules (passive UX)
  - [ ] Hide drops/protections, bulk actions, and admin utilities on XS/SM.
  - [ ] Keep read-only badges/state; no destructive actions on mobile.
  - [ ] Defer interactive draft tooling; optional future "watch" star only after passive baseline.
- [ ] Mobile navigation & search
  - [ ] Ensure nav wraps cleanly; increase tap targets; search input full-width on XS.
  - [ ] Add jump links within long lists (by position/section) and back-to-top shortcuts.
- [ ] PWA foundation
  - [ ] Add/verify `manifest.webmanifest` (name, icons, theme, display=standalone).
  - [ ] Add service worker for offline shell and asset caching.
  - [ ] Cache strategies for static assets/icons; consider prefetch for top pages.
- [ ] Frontend stack upgrades (as needed)
  - [ ] Lightweight responsive table utilities; ARIA roles and keyboard nav.
  - [ ] Form controls tuned for mobile inputs (where applicable).
- [ ] Analytics and QoS
  - [ ] Measure mobile CWV (LCP/CLS/INP); image/asset budgets.
  - [ ] Error tracking for client-side JS; feature flags to iterate safely.
- [ ] Tests and QA
  - [ ] Visual snapshots for key mobile breakpoints.
  - [ ] Manual device runs for homepage, search/filter, team, player pages.

Decision points
- **Per-page table approach**: horizontal scroll vs stacked cards on XS.
- **Which actions (if any) allowed on mobile** once passive baseline is solid (e.g., "watch").

Milestones
- **M1**: Passive baseline on homepage + search/filter: readable, scrollable tables.
- **M2**: Team and player pages mobile-optimized; actions hidden on XS/SM.
- **M3**: PWA manifest + service worker; A2HS viable; mobile CWV targets met.
- **M4**: Optional "watch" star evaluation; keep destructive/admin flows desktop-only.

### Epic 3: AI integration (trades, roster evaluations, draft prep)

Goals
- **Decision support** for trades, roster optimization, and draft strategy using league context and historical performance.
- **Transparent rationale** and traceable data sources; no hallucinations for facts.

Architecture
- **Retrieval-first**: deterministic data fetch from our DB first; LLM only for synthesis.
- **Guardrails**: schema-constrained outputs, disclaimers, and reproducibility of advice.

Design/implementation to-dos
- [ ] Data access layer
  - [ ] Build read models that assemble player projections, contracts, league settings, team needs.
  - [ ] Normalize value metrics (e.g., WAR/wRC+, role, aging curves, risk flags) for input into models.
- [ ] Feature services
  - [ ] Trade evaluator API: ingest assets from both sides; output fairness and what each side gains/loses.
  - [ ] Roster optimizer: suggest lineup/rotation/pen with constraints (injuries, roles, usage).
  - [ ] Draft assistant: tier boards, comps, reach/steal probabilities by round.
- [ ] LLM integration
  - [ ] Provider selection (API vs local); rate limits, cost caps, caching.
  - [ ] Prompt templates with explicit instructions and JSON schema outputs.
  - [ ] Safety filters; PII redaction; ban external calls from prompts.
  - [ ] Deterministic seeds/top-p ranges for repeatability where possible.
- [ ] Evaluation harness
  - [ ] Golden tasks with expected outputs; regression tests for advice consistency.
  - [ ] Human-in-the-loop review UI to accept/reject suggestions and tune prompts.
- [ ] UI/UX
  - [ ] Forms to propose trades; in-line justifications; show uncertainty bands.
  - [ ] Explanations with linked metrics and raw numbers; expand for details.
- [ ] Observability
  - [ ] Log prompts/outputs with redaction; track latency, token usage, and error rates.
  - [ ] Feedback capture (thumbs up/down) tied to sessions.

Decision points
- **Model choice** and deployment (fully managed vs self-hosted).
- **Output format**: strictly typed JSON for downstream automation vs prose summaries.

Milestones
- **M1**: Read models and metrics in place; trade evaluator API stub.
- **M2**: First integrated LLM path for trade advice with guardrails.
- **M3**: Roster optimizer + draft assistant MVPs; feedback loop wired.
- **M4**: Evaluation harness with golden tasks; iterate for consistency.

### Epic 4: Replace Strat-O-Matic with a web-based engine

Goals
- **Server-authoritative web game engine** that mirrors Strat outcomes closely while addressing usage limits and reducing avenues for cheating.
- **Modernized model**: less extreme platoon splits, use wRC/xStats to inform event probabilities, de-bias for luck and park effects.

Architecture
- **Deterministic core with auditable randomness** (seeded RNG per play/session; hashes recorded).
- **Rules engine** decoupled from UI; persistent state in DB; event-sourced log for replay.
- **Anti-cheat**: server-validates all actions, signs results, detects anomalies.

Design/implementation to-dos
- [ ] Rules specification
  - [ ] Document inning/outs/balls/strikes state machine; base runner states; substitutions.
  - [ ] Define resolution order for events (pitch, contact, fielding, baserunning).
  - [ ] Calibrate probabilities from player cards (or derived xStats), park factors, handedness, fatigue.
- [ ] Data ingestion
  - [ ] Define schema for player cards/ratings and park factors; import existing data into DB.
  - [ ] Map legacy Strat ratings to new engine inputs with adjustable weights.
- [ ] Simulation engine
  - [ ] Deterministic RNG wrapper (seeded, per-event recorded seed).
  - [ ] Outcome calculators for PA types; pitcher-batter interaction matrix (reduced platoon emphasis).
  - [ ] Defense and baserunning modules with ratings → outcome probabilities.
  - [ ] Fatigue/usage model and substitutions policy.
  - [ ] Event log and audit trail; full replay and box score generation.
  - [ ] Batch sim mode for testing/calibration vs historical distributions.
- [ ] Game server and UX
  - [ ] Server-authoritative turn processing; WebSocket or SSE updates to clients.
  - [ ] Spectator mode; pause/resume; reconnection handling.
  - [ ] Admin tools to review games, overrides, and voids with signatures.
- [ ] Anti-cheat & fairness
  - [ ] Server-only RNG; clients never roll.
  - [ ] Signed event logs with tamper-evident hashes.
  - [ ] Usage caps and monitoring to prevent abuse.
  - [ ] Anomaly detection (suspicious patterns, excessive optimal decisions, timing attacks).
- [ ] Calibration & validation
  - [ ] Golden scenarios to match legacy outcomes within tolerance bands.
  - [ ] A/B sims to tune platoon weights and wRC/xStats adjustments.
  - [ ] Statistical validation suite (K-S tests, chi-square on outcome distributions).
- [ ] Ops
  - [ ] Performance profiling; scalable match processing queue.
  - [ ] Crash-only design; autosave after each event; recovery on restart.

Decision points
- **How closely to mirror Strat** vs introduce principled improvements.
- **Client protocol** (WebSocket vs HTTP polling) and reconnection semantics.

Milestones
- **M1**: Rules spec + data schema; deterministic RNG with audit.
- **M2**: Play resolution path E2E; box score + logs generated.
- **M3**: Multi-game server with anti-cheat and calibration suite.
- **M4**: Public beta; balance iterations; finalize fairness reports.

### Epic 5: Data cleanup (open-universe expansions and pruning)

Goals
- **Open-universe coverage**: add amateur players and foreign pros (NPB, KBO, CPBL, LMB/LMP, independent leagues, DSL/academies, college/HS where appropriate).
- **Prune inactive/retired players** to reduce processing time and clutter while preserving historical integrity.

Scope and definitions
- **Active status**: on a roster, under pro contract, or recorded appearances within freshness windows (league-specific).
- **Inactive/retired**: no appearances and no rostered status past window; manual overrides allowed for stash/prospect edge cases.

Design/implementation to-dos
- [ ] Source inventory and import
  - [ ] Identify authoritative directories for NPB, KBO, CPBL, Mexican (LMB/LMP), indy leagues, DSL.
  - [ ] Define raw snapshot fetchers with pagination, rate limiters, and caching.
  - [ ] Create mappers from each source schema → normalized player model.
- [ ] Bulk creation and enrichment tools
  - [ ] CLI workflow to stage new players from external lists with dry-run diff.
  - [ ] Admin UI to review staged adds/merges with fuzzy match suggestions.
  - [ ] Heuristics + fuzzy search: name, DOB, nationality, prior teams; show likely duplicates.
  - [ ] Auto-assign external IDs where reliable; defer uncertain cases to review queue.
- [ ] Duplicate detection and merging
  - [ ] Background job to generate candidate duplicate pairs using blocking keys:
    - [ ] Normalized names (lowercase, strip punctuation/diacritics, collapse whitespace).
    - [ ] Phonetic keys (Double Metaphone) and n-gram tokens for Jaro-Winkler/Sørensen–Dice.
    - [ ] DOB exact or within tolerance (±365 days for HS/JUCO data drift).
    - [ ] Overlapping context: college/team history, draft year/round/pick, birthplace.
  - [ ] Signals and hard matches
    - [ ] Conflicting rows sharing same external ID (MLBAM/FG/BBRef/Retrosheet) across two players.
    - [ ] Identical `bbref_slug` or `mlbam_name_key` with DOB proximity.
    - [ ] New FG/MLB post-draft entry matching existing placeholder (pre-draft) by name+DOB.
  - [ ] Scoring & thresholds
    - [ ] Compute composite duplicate score from fuzzy name, DOB delta, context overlaps.
    - [ ] Queue pairs above threshold for human review; auto-merge only for unambiguous ID collisions.
  - [ ] Review UX
    - [ ] Side-by-side compare with per-field provenance and proposed winner/field-level picks.
    - [ ] Actions: merge, link IDs only, dismiss, escalate; notes required for overrides.
  - [ ] Merge engine
    - [ ] Safe merge op that reassigns all foreign keys from loser → winner (atomic transaction).
    - [ ] Maintain `PlayerAlias`/`PlayerIdMap` entries for all prior names/IDs.
    - [ ] Write tamper-evident audit record (who, when, why, signals, before/after).
    - [ ] Soft-merge with rollback capability; no hard deletes.
  - [ ] Safeguards
    - [ ] Block merges when DOB differs beyond tolerance unless admin override.
    - [ ] Prevent merges across incompatible handedness without explicit confirmation.
  - [ ] Tooling
    - [ ] CLI: `players_find_duplicates`, `players_merge --winner --loser`, `players_merge_undo`.
    - [ ] Management command to refresh candidate queue nightly and on new imports.
    - [ ] Metrics: candidates/day, precision/recall (via reviewed outcomes), time-to-resolution.
  - [ ] Libraries & tech
    - [ ] Adopt `rapidfuzz` for fast fuzzy similarity; store precomputed tokens for performance.
    - [ ] Optional phonetic indexing table for blocked searches.
- [ ] Activity detection and status transitions
  - [ ] League-specific freshness windows (e.g., MLB 2y, NPB/KBO 2y, indy 1y, college 1y).
  - [ ] Scheduled job to compute `is_active`, `last_appearance_date`, and `activity_source`.
  - [ ] Manual override flags (`force_active`, `force_inactive`) that bypass automation.
- [ ] Pruning and archiving
  - [ ] Introduce `visibility_state` (active, archived, hidden) instead of hard deletes.
  - [ ] Exclude archived players from default queries, tables, and exports.
  - [ ] Archive job moves players to cold storage indexes; maintain references for history.
  - [ ] Optionally purge derived caches/stats for hidden players to speed processing.
- [ ] Performance tuning
  - [ ] Add partial indexes on `(is_active, league)` and external ID fields.
  - [ ] Denormalized read models for common mobile/table views that exclude archived.
  - [ ] Batch ETL with chunked upserts and retry semantics.
- [ ] Safety and auditability
  - [ ] Full change log with who/when/why for adds, merges, and status changes.
  - [ ] Exportable CSV of proposed adds/prunes for out-of-band review.
- [ ] Tests and QA
  - [ ] Golden fixtures per league; ensure consistent ID mapping and status transitions.
  - [ ] Backfill simulation on a copy of prod data; measure runtime and row deltas.

Decision points
- **Coverage depth** for amateurs (HS vs college vs international academies).
- **Archival policy**: how long before inactivity → archive; conditions for resurrection.

Milestones
- **M1**: Staging tools + importers for 2 foreign leagues; status computation job.
- **M2**: Admin review UI; archive/visibility states enforced in queries.
- **M3**: Full league coverage (NPB/KBO/CPBL/LMB/indy/DSL) with automated adds.
- **M4**: Performance target met (X% faster ETL, Y% smaller active sets).

### Cross-cutting concerns

- **Security**: authn/z for new APIs, CSRF on forms, rate limits for AI endpoints, secure secrets handling.
- **Privacy**: redact PII from logs; opt-in analytics.
- **Observability**: consistent structured logs; dashboards; alerts.
- **DX**: `make` or `bin/` commands for common tasks; dev data seeds; fast test loops.


