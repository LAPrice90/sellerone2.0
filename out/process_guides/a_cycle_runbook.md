# A Cycle Runbook (Inventory + Catalog + Researching Deltas)

This guide explains the A scripts in plain language, what each one does, and how they should run daily. It is the source of truth for the A cycle.

---

## 0) What the A cycle is

The A cycle is the "catalog and inventory" pipeline. It refreshes listings, catalog metadata, inventory snapshot, and applies researching or unsellable deltas.

It does NOT touch orders or tokens directly. It prepares the live stock view that the token system relies on.

---

## System health check (use after changes)

Run `python scripts/A015_build_system_health_check.py` after any changes or failed runs.
This catches blank Order_Master rows, token gaps, and stale data before they cascade.
Alert summary prints after the health check (FAIL/WARN counts) so issues are obvious without manual digging.
Note: A and B now share a run lock (default `out/run_cycle.lock`). If A is running, B should wait, and vice versa.
Alert aging metadata is now added per check so repeated alerts are easier to triage:
- `alert_first_seen_utc`
- `alert_last_seen_utc`
- `alert_consecutive_runs`
- `alert_age_hours`
State file:
- `out/system_health_alert_state.csv` (active FAIL/WARN checks only)
- B and E diagnostics now use live-first artifact paths:
- B log source for `b_cycle_recent_fail_lines`: `out/systems/B/live/B_cycle.log` then fallback `out/B_cycle.log`.
- E run log source for schema checks: `out/systems/E/live/e_run_log.jsonl` then fallback `out/e_run_log.jsonl`.
- E run log rows now include:
- `expected_input_asof`
- `output_asof`
- `asof_rerun_trigger`
- New B external dependency visibility check:
- `b_sheet_sync_external_health` (warn-only signal for sheet degradation, core B failures stay separate).

Health check gate:
- A015 exit code 2 (FAIL) blocks publishing and stops the A run.
- A015 exit code 1 (WARN) allows the run to continue but prints an alert.
- A split isolation modes:
- `A_SPLIT_HEALTH_MODE=legacy|shadow|split` (rollout default `shadow`)
- `A_SPLIT_CHECKLIST_PATH=out/cycle_alerts/checklist_A_split.csv`
- `legacy`: existing global A015 gate behavior.
- `shadow`: keep legacy gate, run `A015 --profile a` candidate, and log compare row.
- `split`: gate on `A015 --profile a`; run global A015 for observability only (non-blocking).
- Shared rollout tracker files (A/B/E):
- `out/cycle_alerts/flow_selftest_compare.csv`
- `out/cycle_alerts/flow_selftest_state.json` with:
- `a_match_streak`
- `b_match_streak`
- `e_match_streak`
- `ready_for_cutover`

Detail output (for investigations):
- out/health_order_master_blank_cogs_lvl1plus.csv (orders missing token COGS)

---

## 1) Daily run order (intended)

1) A001_run_listings_to_sheet.py
2) A002_run_catalog_items_to_sheet.py
3) A003_run_inventory_to_sheet.py
4) A010_apply_researching_delta.py (wraps B010)
5) A005_run_inventory_adjustments_report.py
6) A004_run_fees_to_sheet.py
7) A016_refresh_phase1_daily_intel.py (full DB Phase 1 intel refresh)
8) dedupe_product_db.py
9) sync_product_db_to_main_sheet.py
10) H001_capture_offer_snapshot.py
11) run_E_cycle.py
12) A015_build_system_health_check.py (system checklist report)
13) A020_run_daily_finance.py (daily finance/report steps)
14) process_stock_receipts_sheet.py (only when RECEIPTS_RUN=YES)

---

## 2) Script purposes (plain language)

### A001_run_listings_to_sheet.py
Purpose: refresh the seller listings snapshot (SKU, ASIN, title). Used as the base for all later catalog and inventory pulls.

Outputs:
- out/merchant_listings_latest.csv
- Sheets: MerchantListings_raw, Listings_focus_summary

### A002_run_catalog_items_to_sheet.py
Purpose: fetch catalog metadata (titles, brand, category, etc) for the active ASINs.

Outputs:
- out/catalog_items_flat.csv
- Sheets: CatalogItems_raw, Listings_focus_summary

### A003_run_inventory_to_sheet.py
Purpose: pull live inventory snapshot (available, inbound, reserved, researching, unsellable, etc).

Outputs:
- out/inventory_summaries.csv
- Sheets: Inventory_raw, Listings_focus_summary (unless INVENTORY_WRITE_SHEETS=0)

Default behavior in run_A_all.py:
- INVENTORY_WRITE_SHEETS defaults to 0 to avoid quota errors.

### A010_apply_researching_delta.py
Purpose: apply daily deltas for researching/unsellable movement to the token system.

Important rule:
- If A003 fails, A010 must be skipped because it depends on a fresh inventory snapshot.

### A005_run_inventory_adjustments_report.py
Purpose: pull inventory ledger detail view (Amazon stock adjustments).

Outputs:
- out/inventory_ledger_raw.csv
- Sheet: Inventory_Ledger_raw

### A004_run_fees_to_sheet.py
Purpose: pull fees estimates for SKUs.

Outputs:
- out/fees_estimates.csv
- out/fees_failed.csv (final unresolved-only rows after retries)
- Sheet: Fees_Estimates

Retry behavior:
- A004 now retries by failed price point, not by whole row.
- Price points that already succeeded are kept and are not retried.
- Controlled requeue settings:
- `FEES_REQUEUE_MAX_PASSES` (default `2`)
- `FEES_REQUEUE_PASS_BACKOFF_SEC` (default `15`)

How to read `out/fees_failed.csv`:
- Each row is a true unresolved SKU after all retry passes.
- `failed_price_points` shows which price points still failed (for example `10|100`).
- `attempt_count_10` and `attempt_count_100` show total attempts used.
- `failure_recorded_utc` shows when the unresolved result was written.

### A016_refresh_phase1_daily_intel.py
Purpose: build daily Phase 1 intel for repricing across the full SKU database.

Policy:
- Scope default is full DB (`--scope full_db`).
- A016 generates `out/phase1_sku_scope.csv` each run and uses strict parked classification.
- Parked SKUs are no-write and no-CPT-call.
- Target universe for H/A016 should be `scope_non_parked` (non-parked scope is source of truth).
- Even when `active_merchant` mode is used, resolver applies a scope guardrail to exclude parked SKUs.
- CPT calls are A-cycle only and tiered by writer mode / parked state.
- `HTTP 200` with no CPT value is treated as `NO_CPT` (normal non-alerting state).
- `NO_CPT` rows are retried weekly (default `168` hours), not every run.
- `MISSING` and `ERROR` keep daily recovery retry behavior.

Inputs:
- out/product_db_preview.csv
- out/merchant_listings_latest.csv
- latest out/listing_offer_snapshot_*.csv
- config/phase1_writer_modes.csv

Outputs:
- out/phase1_sku_scope.csv
- data/sku_daily_intel.csv

Key A016 counters:
- `a016_cpt_no_cpt_rows`
- `a016_cpt_due_no_cpt_weekly`
- `a016_cpt_skip_no_cpt_weekly`
- `a016_cpt_no_value_recheck_hours`

### dedupe_product_db.py and sync_product_db_to_main_sheet.py
Purpose: clean and publish Product_DB to the main sheet.

### process_stock_receipts_sheet.py
Purpose: turn received stock rows into tokens.

Guardrail:
- This only runs when RECEIPTS_RUN=YES.
- If not set, it is skipped and does NOT fail the A cycle (this is expected).

---

## 3) Failure handling rules

### Inventory snapshot failure
If A003 fails:
- A010 must be skipped.
- Do not apply researching/unsellable deltas off a stale snapshot.

### Sheet quota limits
If sheets hit quota:
- Run A003 with INVENTORY_WRITE_SHEETS=0
- Keep data local and reduce sheet writes.

---

## 4) What "working" means

A healthy A run means:
- Listings and catalog are refreshed without errors.
- Inventory snapshot is saved locally.
- Researching/unsellable deltas apply only after a successful A003 snapshot.
- Product_DB export is updated.

---

## 5) Daily sanity check (fast)

1) Verify out/inventory_summaries.csv updated today
2) Verify A010_apply_researching_delta.py reports deltas or no_deltas (not error)
3) Verify out/phase1_sku_scope.csv updated today and parked/non-parked counts look sane
4) Verify non-parked SKUs have same-day rows in data/sku_daily_intel.csv
5) Verify Product_DB_Export updated
6) Verify `out/fees_failed.csv` is either empty or only contains true unresolved retries
7) Verify A016 counters explain CPT call behavior (`a016_cpt_calls`, `a016_cpt_due_no_cpt_weekly`, `a016_cpt_skip_no_cpt_weekly`)

---

## 6) Owner decisions (explicit)

- A010 only runs after a successful A003.
- process_stock_receipts_sheet.py is manual guardrail (RECEIPTS_RUN=YES).
- Keep sheets minimal to avoid quota failures.
- A020_run_daily_finance.py runs the heavy finance/report steps once per day.

Finance write guardrail:
- FIN_L3_SKIP_SHEETS defaults to 1 in run_A_all.py when running A020.
- This prevents Level 3 sheet writes from hitting the 10M cell limit.
- `scripts/D017_audit_daily_guardrails.py` also writes alert aging fields in `out/audit_daily_guardrails.csv`
  using state file `out/audit_daily_guardrails_state.csv`.

Phase 1 writer-mode guardrail:
- `config/phase1_writer_modes.csv` is the source of truth for per-SKU writer mode.
- Allowed values: `PPP`, `CODEX_H`, `READ_ONLY`.
- Missing mode defaults to `READ_ONLY`.

Rollout guardrail:
- Stage A: all SKUs stay `READ_ONLY`.
- Stage B: enable `CODEX_H` in small approved batches only after soak gates pass.
- Dropped/discontinued products stay parked automatically and never move to write-enabled.

---

## 7) A scripts TODO (after stability)

Keep this simple and do not act on it until the system is stable.

Planned (not active yet):
- Add a "dropped/discontinued" list to Product_DB.
- Backfill past dropped SKUs for accuracy.
- Use the dropped list to skip fees/catalog calls for discontinued SKUs.

---

End.

---

## 8) Self-healing development rules (mandatory)

Whenever we add a new phase or script:
1) Add a health check item (A015) that validates it.
2) Add an alert rule (FAIL or WARN) so issues are visible immediately.
3) Add schema checks for any new CSV outputs.
4) Use staged writes (build locally, publish once complete).
5) Ensure the step is idempotent (safe to rerun).

If any of these are missing, stop and add them before continuing.

---

## 9) Daily Intel Coverage Recovery

Use this when daily intel coverage drops for non-parked SKUs.

1) Check latest scope:
- Confirm `out/phase1_sku_scope.csv` exists and has expected non-parked count.

2) Check writer mode map:
- Confirm `config/phase1_writer_modes.csv` has valid `pricing_writer_mode` values.
- Invalid values fall back to `READ_ONLY`.

3) Rebuild daily intel safely:
- Run A016 in dry-run first to confirm counts:
- `python scripts/A016_refresh_phase1_daily_intel.py --dry-run --scope full_db`
- Then run normal A cycle (no ad-hoc H writes).

4) Verify health checks:
- Watch A015 checks:
- `a_daily_intel_coverage_non_parked`
- `a_daily_intel_compliance_nonempty_non_parked`
- `h_no_cpt_calls_in_h_cycle`
- `h_parked_sku_write_attempts`
- `h_scope_non_parked_matches_targets`

---

## 10) Verification Using Cycle Artifacts

Use this after changes without running ad-hoc A scripts.

1) Check latest health snapshot:
- `out/system_health_checklist.csv`
- Confirm `a_fees_failed_rows_today` value and status.

2) Check cycle timing and fail-window context:
- `out/B_cycle.log`
- `out/run_cycle.log`

3) Check fee retry outcome:
- `out/fees_estimates.csv` has one final row per SKU for the run.
- `out/fees_failed.csv` has unresolved-only rows with attempt counts and failed price points.

4) Check NO_CPT scheduling behavior:
- Review A016 console counters in the cycle log:
- `a016_cpt_no_cpt_rows`
- `a016_cpt_due_no_cpt_weekly`
- `a016_cpt_skip_no_cpt_weekly`
