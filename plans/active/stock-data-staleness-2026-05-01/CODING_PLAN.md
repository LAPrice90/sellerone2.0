# Stock Data Staleness - 2026-05-01

## Status
- Phase: isolated verification passed; live timestamp proof confirmed; core auto-refresh proof pending parent reload
- Started at: 2026-05-01T09:33:00Z
- Owner: Codex

## Problem
Stock data is stale again. User reported SKU `6V-EEC1-2S9Z` showing `260` products while Amazon-side stock is now `224`.

Current local evidence:
- `out/inventory_snapshot_latest.csv` was written at `2026-05-01T05:02:05Z`.
- For SKU `6V-EEC1-2S9Z`, local latest stock is `available=169`, `total_quantity=194`, `last_updated_time=2026-05-01T03:38:13Z`.
- H recovered run `20260501T091405Z` warned that stock snapshot age was `9.23` hours.

## Root Cause
- Daily A003 inventory refresh was working, but H consumed the same morning inventory snapshot all day.
- H rewrote inventory history from the existing same-day snapshot; it did not refresh inventory before repricing when the same-day snapshot aged.
- H stock-age calculation preferred `asof_date` before `timestamp_utc`, so a valid same-day snapshot could be treated as midnight and reported with a misleading `age_hours`.
- The user-reported `224` Amazon-side count was not reproduced by local SP-API proof. The forced A003 refresh returned SKU `6V-EEC1-2S9Z` as `available=159`, `total_quantity=192`, `last_updated_time=2026-05-01T09:14:43Z`.

## Allowed Files
- `scripts/flows/A/A003_run_inventory_to_sheet.py`
- relevant A-owned tests under `tests/`
- A/H health checks or scoped validators only if already part of owned proof
- this plan file
- roadmap/expectation files only if evidence supports a status update

## Boundaries
- Do not change Google Sheets unless explicitly asked.
- Do not change local DB to match Sheets without approval.
- Do not run A scripts ad-hoc unless the user explicitly asks for an A run or a forced A-owned proof window is documented and approved by current instructions.

## Proof Plan
- Use existing artifacts first: A logs, inventory snapshots, health outputs, and current code paths.
- Identify whether the defect is cadence, source selection, SP-API freshness, token-floor overlay, or publish/display staleness.
- If code changes are needed, add focused tests and use an A-owned proof path instead of a standalone health script.

## Implementation
- Ran A003 manually with Google Sheets disabled:
  - `INVENTORY_WRITE_SHEETS=0`
  - `INVENTORY_USE_API_OWNER=0`
  - script: `scripts/flows/A/A003_run_inventory_to_sheet.py`
- A003 refreshed local inventory outputs and Product DB preview:
  - persisted inventory rows: `339`
  - local Product DB stock rows refreshed: `318`
  - sheet tabs written: `[]`
- Updated `scripts/flows/H/H110_run_phase1_h_pilot.py` so snapshot age prefers `timestamp_utc` before date-only fields.
- Updated `scripts/cycles/run_H_pricing_cycle.py` so H can call A003 locally, with Sheets disabled, when the same-day inventory snapshot is older than `H_INVENTORY_SNAPSHOT_REFRESH_MAX_AGE_SECONDS` default `3600`.
- Added focused regression coverage in `tests/test_h110_stock_stale_guard.py`.

## Verification
- `python -m py_compile scripts\cycles\run_H_pricing_cycle.py scripts\flows\H\H110_run_phase1_h_pilot.py` passed.
- `python -m pytest tests\test_h110_stock_stale_guard.py tests\test_a003_inventory_stale_token_floor.py -q` passed: `10 passed`.
- Live H child-process proof after the H110 fix: run `20260501T094820Z` reported inventory snapshot `age_hours=0.20`, proving the source-age calculation no longer treated the current snapshot as midnight.
- Monitoring check at `2026-05-01T10:11Z`: H stock status reported inventory snapshot `age_hours=0.44`; current inventory latest file was last written at `2026-05-01T09:36:20Z`.
- Monitoring check at `2026-05-01T10:18Z`: H stock status still reports inventory snapshot `age_hours=0.44`; remaining `WARN` is row-level stale history count, not a source-age failure.
- Core auto-refresh in `run_H_pricing_cycle.py` is code-fixed and isolated-test-clean, but live proof requires the H parent process to reload the patched core at a natural restart boundary.

## Monitoring
- Artifact: `out/inventory_snapshot_latest.csv`.
- SKU probe: `6V-EEC1-2S9Z`.
- Success threshold: the process has a clear current-stock refresh owner, stale stock cannot silently feed H beyond the agreed age, and evidence distinguishes API freshness from dashboard/display freshness.
- Timeout rule: if root cause needs Amazon live truth that is unavailable locally, park with exact missing evidence and the safe next proof window.
