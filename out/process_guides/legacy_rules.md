# Pipeline Rules

Keep each dataset isolated, simple, and observable.

## Structure
- Folder layout:
  - `scripts/` holds runners labeled by flow: `A001_run_listings_to_sheet.py`, `A002_run_catalog_items_to_sheet.py`, etc.
  - `scripts/api/` holds API callers/helpers only (no Sheets writes): `get_merchant_listings_report.py`, `get_catalog_items.py`.
  - `scripts/SCRIPTS.md` documents runners; `out/` holds CSV snapshots; `secrets/.env` stores env.
- One runner per dataset/pipeline; API calls belong in `scripts/api/`.
- Each runner:
  - Loads creds/IDs from env.
  - Writes a raw tab and a focused summary tab to Google Sheets (shared tab `Listings_focus_summary` uses column 1 for script code, then your keep columns).
  - Updates a single row in `Run_Status` (no growth) with status/alert/counters.
  - Saves a CSV snapshot to `out/` for history.
- Tabs stay fixed per runner; do not mix datasets in one tab.

## Behavior
- No silent failures: on error, set `alert` and record the message in `Run_Status`.
- Consistent layouts:
  - Raw tabs: full dataset as returned.
  - Summary tabs: clean headers, only the focused columns; no mixed meta rows.
  - Run_Status: one row per `script+mode+marketplace`, overwritten each run.
- Optional debug: if `DEBUG_RAW=true`, write lightweight step logs to `out/debug.log`; default off to keep noise down.
- Avoid optional extras unless data is available (e.g., image enrichment stays off until confirmed).
- Keep history in snapshots (CSV). Sheets are for monitoring/spot checks.
- Keep cache noise out of git: add `__pycache__/` and other generated files to `.gitignore`.
- `Run_Status` is the single source of truth for failures: always set `alert` and message on error, and overwrite the same row per `script+mode+marketplace`.

## Adding a new runner
- Reuse shared helpers in `scripts/`.
- Define fixed tab names for raw and summary.
- Implement status upsert (single row) with alert logic.
- Save a CSV snapshot to `out/`.
- Keep polling/attempts configurable via env.
