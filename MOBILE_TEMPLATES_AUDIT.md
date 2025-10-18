### Mobile Web Audit (Passive-first)

Scope focuses on mobile web (no native app), prioritizing readable tables and browsing. Actions like drops/protections/admin remain desktop-only. Draft tooling deferred; optional future "watch" is noted but not required now.

---

### Shared layout: `ulmg/templates/base.html`
- Current:
  - Has `<meta name="viewport" content="width=device-width, initial-scale=1.0">`.
  - Uses Tailwind CDN and `theme.css`.
  - Global filter section renders on all pages; horizontal table sorting via `sortable`.
- Issues on mobile:
  - Fixed header + collapsible filter can push content; ensure margin compensates consistently.
  - Nav density (links + dropdowns) is high; small tap targets.
- Recommendations:
  - Ensure `.content-with-fixed-header` margin adjusts on resize and orientation change (already present; keep).
  - Wrap all data tables in `.overflow-x-auto` container.
  - Increase tap targets in nav; on XS, collapse non-essential links into a single `More` dropdown.
  - Make search input full-width on XS; consider placing search above nav links.
  - Hide drops/protections/admin utilities on XS/SM via responsive classes or server-side conditionals.

---

### Homepage: `ulmg/templates/index.html`
- Current:
  - League overview cards by division; then large hitters/pitchers tables for unowned MLB players.
  - Wishlist “+” buttons when authenticated.
- Issues on mobile:
  - Two-wide grid ok on XS; stats tables are wide; header and first column can scroll off-screen.
- Recommendations:
  - Wrap tables in `.overflow-x-auto`.
  - Sticky header row and sticky first column for name on XS.
  - Reduce default columns on XS (Lvl + 4–6 key stats); reveal full set on MD+.
  - Keep wishlist “+” if desired for passive-plus; otherwise hide on XS for pure passive baseline.

---

### Search/Filter: `ulmg/templates/search.html`
- Current:
  - Renders hitters grouped by position, then pitchers; uses shared filter bar from base.
  - Rows can represent `Player` or `PlayerStatSeason` and include links to team and player.
- Issues on mobile:
  - Table width; jump links useful; filter form is heavy for phones.
- Recommendations:
  - Keep jump links; add a back-to-top button anchored in-page.
  - Use `.overflow-x-auto`; sticky header and first column.
  - Collapse less-important columns on XS (e.g., some rate stats) to fit ~6–8 columns visible.
  - In base filter form, stack fields in 1-col on XS; make the submit button sticky at the bottom of the filter section.
  - Hide any wishlist or action controls on XS to maintain passive browsing.

---

### Team page: `ulmg/templates/team.html`
- Current:
  - Summary blocks, then hitters/pitchers tables with optional protect/drop controls if `own_team`.
- Issues on mobile:
  - Protect/roster actions render in table headers/cells; not desired on phones.
- Recommendations:
  - Hide columns and cells for protect/roster actions on XS/SM regardless of `own_team`.
  - Wrap tables in `.overflow-x-auto`; sticky name column.
  - For summary grids, ensure two-column layout on XS with readable text size.
  - Hide AA/Open Draft planner tabs on XS/SM; show only on MD+ until mobile-ready.

---

### Team (Trades & picks): `ulmg/templates/team_other.html`
- Current:
  - Tab nav: link back to Roster; shows AA/Open Draft links if `own_team`.
  - Trades grouped by season; table columns Date, Team, Received, Sent with links to players and picks.
  - Draft picks grouped by Year → Season → Type; links to draft page anchors.
- Issues on mobile:
  - Trades table can overflow; Received/Sent lists are long and dense; small tap targets.
  - No sticky header; no in-page jump/back-to-top; sections can be very long.
- Recommendations:
  - Wrap trades table in `.overflow-x-auto` with `min-w-max`; make header sticky on XS.
  - Allow Received/Sent to wrap; consider stacked layout or chip-style items on XS.
  - Add jump links to years and a back-to-top anchor for both Trades and Picks.
  - Collapse picks by Year/Season on XS (accordion); default-expand current year.
  - Keep passive: hide any actions; ensure comfortable tap targets.
  - Hide AA/Open Draft planner tabs on XS/SM; show only on MD+ until mobile-ready.

---

### Player page: `ulmg/templates/player_detail.html`
- Current:
  - Header with optional wishlist "+", team link, tags; transactions history; seasonal stat tables.
- Issues on mobile:
  - Tables are wide; many columns; wishlist “+” visible.
- Recommendations:
  - Keep passive: hide wishlist button on XS for now.
  - Wrap stat tables in `.overflow-x-auto`; collapse to core columns on XS.
  - Use definition-list or 2-col grid for bio details; ensure readable text.

---

### Navigation: `ulmg/templates/includes/nav.html`
- Current:
  - Text links, dropdowns for Drafts and Teams, inline search.
- Issues on mobile:
  - Dense; small input; dropdowns require precision.
- Recommendations:
  - On XS, stack: first row brand + search (full-width), second row collapsible menu (Drafts, Teams, Trades, Login/My Team).
  - Increase input width and tap targets.
  - Consider turning dropdowns into simple links to index pages on XS.

---

### Table readability patterns (apply across templates)
- Horizontal scroll baseline: `.overflow-x-auto` wrapper; `min-w-max` on tables.
- Sticky header: `sticky top-0` on `<thead>`; ensure background to avoid bleed.
- Sticky first column: `sticky left-0 bg-white` on the name cell; add right border.
- Column priority: hide low-priority columns on `sm` and below; show all on `md+`.
- Typography: keep `text-xs` body, `text-sm` headers on XS; increase on larger screens.

---

### Passive constraints and actions
- Hide on mobile (XS/SM): drops, protections, roster/move buttons, bulk actions, admin utilities.
- Hide AA/Open Draft planner tabs on XS/SM regardless of settings/feature flags.
- Keep read-only badges and status indicators.
- Optional later: lightweight "watch" star; for now, keep disabled/hidden on XS.

---

### PWA foundation checklist
- Manifest: ensure `/site.webmanifest` exists and references icons, theme, display=standalone.
- Service Worker: cache static assets, icons, and shell; simple stale-while-revalidate.
- A2HS: verify installability; provide prompt UX where appropriate.

---

### Next steps
- Implement horizontal scroll + sticky header/first column for homepage and search tables.
- Hide action columns and controls on XS/SM for team and player pages.
- Adjust nav layout for XS: larger tap targets, full-width search.
- Add/verify manifest and basic service worker.
 - Hide AA/Open Draft planner tabs on XS/SM until those pages are mobile-friendly.
