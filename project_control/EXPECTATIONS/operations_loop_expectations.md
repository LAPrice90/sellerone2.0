# Operations Loop Expectations

## Purpose
The Operations Loop is the next major connected system after core A/B/E/H. Its goal is to remove manual handoff across disconnected tools by connecting planning, approval, ordering, receiving, and send-to-Amazon flow in one loop.

## SECTION 1 - Completion Definition
| Feature | Description | Status | Notes |
|---|---|---|---|
| Restock Advisor | Generates actionable restock recommendations from live data | Not Started | Planned component |
| Human approval gate | Human approval step exists before commitment actions | Not Started | Planned decision-control step |
| Purchase order creation | Approved recommendations become tracked purchase orders | Not Started | Planned component |
| Ordered stock tracking | Ordered inventory state is tracked end-to-end | Not Started | Planned component |
| Inventory receiving | Received inventory is recorded and reconciled | Not Started | Planned component |
| Send To Amazon flow | Send-to-Amazon preparation and state tracking are integrated | Not Started | Planned component |
| Closed-loop feedback | Updated stock/order state feeds back into A/B/E foundation | Not Started | Planned loop closure requirement |
| Single workflow view | Operator can follow one connected workflow, not multiple tools | Not Started | Planned usability requirement |

## SECTION 2 - Reliability Measurement
Measure reliability over the last 10 completed loop runs after implementation:
- Fails: loop breaks, missing state transitions, or invalid approval-to-commit sequence.
- Warnings: partial completion, delayed transitions, or recoverable data quality issues.
- Clean runs: full loop completes with valid approval and state transitions.

Before runtime exists:
- Reliability Score = `To Baseline`.

Suggested scoring baseline (post-implementation):
- Start at 100.
- Subtract 25 if any loop integrity fail exists.
- Subtract 20 if approval gating is bypassed or ambiguous.
- Subtract 5 per warned run, up to 25.

## SECTION 3 - Acceptance Criteria
- Replacement Complete:
- Restock -> approval -> PO -> receiving -> send-to-Amazon loop is operational and connected.
- Human no longer performs manual data transfer across separate tools.
- Stable:
- No fail in last 10 loop runs.
- At least 8 of last 10 loop runs are clean.
- Approval and commitment lineage is auditable.
- Ready for expansion:
- Stable across 2 review windows.
- Supports optional direct PO generation enhancements from reorder flow.

## SECTION 4 - Improvement Backlog
These do not affect Completion Score:
- Advanced recommendation tuning and forecasting.
- Supplier-facing automation refinements.
- Richer operational dashboards and notifications.
- Additional external support systems feeding the loop.

## SECTION 5 - Phase 0 Readiness Note
- As of 2026-04-03, O Phase 0 contract scaffolding is in place:
- isolated `scripts/flows/O/` path/schema/source-contract modules exist
- isolated test fixtures and O000 contract tests exist
- no runtime runner or scheduler wiring has been introduced
- status table above remains unchanged because this is foundation-only work, not operational loop delivery

## SECTION 6 - Phase 1 Isolated Build Note
- As of 2026-04-03, O Phase 1 isolated Restock Advisor data path is now scaffolded:
- `O001_build_restock_source_view.py` builds `out/systems/O/live/restock_source_view.csv` from approved upstream sources
- `O002_build_restock_recommendations.py` builds `out/systems/O/live/restock_recommendations_live.csv` with first-pass full/test/wait logic
- `O003_build_restock_review_queue.py` builds `out/systems/O/live/restock_review_queue.csv` as operator-facing queue projection
- focused isolated tests now exist for O001/O002/O003 behavior and pass in fixture-driven runs
- no O cycle runner or scheduler wiring has been introduced in this phase
- completion status table above remains unchanged because this is isolated Phase 1 scaffolding, not full loop operation

## SECTION 7 - Product DB SQL Authority Note
- As of 2026-05-01, O Product DB operator view has a local SQL authority path:
- `O030_build_product_db_operator_view.py` prefers `out/sql/sellerone_dev.sqlite3:product_db_products` when present
- `P014_apply_product_db_edit_events.py` provides a dry-run-first local edit-event apply path for SQL plus mirror export
- `P015_product_db_sql_authority_rehearsal.py` proves SQL and O view agreement while showing whether the legacy CSV mirror is stale
- latest proof has SQL Product DB rows 659 and O Product DB operator rows 659
- the operations-loop completion table remains unchanged because this is Product DB foundation work, not the full restock-to-receiving loop

## SECTION 8 - Legacy Purchase List Bridge Note
- As of 2026-05-22, O has a read-only bridge from Google Sheet `Amazon Supplier Process` tab `Purchase List` into the reorder UI:
- `O009_build_legacy_purchase_list_bridge.py` reads the Sheet and writes local-only bridge outputs
- live bridge output: `out/systems/O/live/legacy_purchase_list_bridge.csv`
- live bridge health: `out/systems/O/live/legacy_purchase_list_bridge_health.csv`
- timestamped history snapshots are written under `out/systems/O/history/` for proof and rollback visibility
- `Done=TRUE` rows are excluded, and bridge rows keep `source_system=legacy_purchase_list`
- the reorder UI shows bridge rows first, then native O rows not already covered by bridge SKU or ASIN
- `O010_apply_restock_decisions.py` and `O100_build_purchase_orders.py` can convert bridge-approved UI rows into decision log rows and PO draft rows without depending on the stale native recommendation row
- latest read-only import proof at `2026-05-22T09:43:36Z` copied 72 bridge rows: 51 Restock, 18 No Data, and 3 Drop
- native O parity remains a follow-up fix because current native O can still disagree with the Sheet source
- the operations-loop completion table remains unchanged because this is a temporary bridge and PO-draft cutover step, not the full native Restock Advisor repair

## SECTION 9 - Reorder Price-Proof Completion Note
- As of 2026-05-23, O has a local-only Reorder price-proof layer:
- `O007_build_supplier_buy_cost_truth.py` now records supplier price-list movement and usual paid cost profiles
- `O021_build_restock_profit_checks.py` now carries current list cost, usual paid cost, Max pay, price status, and snooze recommendation evidence
- the Reorder UI shows compact price-proof chips and keeps detailed notes in hover panels
- every buy submission still requires a typed confirmed unit cost
- typed confirmed unit cost above Max pay is blocked in the UI submit path
- `O010_apply_restock_decisions.py` independently blocks over-Max commit events
- `O100_build_purchase_orders.py` holds over-Max decisions instead of creating PO draft lines
- latest local proof is `out/systems/O/history/reorder_price_proof_completion_20260523T110732Z/proof.md`
- latest read-only rebuild produced 608 profit-check rows and 259 health rows
- the operations-loop completion table remains unchanged because this is still a proof and guardrail layer, not full restock-to-receiving loop completion

## SECTION 10 - Reorder Market-Refresh Bridge Note
- As of 2026-05-23, O now writes a local market-refresh candidate queue for reorder rows that need current market proof before Max pay can be trusted:
- live queue: `out/systems/O/live/restock_market_refresh_candidates_live.csv`
- `O021_build_restock_profit_checks.py` creates this queue from rows with missing native market, missing native Max pay, or Sheet-only market evidence
- zero-cost rows are not sent to the market queue because cost confirmation is the first blocker
- `run_api_collection.py` can include ready O restock market candidates in the next read-only listing-offer collection
- active merchant listing rows still win if the same SKU appears in both the normal active listing scan and the O restock queue
- `scripts/phase1/phase1_sku_scope.py` now recovers missing ASIN identity from inventory summaries when Product DB and merchant listings are blank
- latest local proof produced 59 ready market-refresh candidates, including 8 ABGee rows and `12-749B-9EB5` with ASIN `B084HZRR8G`
- no Google Sheet, Amazon write, receiving, send-to-Amazon, O010, or O100 action is part of this step
- the operations-loop completion table remains unchanged because this is a proof-collection bridge, not the full restock-to-receiving loop

## SECTION 11 - Manager Readiness Mapping Note
- As of 2026-05-30, O is explicitly managed as mid-build, not as a finished live operations cycle.
- Current user-working readiness means the manager can prove a safe walkthrough of viewing, review, and decision-shaping only.
- User-working readiness does not mean purchase commitment, purchase order creation, receiving, send-to-Amazon, market scan, H pause, Sheet write, price change, queue edit, local DB alignment, output deletion, or business approval is allowed.
- Old-but-readable O active proof files may remain a visible MOT warning without blocking a user walkthrough. Missing, unreadable, short, or fail-stale proof remains a blocker.
- `Send To Amazon flow` and `Closed-loop feedback` remain not_started as full live-loop features.
- `Single workflow view` and `Pack and supplier readiness` remain not_verified until a dedicated O walkthrough proof and pack/supplier readiness proof exist.
- O/H market proof and H pause/resume remain parked until clean H maintenance controller install proof exists and a separate approved proof packet proves H ownership restoration afterward.
- Real unsafe blockers are still hard blockers: missing O UI files, missing or empty Product DB operator view, buy-ready rows without cost/market/net-fee/Max-pay proof, unlabeled PO draft sources, send-to-Amazon queue rows without receiving proof, H/O proof gates requiring Luke, or any action crossing the protected boundaries above.
