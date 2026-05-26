# Operations Loop Restock Implementation Plan

## 1. Purpose

This document turns the restock blueprint into a practical build order for SellerOne.

It answers:
- what gets built first
- what scripts should exist
- what each phase owns
- what should be tested before moving on
- when the UI should appear

This is the execution map for Codex.
The blueprint remains the business and logic reference.

Reference:
- `project_control/OPERATIONS_LOOP_RESTOCK_BLUEPRINT_2026-04-03.md`
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/EXPECTATIONS/operations_loop_expectations.md`

## 2. Core Build Rule

Build this system in this order:

1. data contracts
2. source merge
3. recommendation engine
4. human decision capture
5. PO state
6. receiving state
7. send-to-Amazon handoff
8. UI polish and runtime cadence

Do not start with the UI.
The old attempt already proved that a nice interface without settled data contracts slows everything down.

## 3. Implementation Shape

Recommended new flow family:
- `scripts/flows/O/`

Recommended output home:
- `out/systems/O/live/`
- `out/systems/O/history/`
- `out/systems/O/inbox/`

Recommended cycle wrapper only after phases 1 to 2 are stable:
- `scripts/run_O_cycle.py`

Recommended shared helper modules inside `scripts/flows/O/`:
- `_paths.py`
- `_schemas.py`
- `_source_contracts.py`
- `_supplier_rules.py`
- `_lead_time.py`
- `_demand_confidence.py`
- `_recommendation_engine.py`
- `_po_engine.py`
- `_receiving_engine.py`
- `_send_to_amazon_engine.py`

These helpers should hold the repeatable logic.
The numbered scripts should stay as thin orchestration steps.

## 4. Phase Order

## 4.1 Phase 0 - Foundations

Purpose:
- create the O flow structure
- lock output paths
- lock schemas
- lock fixture data for tests

Files to introduce first:
- `scripts/flows/O/__init__.py`
- `scripts/flows/O/_paths.py`
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/_source_contracts.py`

Outputs to define:
- `out/systems/O/live/restock_source_view.csv`
- `out/systems/O/live/restock_recommendations_live.csv`
- `out/systems/O/live/restock_review_queue.csv`
- `out/systems/O/live/restock_decisions_log.csv`
- `out/systems/O/live/restock_review_log.csv`
- `out/systems/O/live/purchase_orders_live.csv`
- `out/systems/O/live/purchase_order_lines_live.csv`
- `out/systems/O/live/receiving_events.csv`
- `out/systems/O/live/ordered_stock_state.csv`
- `out/systems/O/live/send_to_amazon_queue.csv`
- `out/systems/O/live/supplier_profiles.csv`
- `out/systems/O/live/supplier_lead_time_history.csv`

Tests in this phase:
- path tests
- schema tests
- required-column contract tests
- basic fixture load tests

Recommended test files:
- `tests/test_o000_paths_and_schemas.py`
- `tests/test_o000_source_contracts.py`

Phase 0 proof:
- all declared output schemas exist in one place
- every new O file has a defined owner and purpose
- test fixtures cover normal, edge, and bulk cases

## 4.2 Phase 1 - Restock Advisor Data

Purpose:
- merge the current truth sources into one restock-ready source view
- calculate recommendation outcomes
- build a human-facing queue

Scripts:
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O002_build_restock_recommendations.py`
- `scripts/flows/O/O003_build_restock_review_queue.py`

What each script should do:

`O001_build_restock_source_view.py`
- read from A, B, E, H, and interim supplier sources
- join one row per active SKU
- keep source columns explicit
- do not overwrite source truth
- calculate helper fields needed by O002 only if they are O-owned derivations

`O002_build_restock_recommendations.py`
- calculate effective supply
- calculate target cover
- calculate forward ROI using current supplier cost and current price context
- apply bulk-long-lead rules
- apply stale-demand confidence rules
- apply snooze filtering
- output recommendation labels and reasons

`O003_build_restock_review_queue.py`
- turn recommendation rows into a cleaner operator view
- group by supplier
- include action-ready fields
- include suggested quantity, suggested cost, expected ROI, days left, and reason

Phase 1 tests:
- source-join coverage tests
- recommendation label tests
- ROI band tests
- snooze date tests
- test-spend cap tests
- MOQ and pack rounding tests
- bulk-long-lead classification tests
- out-of-stock confidence downgrade tests
- supplier profile shipping-threshold tests

Recommended test files:
- `tests/test_o001_restock_source_view.py`
- `tests/test_o002_restock_recommendations.py`
- `tests/test_o003_restock_review_queue.py`

Phase 1 proof:
- every recommendation row has one clear status and one clear reason
- every recommended quantity can be traced back to demand, supply, and supplier rules
- no new copied helper tables are introduced outside O-owned state

## 4.3 Phase 2 - Human Decision Capture

Purpose:
- turn recommendations into durable workflow state
- keep recommendation history and human overrides visible
- support price confirmation and date-based snooze

Scripts:
- `scripts/flows/O/O010_apply_restock_decisions.py`
- `scripts/flows/O/O020_build_restock_review_log.py`

Recommended input pattern:
- UI or admin actions write into `out/systems/O/inbox/restock_decision_events.csv`
- `O010` validates and applies those events into live state

`O010_apply_restock_decisions.py`
- validate decision action rows
- require confirmed price before commitment paths
- recalculate path after confirmed price
- append to `restock_decisions_log.csv`
- never delete prior recommendation or decision rows

`O020_build_restock_review_log.py`
- build the later scorecard from prior decisions and later outcomes
- this is the evidence layer for tuning thresholds later

Phase 2 tests:
- append-only decision log tests
- duplicate event handling tests
- price-confirmation downgrade tests
- snooze-until-date tests
- override lineage tests
- review-log outcome-calculation tests

Recommended test files:
- `tests/test_o010_apply_restock_decisions.py`
- `tests/test_o020_restock_review_log.py`

Phase 2 proof:
- every action taken by the user becomes one durable decision record
- confirmed price changes the final path when economics move
- snoozed SKUs disappear and then reappear on schedule

## 4.4 Phase 3 - Minimal UI

Purpose:
- add a simple page only after the underlying data and decision flow are stable

UI rule:
- phase 3 UI is a thin layer over O003 and O010
- it should not contain core business logic

Recommended first UI screens:
- Restock Review
- Supplier Group View
- Snoozed Items
- Bulk Review

Actions to support first:
- approve
- test buy
- wait
- bulk review
- snooze until date
- skip

UI tests:
- read-only load test for queue data
- action submission test into inbox file or endpoint
- simple filtering and grouping tests

Recommended test files:
- `tests/test_o030_restock_ui_contract.py`

Phase 3 proof:
- user can work from the page without reading raw CSVs
- actions still land in the same O-owned decision log
- no decision logic lives only in the UI

## 4.5 Phase 4 - Purchase Orders

Purpose:
- convert approved decisions into formal supplier order state
- factor in shipping thresholds, MOQ, and supplier basket logic

Scripts:
- `scripts/flows/O/O100_build_purchase_orders.py`
- `scripts/flows/O/O105_apply_po_confirmations.py`
- `scripts/flows/O/O110_publish_purchase_order_view.py`

`O100_build_purchase_orders.py`
- group approved lines by supplier
- apply supplier profile rules
- calculate draft basket totals
- show shipping effect at basket level
- hold lines that still need bulk-price confirmation

`O105_apply_po_confirmations.py`
- capture final supplier-side commercial truth
- confirmed prices
- confirmed expected arrival dates
- confirmed backorder or in-stock status

`O110_publish_purchase_order_view.py`
- build the operator-facing PO view
- write `purchase_orders_live.csv`
- write `purchase_order_lines_live.csv`

Phase 4 tests:
- supplier grouping tests
- shipping-threshold tests
- free-shipping threshold tests
- backorder allowed vs not allowed tests
- bulk-discount review tests
- final price confirmation propagation tests

Recommended test files:
- `tests/test_o100_purchase_orders.py`
- `tests/test_o105_po_confirmations.py`
- `tests/test_o110_purchase_order_view.py`

Phase 4 proof:
- every approved buy can be traced into one PO line or one held reason
- supplier basket economics are visible before PO commit
- price confirmation updates line economics before final PO status

## 4.6 Phase 5 - Ordered Stock And Receiving

Purpose:
- make supplier-ordered stock count as pipeline stock
- learn real lead times from order-to-arrival history

Scripts:
- `scripts/flows/O/O200_build_ordered_stock_state.py`
- `scripts/flows/O/O210_apply_receiving_events.py`
- `scripts/flows/O/O220_build_supplier_lead_time_history.py`

`O200_build_ordered_stock_state.py`
- summarize open supplier orders
- expose remaining open quantities by SKU
- feed ordered-not-yet-arrived state back into restock supply calculations

`O210_apply_receiving_events.py`
- apply receipts
- update received qty and remaining open qty
- move received units into ready-for-send state

`O220_build_supplier_lead_time_history.py`
- learn lead time from order timestamp to arrival timestamp
- split in-stock and backorder lead times
- prefer SKU history first, supplier history second

Phase 5 tests:
- partial receipt tests
- over-receipt rejection tests
- open-qty rollforward tests
- lead-time split tests
- mixed-history fallback tests
- supplier-order-counted-as-stock tests

Recommended test files:
- `tests/test_o200_ordered_stock_state.py`
- `tests/test_o210_receiving_events.py`
- `tests/test_o220_supplier_lead_time_history.py`

Phase 5 proof:
- once a PO is open, its quantities appear in pipeline supply
- once units are received, open qty drops correctly
- lead-time history reflects real order and arrival records

## 4.7 Phase 6 - Send To Amazon Handoff

Purpose:
- move received stock into the Amazon inbound workflow cleanly
- keep the order of operations strict so shipment data is not lost

Scripts:
- `scripts/flows/O/O300_build_send_to_amazon_queue.py`
- `scripts/flows/O/O310_execute_send_to_amazon_handoff.py`
- `scripts/flows/O/O320_sync_send_to_amazon_state.py`

Critical rule for this phase:
- follow the AMZ Manager 1 lesson exactly
- shipment planning must exist before carton and content detail is finalized
- the order of operations matters more than the UI here

`O300_build_send_to_amazon_queue.py`
- identify received stock ready for send
- build queue rows by SKU and source PO

`O310_execute_send_to_amazon_handoff.py`
- create the draft handoff state
- persist shipment references
- only then allow pack and content steps

`O320_sync_send_to_amazon_state.py`
- sync later shipment state back into O-owned workflow rows
- keep receiving, ordered stock, and send queues aligned

Phase 6 tests:
- queue eligibility tests
- duplicate handoff prevention tests
- shipment-reference persistence tests
- step-order contract tests
- re-run safety tests

Recommended test files:
- `tests/test_o300_send_to_amazon_queue.py`
- `tests/test_o310_send_to_amazon_handoff.py`
- `tests/test_o320_send_to_amazon_state_sync.py`

Phase 6 proof:
- received stock enters send queue once
- shipment reference survives reruns
- handoff state can be resumed without rebuilding from scratch

## 4.8 Phase 7 - Runtime Cadence And Evidence

Purpose:
- give O a repeatable runner only after the data path is stable

Files:
- `scripts/run_O_cycle.py`
- internal cycle runner matching existing A/B/E/H patterns

Recommended first task list for the runner:
- O001
- O002
- O003
- O010
- O020
- O100
- O110
- O200
- O210
- O220
- O300

Runner rule:
- do not create the cycle runner until the individual steps already pass in isolation

Phase 7 tests:
- task-order tests
- manifest-write tests
- rerun-safety tests
- phase-skip safety tests

Recommended test files:
- `tests/test_o_cycle_runner.py`
- `tests/test_o_manifest_contract.py`

## 5. UI Rollout Rule

The UI should be introduced in layers:

1. read-only queue view
2. action submission for decision capture
3. PO confirmation page
4. receiving page
5. send-to-Amazon page

This keeps the UI simple and keeps the data model in charge.

## 6. Test Strategy

Use three levels of testing.

### Level 1 - Rule tests

Small fixture-driven tests for:
- ROI bands
- cover-day logic
- shipping thresholds
- MOQ rounding
- snooze rules
- demand-confidence downgrades
- lead-time split logic

### Level 2 - Contract tests

Tests that check:
- required columns exist
- types are sensible
- append-only logs stay append-only
- IDs and references stay joinable

### Level 3 - Phase integration tests

Small end-to-end fixtures that run several O scripts in sequence and confirm:
- recommendation -> decision -> PO -> receiving -> send queue lineage

Recommended fixture packs:
- normal fast mover
- tight-margin test restock
- stale out-of-stock SKU
- bulk-long-lead SKU
- backorder-only SKU
- free-shipping-threshold supplier basket

## 7. What Should Be Proven Before Each Phase Is Marked Ready

### Phase 1 readiness
- source rows reconcile to the active SKU universe
- recommendation rows reconcile to the source view
- each recommendation has status, quantity, and reason

### Phase 2 readiness
- every human action creates one durable record
- no decision silently overwrites prior history
- price-confirmation logic changes the path when needed

### Phase 4 readiness
- approved lines become PO lines or a clear held reason
- supplier basket totals reconcile from line data

### Phase 5 readiness
- open supplier quantities appear in effective supply
- receipts reduce open quantities correctly

### Phase 6 readiness
- received units flow into send queue once
- shipment references remain stable across reruns

## 8. Recommended Ticket Split

Keep the implementation in separate tickets.

Ticket 1:
- Phase 0
- Phase 1

Ticket 2:
- Phase 2
- minimal UI read and action path

Ticket 3:
- Phase 4

Ticket 4:
- Phase 5

Ticket 5:
- Phase 6

Ticket 6:
- Phase 7 runner and cadence

This is the safest split because each ticket adds one more durable workflow layer without forcing the whole loop into one risky jump.

## 9. Bottom Line

The clean real-world implementation order is:

1. build O data contracts
2. build the recommendation engine
3. build decision capture
4. add a thin UI
5. build PO state
6. build receiving state
7. build send-to-Amazon handoff
8. add the cycle runner last

If this order is followed, the system grows from trustworthy data outward.
If this order is ignored and the UI or Amazon handoff is pushed too early, the project will slow down and the data model will get muddy again.
