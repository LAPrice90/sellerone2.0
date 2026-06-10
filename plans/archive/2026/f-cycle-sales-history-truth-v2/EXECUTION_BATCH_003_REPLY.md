# Execution Batch 003 Reply

## Status
- Complete / Partial / Failed:
  - complete
- Checked against:
  - `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_003.md`

## Summary of work done in this hometime window
- Hardened qualification at the earliest owner stage (`F071`) with explicit component contract fields:
  - market gate state and factor
  - Amazon pressure factor
  - buy-box coverage factor
  - maturity factor
  - final qualification factor
  - zero or block reason
- Propagated qualification truth through replay and summary:
  - replay carries qualification fields and explicit value-source tag
  - summary writes explicit `expected_units_source` and `expected_profit_source`
  - READY rows no longer silently rely on replay fallback when qualified input truth is missing
- Extended health and validation proof:
  - `F074` validates component presence, factor consistency, and source alignment
  - `F005` now exposes raw vs qualified delta and qualification reason path

## Isolated verification
- command:
  - `pytest tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f005_build_sales_history_validation_audit.py`
- result:
  - `43 passed`
- compile check:
  - `python -m py_compile` passed for all changed F scripts and changed tests

## Controlled proof window
- owner handoff:
  - paused live owner path before rebuild
  - resumed owner path after proof
- unchanged-input boundary:
  - `feeder_legacy_scrape_evidence_live.csv` hash remained unchanged during proof:
    - `E38EE98FC4EA278CF41F4CCEAED7C6C737FA8D1DFB2ACA2CB20CCD429EA3E481`

## Rebuild proof
- commands:
  - `python -m scripts.flows.F.F070_build_backtest_policy_snapshot`
  - `python -m scripts.flows.F.F071_build_backtest_input_view`
  - `python -m scripts.flows.F.F072_run_backtest_replay`
  - `python -m scripts.flows.F.F073_build_backtest_summary`
  - `python -m scripts.flows.F.F074_build_backtest_health`
  - `python scripts/one_off/F004_build_bbp_sales_sample_audit.py`
  - `python scripts/one_off/F005_build_sales_history_validation_audit.py`
  - `python -m scripts.flows.F.F074_build_backtest_health` (final staleness-close rerun)
- output counts:
  - `F070`: rows `1`
  - `F071`: rows `2364` (`ready=2158`, `manual_review=206`)
  - `F072`: rows `772366`
  - `F073`: rows `2364` (`ready=2158`, `manual_review=206`, `decision_fail=1890`, `decision_pass=268`)
  - `F074`: rows `17` (`ok=17`, `warn=0`, `fail=0`)
  - `F004`: rows `18`, mismatch rows `2`
  - `F005`: rows `28764`, trusted rows `2270`, qualified-delta rows `28540`

## Health and source-alignment proof
- `f_backtest_demand_basis_integrity`: `ok`
- `f_backtest_price_qualified_demand_integrity`: `ok`
- `f_backtest_qualification_source_alignment`: `ok`
- `f_backtest_health_staleness`: `ok`
- READY summary source alignment:
  - READY rows: `2158`
  - `expected_units_source=input_qualified`: `2158`
  - `expected_profit_source=input_qualified`: `2158`
  - READY rows with blank qualification components: `0`

## Owner-state proof after completion
- canonical queue rows for `stocklist_supplier`:
  - `42663`
- loop owner resumed and active:
  - `cmd.exe /c run_F_supplier_full_legacy_scan.bat stocklist_supplier`
  - child:
    - `python ... F061_run_legacy_first_checks_local.py --supplier-id stocklist_supplier --max-rows 5 --loop`

## Required status language
- `code fix applied`
- `isolated verification passed`
- `controlled Phase 3 proof completed`
- Phase 4 status:
  - not started in this ticket
  - now eligible for Batch 004 execution packaging
