# Execution Batch 002 - Complete

## Purpose
Implement the O-side supplier buy-cost bridge, discount confirmation queue, and max purchase price guard for the stock decider.

## Approval Status
Approved by user messages: `approve` and `proceed with all phases`.

## Completed Work
- Added O output `supplier_buy_cost_truth.csv`.
- Added O output `supplier_cost_confirmation_queue.csv`.
- Wired the O source view to use expected supplier cost from the cost bridge.
- Wired O recommendations to carry max break-even purchase price, max target-ROI purchase price, target ROI percent, purchase-price safety status, and user price-check fields.
- Wired O review queue and O020 readiness report to carry the same cost-confirmation fields.
- Blocked action-ready readiness when supplier cost confirmation is still required.
- Kept Google Sheets and Product DB writes out of scope.
- Did not run O purchase-order or decision-apply steps during proof.

## Files Touched
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/_source_contracts.py`
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O002_build_restock_recommendations.py`
- `scripts/flows/O/O003_build_restock_review_queue.py`
- `scripts/flows/O/O007_build_supplier_buy_cost_truth.py`
- `scripts/flows/O/O008_build_supplier_cost_confirmation_queue.py`
- `scripts/flows/O/O020_build_reorder_input_coverage_report.py`
- `scripts/cycles/run_O_cycle.py`
- O and F targeted tests
- this plan folder

## Proof
- `python -m py_compile scripts\flows\O\_schemas.py scripts\flows\O\_source_contracts.py scripts\flows\O\O001_build_restock_source_view.py scripts\flows\O\O002_build_restock_recommendations.py scripts\flows\O\O003_build_restock_review_queue.py scripts\flows\O\O007_build_supplier_buy_cost_truth.py scripts\flows\O\O008_build_supplier_cost_confirmation_queue.py scripts\flows\O\O020_build_reorder_input_coverage_report.py scripts\cycles\run_O_cycle.py`
- Contract/runner/new-output tests: 15 passed.
- O bridge behavior tests: 22 passed.
- F source-shape regression tests: 76 passed.
- O test pack: 147 passed.
- Focused O proof rebuilt O007, O008, O001, O002, O003, O004, and O020.

## Latest Local Output Evidence
- `supplier_buy_cost_truth.csv`: 608 rows.
- Price-list match rows: 87.
- Expected-cost rows: 196.
- User price-check required rows: 538.
- `supplier_cost_confirmation_queue.csv`: 538 rows.
- `restock_recommendations_live.csv`: 608 rows, with 602 wait and 6 full_restock.
- `reorder_input_coverage_report.csv`: 608 rows.
- Action-ready rows: 6.
- Action-ready rows still requiring user price check: 0.

## Proof Artifacts
- Before-write rollback snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/o_live_backup_before_phase2_20260519T122526Z`
- Proof snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/phase2_to_5_o_cost_bridge_20260519T123903Z`
- Proof summary: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/phase2_to_5_o_cost_bridge_20260519T123903Z/proof_summary.md`

## Open Decision After This Batch
- The bad TD Synnex F live active run is still blocked by the F guard.
- Replacing or quarantining that live F active run needs a separate decision because it changes live F queue state.
