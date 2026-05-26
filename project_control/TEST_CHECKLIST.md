# Test Checklist

Audit timestamp: 2026-05-01T14:22Z

Legend:
- `[x]` verified with evidence
- `[ ]` not verified or failed

## A) Price List Scanner

- [x] Script runs without error
  - Evidence: active FPM status shows scanner running and previous chunk success in `out/systems/F/price_list_manager/live/live_cycle_health.csv`.
- [x] Output file generated
  - Evidence: `out/scanner_latest.csv`, 51 rows.
- [x] Product count > 0
  - Evidence: scanner rows = 51.
- [x] ASIN extraction valid
  - Evidence: 51 nonblank ASIN cells and 50 unique ASINs in `out/scanner_latest.csv`.
- [x] New products identified
  - Evidence: `out/link_check.csv` has 50 `New` ASINs.
- [ ] Existing products not duplicated
  - Evidence: scanner duplicate ASIN `B0DPMGDZLZ` appears twice.
- [x] SKU mapping correct
  - Evidence: scanner `supplier_sku` has 51 nonblank values and 51 unique values.
- [x] Data fields populated (price, cost, ROI if applicable)
  - Evidence: scanner export contains cost and price fields; all 51 rows have `pf=PASS`. ROI is represented by pass/fail economics in this scanner output, not a dedicated ROI column.

## B) Database Linking

- [ ] New ASIN inserted
  - Evidence: not run. No DB or Sheet insert was attempted.
- [ ] Existing ASIN updated (no duplicate row)
  - Evidence: not run. Update behavior was not tested because it could alter Product DB/Sheets.
- [ ] Unique identifiers enforced
  - Evidence: failed for ASIN uniqueness. Product DB snapshot has duplicate ASINs `0786964502`, `B07RRQX71T`, `B09NQ9ZHDQ`. `seller_sku` is unique.
- [x] Data persists across runs
  - Evidence: SQLite table `sys_product_db_preview` exported to `out/db_snapshot.csv` with 608 rows; O030 produced `out/systems/O/live/product_db_operator_view.csv` with 608 rows.

## C) Pricing System

- [x] Pricing script executes
  - Evidence: E002 ran successfully and wrote `out/sku_roi_snapshot.csv` with 58 rows.
- [x] Inputs loaded from database
  - Evidence: H pricing proof reads Product DB-derived runtime context; `out/pricing_output.csv` contains 89 SKU rows. E002 loaded sales truth inputs and wrote ROI output.
- [x] Output decisions generated
  - Evidence: `out/pricing_output.csv` has 62 `execute`, 8 `skip_cooldown`, 17 `skip_no_market_data`, and 2 blank decision rows.
- [ ] No null/zero pricing errors
  - Evidence: not fully clean. `out/pricing_output.csv` has 20 rows with blank `execution_write_status`.

## D) H-Cycle

- [ ] Scheduler triggers script
  - Evidence: no H scheduler XML export was found in `config/scheduler/`. Docs and tools reference task name `AMZ H Cycle`, but this audit did not query or change Windows Task Scheduler.
- [x] Cycle runs without crash
  - Evidence: `out/systems/H/live/H_cycle_last_terminal_info.txt` shows `state=finalized`, `publish_status=ok`, run `20260501T140505Z`.
- [x] Output/logs generated
  - Evidence: `out/phase1_runtime_floor_snapshot_latest.csv` has 89 rows; H terminal and publish markers exist.
- [x] Writes occur where expected
  - Evidence: H publish marker has `rows=49`, `status=ok`; `out/pricing_output.csv` includes 4 `APPLIED` rows.

## E) Focused Regression Tests

- [x] `tests/test_e002_build_roi_snapshot.py`
- [x] `tests/test_o030_build_product_db_operator_view.py`
- [x] `tests/test_f000_paths_and_schemas.py`
- [x] `tests/test_f005_build_supplier_price_list_universal.py`
- [x] `tests/test_fpm020_placeholder_scanner.py`
- [x] `tests/test_storage_adapter.py`

Result: 28 passed.
