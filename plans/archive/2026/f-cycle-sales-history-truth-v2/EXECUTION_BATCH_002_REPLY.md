# Execution Batch 002 Reply

## Status
- Complete / Partial / Failed:
  - complete
- Checked against:
  - `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_002.md`

## Summary of work done in this hometime window
- Live ownership safety:
  - detected overlapping owner run on `stocklist_supplier`
  - paused overlap process chain before subset apply
- Validation:
  - built mixed live-ASIN pack with completed-month, zero-history, and missing-basis rows
- Targeted recovery:
  - built targeted subset from missing completed or replay basis rows
  - applied subset queue with backup snapshot
  - ran bounded subset recovery window (`25` rows)
- Rebuild:
  - rebuilt `F070` to `F074`
  - rebuilt `F004` and `F005`
- Restore:
  - restored full supplier queue from `canonical_current`
  - resumed overnight owner path on `stocklist_supplier`

## Runtime proof checkpoints (5)
1. Live validation pack built
- command:
  - `python scripts/one_off/F006_build_live_asin_validation_pack.py --completed-count 4 --zero-history-count 2 --missing-basis-count 6`
- result:
  - rows: `12`
  - `trusted_completed_month=4`
  - `explicit_zero_history=2`
  - `missing_completed_month_basis=6`
- output:
  - `out/analysis_reports/f_live_asin_validation_pack_latest.csv`

2. Targeted subset applied
- dry-run command:
  - `python scripts/one_off/F007_prepare_targeted_rescrape_subset.py --supplier-id stocklist_supplier --queue-source auto --output-dir out/analysis_reports`
- apply command:
  - `python scripts/one_off/F007_prepare_targeted_rescrape_subset.py --supplier-id stocklist_supplier --queue-source auto --apply --output-dir out/analysis_reports`
- dry-run/apply facts:
  - latest supplier scrape rows: `4598`
  - missing ASIN rows with missing completed or replay basis: `2267`
  - selected subset rows: `2248`
  - supplier active rows:
    - before apply: `32872`
    - after apply: `2248`
  - backup:
    - `out/systems/F/inbox/suppliers/stocklist_supplier/rescrape_subset_backups/20260418T203524Z`

3. Targeted subset run completed
- overlap-safe handoff:
  - detected overlap owner processes:
    - `cmd.exe /c run_F_shure_full_legacy_scan.bat stocklist_supplier`
    - `python ... F061_run_legacy_first_checks_local.py --supplier-id stocklist_supplier --loop`
  - stopped overlap pids: `25872`, `22032`
- run command:
  - `python scripts/flows/F/F061_run_legacy_first_checks_local.py --supplier-id stocklist_supplier --max-rows 25 --scrape-mode legacy_module --price-source native_comp_summary --pricing-min-interval-seconds 32 --legacy-scanner-root c:\Users\Luke\Desktop\SellerOne 2.0\scripts\flows\F\legacy_scanner_2_1`
- result:
  - processed rows: `25`
  - scrape attempted rows: `25`
  - scrape success rows: `24`
  - subset pending rows after run: `2223`

4. Rebuild outputs completed
- commands:
  - `python -m scripts.flows.F.F070_build_backtest_policy_snapshot`
  - `python -m scripts.flows.F.F071_build_backtest_input_view`
  - `python -m scripts.flows.F.F072_run_backtest_replay`
  - `python -m scripts.flows.F.F073_build_backtest_summary`
  - `python -m scripts.flows.F.F074_build_backtest_health`
  - `python scripts/one_off/F004_build_bbp_sales_sample_audit.py`
  - `python scripts/one_off/F005_build_sales_history_validation_audit.py`
- result:
  - `F070`: rows `1`
  - `F071`: rows `2359`, `ready=2155`, `manual_review=204`
  - `F072`: rows `771255`
  - `F073`: rows `2359`, `fail=1886`, `pass=269`, `manual_review=204`
  - `F074`: status counts `ok=15`, `warn=1`
  - `F004`: rows `18`, mismatch rows `2`
  - `F005`: rows `28681`, trusted rows `2264`, predicted rows `6792`

5. Full queue restored and overnight owner target confirmed
- restore command:
  - `python scripts/flows/F/F062_reset_supplier_test_mode.py --supplier-id stocklist_supplier --no-clear-review-live`
- restore result:
  - supplier active rows restored to `42663`
- overnight ownership resume:
  - started:
    - `cmd.exe /c run_F_supplier_full_legacy_scan.bat stocklist_supplier`
  - confirmed active child:
    - `python ... F061_run_legacy_first_checks_local.py --supplier-id stocklist_supplier --max-rows 5 --loop`

## Coverage and health proof
- Required historical baseline reference from batch prompt:
  - evidence rows baseline: `1581`
  - completed-month coverage baseline: `330`
  - missing full-chart rows with ASIN baseline: `1251`
- Live proof window baseline (`2026-04-18T20:33:29Z`):
  - evidence rows: `4598`
  - completed-month rows: `2241`
  - replay-basis rows: `2354`
  - missing full-chart rows with ASIN: `2244`
- After run and rebuild (`2026-04-18T21:20:26Z`):
  - evidence rows: `4598` (`delta=0`)
  - completed-month rows: `2264` (`delta=+23`)
  - replay-basis rows: `2379` (`delta=+25`)
  - missing full-chart rows with ASIN: `2219` (`delta=-25`)
- Health:
  - `f_backtest_demand_basis_integrity`: `ok`
  - `f_backtest_manual_review_share`: `ok` (`0.086477`)
  - `f_backtest_health_staleness`: `warn` (`stale_sources:input_view|replay_daily|summary`)

## Required status language
- `code fix applied`
- `isolated verification passed`
- `live subset recovery proof completed`
- Phase 3 status:
  - not started in this ticket
  - gate decision deferred to next batch package
