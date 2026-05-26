# Master Endgame Checklist

Created: 2026-05-26
Mode: planning-only command center

## Plain-English Goal

SellerOne needs to stop being a half-finished machine and become a money-making operating system.

The cash-first order is:

1. Keep the core data machine stable enough to trust.
2. Finish restocking so existing products can be reordered confidently.
3. Finish the price-list scanner so new products can enter review.
4. Finish the new-product listing and Product DB promotion path.
5. Finish purchase orders, receiving, and send-to-Amazon so the workflow closes.

## Current Snapshot From Existing Files

Evidence read on 2026-05-26:

- `out/cycle_alerts/summary.csv`: A has 0 FAIL / 1 WARN, B has 0 FAIL / 0 WARN, E has 0 FAIL / 0 WARN, H has 9 FAIL / 15 WARN.
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`: F price-list manager is `blocked_storage_drift`.
- `out/systems/F/price_list_manager/live/storage_drift_report.csv`: blocking F drift is `feeder_legacy_chart_daily_raw_live`; CSV has 7437 rows, SQL has 34450 rows, SQL is newer.
- `out/systems/O/live/restock_source_view.csv`: 608 rows.
- `out/systems/O/live/restock_recommendations_live.csv`: 608 rows.
- `out/systems/O/live/restock_profit_checks_live.csv`: 608 rows.
- `out/systems/O/live/restock_market_refresh_candidates_live.csv`: 59 rows.
- `out/systems/O/live/legacy_purchase_list_bridge.csv`: 72 rows.
- `out/systems/O/live/purchase_orders_live.csv`: 2 rows.
- `out/systems/O/live/purchase_order_lines_live.csv`: 9 rows.
- `out/systems/O/live/send_to_amazon_queue.csv`: 0 rows.
- `out/housekeeping/storage_health.latest.csv`: `unclassified_scan_items` FAIL with value 281.

## Endgame Work Order

### Phase 0 - Organise And Freeze The Map

- [x] Create this command-center folder.
- [x] Create separate cycle checklist files.
- [ ] In the next planning pass, review each checklist file against its source plans and mark tasks as `keep`, `merge`, `drop`, or `needs proof`.
- [ ] Do not start coding from this command center until one cycle file has a clear phase and proof path.

Success condition:
- Every cycle has one readable checklist file.
- The next active implementation target is obvious.

### Phase 1 - Clear Current Blockers That Stop Money Work

- [ ] F scanner blocker: investigate `blocked_storage_drift` before trying to resume scanner work.
- [ ] H blocker: decide whether H must be stabilized before the O 59-row market-refresh proof.
- [ ] O blocker: resolve the blocked `O Reorder Price-Proof Completion Plan` path, which needs H isolation before the read-only market scan.
- [ ] A warning: classify duplicate stock receipt batches as business-safe, user cleanup, or source-data fix.
- [ ] Storage housekeeping FAIL: classify the 281 unclassified output families.

Success condition:
- F can scan again or the exact safe repair path is known.
- O can continue restock proof without colliding with H.
- No blocker is just sitting in chat.

### Phase 2 - Finish Restocking For Existing SKUs

Work file:
- `O_RESTOCKING_TODO.md`

Target outcome:
- The user can open a supplier-first reorder board, see whether a supplier is worth ordering today, confirm quantity and cost, and produce a clean PO draft or a clear hold reason.

Success condition:
- Restock rows explain cost, market price, ROI, Max pay, supplier threshold, and quantity/pack logic.
- Approved rows become PO draft rows or held rows with plain reasons.
- No Google Sheets write unless explicitly approved.

### Phase 3 - Finish Price-List Scanner And New Product Intake

Work file:
- `F_PRICE_LIST_SCANNER_TODO.md`

Target outcome:
- Supplier files turn into scanner batches, scanner batches turn into AI-gated New Product Review rows, and approved rows can move toward Product Listing Profile Review.

Success condition:
- Scanner is not blocked.
- Completed supplier runs build review packs only after readiness gates pass.
- New products do not enter Product DB or Amazon listing flows until review and profile gates pass.

### Phase 4 - Stabilize H Enough To Support Buying Decisions

Work file:
- `H_REPRICER_TODO.md`

Target outcome:
- H gives fresh market truth and pricing evidence without blocking O or creating stale FAIL noise.

Success condition:
- H scoped FAIL count is 0 or every remaining item has an approved non-blocking exception.
- Latest H terminal and publish evidence is fresh enough for restock support.

### Phase 5 - Keep A/B/E Core Truth Clean

Work files:
- `A_CYCLE_TODO.md`
- `B_CYCLE_TODO.md`
- `E_ANALYTICS_TODO.md`

Target outcome:
- A, B, and E keep feeding restock and pricing with trustworthy stock, order, token, cost, fee, ROI, and velocity truth.

Success condition:
- Scoped A/B/E checks remain 0 FAIL.
- Any WARN that remains is named, tracked, and non-blocking.

### Phase 6 - Close The Operations Loop

Work file:
- `O_RESTOCKING_TODO.md`

Target outcome:
- Restock approval flows into PO, receiving, ordered stock, and send-to-Amazon tracking.

Success condition:
- A real approved buy can be traced from recommendation to PO draft to received state to send-to-Amazon queue.

## Stop Conditions

Stop and ask before implementation if:

- a task requires Google Sheets writes
- a task requires Product DB live alignment
- a task requires Amazon live submit
- a task requires elevated H isolation
- a root cause is unclear and the next action would change source data
- a manual user business decision is needed, such as whether to buy a brand-approval invoice quantity

## Recommended Next Task

Start with `O_RESTOCKING_TODO.md`, but do not ignore the F scanner blocker. Restocking is the quickest path to cash because it works on products already in the business. F scanner/new products comes next once the scanner is unblocked.

