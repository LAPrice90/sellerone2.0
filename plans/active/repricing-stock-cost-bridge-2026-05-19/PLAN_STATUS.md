# Plan Status

## Summary
- Plan slug: `repricing-stock-cost-bridge-2026-05-19`
- Current stage: Phase 2-5 O cost bridge implemented and locally proven
- Current phase: Phase 5 - small real-SKU proof completed for current O live file set
- Current batch: Batch 002
- Overall status: O stock-decider cost bridge complete; F TD Synnex active-run replacement still needs a separate data-state decision
- Monitoring window: none
- Next check UTC: none
- Unlock condition: user chooses whether to quarantine/replace the bad TD Synnex active run
- Timeout action: none
- Notification mode: milestone only
- User interruption threshold: approval required before replacing live F active-run rows

## Checklist
- [x] Project brief written
- [x] Research report written
- [x] Plan written
- [x] Coding plan written
- [x] Batch 001 ready
- [x] Batch 001 complete
- [x] Batch 002 ready
- [x] Batch 002 complete
- [x] Runbook written
- [ ] Ready to archive

## Open blockers
- TD Synnex live active F run is still `fpm_td_synnex_20260519T090704Z`, now blocked by `blocked_source_shape_guard`.
- Replacing or quarantining the 43,039-row bad TD Synnex active run needs explicit user decision because it changes live F queue state.
- O cost bridge now has 608 rows, but only 90 rows currently have a matched F price-list row.
- O restock recommendations were rebuilt locally for cost/readiness proof; purchase-order and decision-apply steps were not run.
- Product DB SQL authority exists, but O restock still reads `out/product_db_preview.csv` for the cost source.
- The target ROI policy is currently set to 10 percent for max purchase price calculations.

## Latest proof snapshot
- Date: 2026-05-19
- Evidence:
  - Phase 2-5 O proof snapshot folder: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/phase2_to_5_o_cost_bridge_20260519T123903Z`.
  - Before-write O rollback snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/o_live_backup_before_phase2_20260519T122526Z`.
  - O focused proof completed: O007, O008, O001, O002, O003, O004, and O020.
  - O test pack passed: 147 tests.
  - O cost bridge tests passed: 15 contract/runner/new-output tests and 22 behavior tests.
  - F source-shape regression tests passed: 76 tests.
  - `supplier_buy_cost_truth.csv`: 608 rows, 87 price-list matches, 196 expected-cost rows, 538 rows requiring user price check.
  - `supplier_cost_confirmation_queue.csv`: 538 rows.
  - Cost confidence counts: 412 none, 109 actual_paid_without_list_reference, 64 price_list_only, 12 discount_assumption_needs_confirmation, 6 price_list_actual_match, 5 actual_paid_above_list_needs_review.
  - `restock_recommendations_live.csv`: 608 rows, 602 wait, 6 full_restock.
  - Purchase safety counts: 301 missing_market_price, 244 missing_expected_cost, 62 within_target_roi_max, 1 above_break_even_max.
  - `reorder_input_coverage_report.csv`: 608 rows, 6 action-ready rows, 0 action-ready rows requiring user price check.
  - Phase 1A tests passed: 76 targeted FPM tests.
  - Old F owner drained at `2026-05-19T11:57:03Z`.
  - F supervisor restarted the owner as PID `6584` at `2026-05-19T11:58:21Z`.
  - Live status at `2026-05-19T11:58:50Z`: `state=blocked_source_shape_guard`, `active_supplier_id=td_synnex`, `active_f061_run_id=fpm_td_synnex_20260519T090704Z`, `pending_rows=43039`.
  - Blocked-state sleep was raised to a one-minute floor and the F owner was reloaded again.
  - Current owner after reload: PID `35404`, started `2026-05-19T12:03:36Z`, status `blocked_source_shape_guard`.
  - Live event rows show `source_shape_guard_blocked` with `td_synnex_supplier_title_numeric_like` count `42915`.
  - Proof snapshot folder: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/phase1_source_shape_guard_final_20260519T120528Z`.
  - H runtime artifacts are current, but health has 2 FAIL and 5 WARN.
  - F manager batch rows contain clean TD Synnex rows such as `supplier_sku=AP9815`, `supplier_title=UPS INTERFACE EXTENSION`, `unit_cost=30.93`.
  - F live active run currently shows shifted-looking TD rows such as `supplier_sku=ADDON NETWORKING`, `supplier_title=104.75`, `unit_cost=177.55`.
  - O source view has 608 rows, with 132 `last_purchase_price` costs and 476 missing costs.
  - O recommendations currently have 10 UI preview sample rows.

## Notes
- This plan intentionally fixes source truth before changing the stock decider.
- Phase 1A has stopped malformed TD Synnex rows from feeding F061 or O.
- O now reads clean F price-list manager batch rows, not the F061 active scanner queue.
- The F061 scanner should enrich/check rows; it is not treated as the daily source-acquisition owner for supplier price lists.
- Do not replace/quarantine the bad TD Synnex active F run without a separate backup and explicit choice of replacement strategy.
- Guidebook written: `project_control/O_SUPPLIER_BUY_COST_BRIDGE_GUIDEBOOK.md`.
