# Execution Batch 002

## Purpose
- Recover BBP chart coverage on the current supplier scrape list, prove the new monthly fields against a small live ASIN pack, then return the supplier to normal overnight scanning with the fuller data capture path in place.

## Why this batch exists
- Batch 001 fixed the trust contract.
- It exposed the next root cause:
  - the scraper logic is ready to use completed-month BBP truth
  - but current scrape coverage is thin
  - only `330` of `1581` current scrape-evidence rows carry the full BBP month fields
  - `1251` rows already have ASINs but still have no trusted completed-month basis
- This is now the main reason:
  - `manual_review_share` is high
  - sampled audit mismatches stay high

## Scope guardrails
- Only do:
  - validate a handful of current ASINs against live BBP chart output
  - build a targeted rescrape subset from the current supplier queue
  - recover BBP chart coverage for rows missing completed-month evidence
  - rebuild F outputs after the rescrape
  - restore the supplier to its normal full queue before the overnight run
  - make the runner path explicit for the supplier actually in the active queue
- Do not change:
  - Google Sheets
  - local DB state
  - H runtime
  - decision logic rules unless live validation proves a scraper contract gap
- Do not add:
  - manual per-ASIN CSV patching as the source of truth
  - a permanent split where the overnight loop only scans a test subset

## Files allowed to change
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_002.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/RUNBOOK.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/STATUS_REPORT_2026-04-14.md`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/F062_reset_supplier_test_mode.py`
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/_source_contracts.py`
- `scripts/one_off/F004_build_bbp_sales_sample_audit.py`
- `scripts/one_off/F005_build_sales_history_validation_audit.py`
- new one-off helper(s) under `scripts/one_off/` for:
  - live ASIN validation pack build
  - targeted supplier rescrape subset build
- `run_F_shure_full_legacy_scan.bat`
- `run_F_shure_test_mode_scan_once.bat`
- new F runner batch file(s) if needed for `stocklist_supplier` or a generic supplier runner
- related tests under `tests/`

## Inputs to read first
- `AGENTS.md`
- `CODEX.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/STATUS_REPORT_2026-04-14.md`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/systems/F/live/feeder_backtest_input_view_live.csv`
- `out/systems/F/live/feeder_backtest_summary_live.csv`
- `out/systems/F/live/feeder_backtest_health.csv`
- `out/systems/F/inbox/supplier_price_list_active_run.csv`
- `out/systems/F/inbox/suppliers/stocklist_supplier/active_run.csv`
- `out/systems/F/inbox/suppliers/stocklist_supplier/canonical_current.csv`
- `out/analysis_reports/f_backtest_bbp_sales_sample_audit_latest.csv`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/F062_reset_supplier_test_mode.py`
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`

## Tasks

### Task 1
- Goal:
  - build and check a mixed live-ASIN validation pack before broad rescrape work
- Notes:
  - include at least:
    - completed-month rows
    - zero-history rows
    - rows missing completed-month fields
  - the pack must be easy for the operator to open row by row in Amazon/BBP
  - use direct Amazon links in the output

### Task 2
- Goal:
  - add a targeted supplier rescrape subset path
- Notes:
  - build the subset from the current supplier queue plus current scrape evidence
  - start with rows that already have ASINs but are missing:
    - `bbp_sales_last_completed_month_label`
    - `bbp_sales_replay_demand_basis_source`
  - the subset path must be reversible so the full supplier queue can be restored cleanly

### Task 3
- Goal:
  - make the supplier runner path truthful for the live supplier queue
- Notes:
  - current checked-in batch files are Shure-specific
  - live active queue is currently `stocklist_supplier`
  - either:
    - add a correct stocklist runner
    - or replace the hard-coded runner with a generic supplier runner

### Task 4
- Goal:
  - run targeted rescrape recovery and rebuild F outputs
- Notes:
  - after the subset run:
    - rebuild `F070` to `F074`
    - rebuild `F004`
    - rebuild `F005`
  - compare before/after coverage and health truthfully

### Task 5
- Goal:
  - restore the supplier to normal overnight scanning
- Notes:
  - restore from `canonical_current`
  - prove the active run is back on the full queue
  - prove the overnight runner is pointing at the correct supplier

## Tests
- Minimum command:

```powershell
pytest tests/test_f004_build_bbp_sales_sample_audit.py tests/test_f005_build_sales_history_validation_audit.py tests/test_f061_run_legacy_first_checks_local.py tests/test_f071_build_backtest_input_view.py tests/test_f074_build_backtest_health.py
```

- Plus:
  - tests for any new one-off rescrape subset builder
  - tests for any new live-ASIN validation export
  - tests for any new or changed runner helper

## Proof required
- Coverage proof:
  - before/after count of rows with:
    - chart month labels
    - completed-month fields
    - replay basis fields
  - before baseline to beat:
    - evidence rows: `1581`
    - completed-month coverage rows: `330`
    - missing full-chart rows with ASIN: `1251`
- Validation proof:
  - a small live-ASIN pack exists with mixed cases
  - at least one row in each case is checked:
    - completed month correct
    - zero history correct
    - missing field correctly flagged for rescrape
- Health proof:
  - `f_backtest_health_staleness` remains current
  - `f_backtest_demand_basis_integrity` stays `ok`
  - `manual_review_share` is remeasured after the rescrape
- Queue proof:
  - targeted subset queue size is captured
  - restored full queue size is captured
  - supplier runner used for the overnight run matches the active supplier queue
- Output files:
  - updated `feeder_legacy_scrape_evidence_live.csv`
  - updated `feeder_backtest_input_view_live.csv`
  - updated `feeder_backtest_summary_live.csv`
  - updated `feeder_backtest_health.csv`
  - updated `f_backtest_bbp_sales_sample_audit_latest.csv`
  - updated `f_sales_history_validation_latest.csv`
  - new live-ASIN validation pack if added

## Completion checklist
- [x] Mixed ASIN validation pack built
- [x] Mixed ASIN pack checked against live BBP
- [x] Targeted rescrape subset path built
- [x] Correct supplier runner path defined
- [x] Targeted rescrape run completed
- [x] F outputs rebuilt after rescrape
- [x] Before/after coverage proof captured
- [x] Full supplier queue restored
- [x] Overnight run path ready
