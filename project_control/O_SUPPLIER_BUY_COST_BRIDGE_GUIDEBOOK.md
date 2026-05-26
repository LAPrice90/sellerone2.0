# O Supplier Buy-Cost Bridge Guidebook

## Purpose
The O stock decider needs one clear expected buy cost before it recommends stock. This bridge turns supplier price-list data and actual purchase cost data into one O-owned cost truth file.

Think of it like a checkout rulebook:
- The supplier list says the shelf price.
- Our last purchase says what we actually paid.
- The bridge decides whether the next buy price can be trusted or needs a user check.

## Inputs
- `out/product_db_preview.csv`
  - Seller SKU, ASIN, supplier identity, catalog cost, and last purchase cost.
- `out/systems/F/price_list_manager/test_mode/batch_rows.csv`
  - Supplier price-list rows collected by the F price-list manager.
- `out/systems/F/price_list_manager/test_mode/price_list_batches.csv`
  - Batch freshness and source lineage for those price-list rows.

## Important Ownership Boundary
- The price-list manager gathers supplier price-list data.
- F061 scans or enriches rows after the source rows exist.
- O must not rely on F061 to download supplier price lists daily.
- O reads collected price-list manager rows and keeps F061 active-run scanner state out of the cost bridge.

## Outputs
- `out/systems/O/live/supplier_buy_cost_truth.csv`
  - One row per Product DB SKU.
  - Shows current list cost, actual paid cost, expected next cost, confidence, user-check flag, and source lineage.
- `out/systems/O/live/supplier_cost_confirmation_queue.csv`
  - Rows where a user should confirm the supplier cost assumption.
- `out/systems/O/live/restock_source_view.csv`
  - Carries expected supplier cost into O source rows.
- `out/systems/O/live/restock_recommendations_live.csv`
  - Carries max purchase price, target ROI, and cost-confirmation flags.
- `out/systems/O/live/reorder_input_coverage_report.csv`
  - Blocks action-ready rows when user cost confirmation is required.

## Discount Rules
- If the list cost and actual paid cost match, trust the current supplier list cost.
  - Example: old list GBP 2.00, actual paid GBP 2.00, new list GBP 2.50, expected next cost GBP 2.50.
- If actual paid cost is lower than list cost, apply the same discount ratio to the current list cost and require user confirmation.
  - Example: old list GBP 2.00, actual paid GBP 1.80, new list GBP 2.50, expected next cost GBP 2.25, user check required.
- If actual paid cost is higher than list cost, require user confirmation.
- If the current supplier list cost is missing, fall back only with reduced confidence and require user confirmation.

## Max Purchase Price Rules
- `max_break_even_purchase_price_gbp = market price - expected refund drag`
- `max_target_roi_purchase_price_gbp = max break-even purchase price / 1.10`
- Current target ROI is 10 percent.
- If expected next cost is above break-even max, O uses `above_break_even_max`.
- If expected next cost is above target-ROI max but below break-even max, O uses `above_target_roi_max`.
- If supplier cost confirmation is required, O020 does not allow the row to be action-ready.

## Safe Proof Sequence
Run this proof when testing cost bridge changes:

1. Back up `out/systems/O/live`.
2. Run:
   - `python -m scripts.flows.O.O007_build_supplier_buy_cost_truth`
   - `python -m scripts.flows.O.O008_build_supplier_cost_confirmation_queue`
   - `python -m scripts.flows.O.O001_build_restock_source_view`
   - `python -m scripts.flows.O.O002_build_restock_recommendations`
   - `python -m scripts.flows.O.O003_build_restock_review_queue`
   - `python -m scripts.flows.O.O004_build_restock_diagnostics`
   - `python -m scripts.flows.O.O020_build_reorder_input_coverage_report`
3. Do not run O010 or purchase-order steps for a cost bridge proof unless the user explicitly approves order-state changes.
4. Check:
   - `supplier_buy_cost_truth.csv` row count equals Product DB SKU row count.
   - every row has a cost confidence state.
   - discounted rows appear in `supplier_cost_confirmation_queue.csv`.
   - `reorder_input_coverage_report.csv` has zero action-ready rows where `user_price_check_required=1`.

## Latest Proof
- Proof snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/phase2_to_5_o_cost_bridge_20260519T123903Z`
- Action-ready rows: 6.
- Action-ready rows still requiring user price check: 0.
