# O Restocking Todo

Created: 2026-05-26
Owner flow: O
Business purpose: reorder existing profitable products and stop stock gaps.
Last plan comparison: 2026-05-26
Current next phase: Phase 1 - Clear the price-proof blocker before deeper PO, receiving, or send-to-Amazon work.

## Source Plans To Read First

- `project_control/OPERATIONS_LOOP_RESTOCK_IMPLEMENTATION_PLAN_2026-04-03.md`
- `project_control/OPERATIONS_LOOP_RESTOCK_BLUEPRINT_2026-04-03.md`
- `project_control/O_REORDER_BOARD_BLUEPRINT.md`
- `project_control/O_REORDER_INPUT_RULES.md`
- `project_control/EXPECTATIONS/operations_loop_expectations.md`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`
- `plans/active/o-net-fee-restock-bridge-2026-05-19/CODING_PLAN.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/PLAN_STATUS.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/RESTOCK_OVERALL_PLAN_2026-04-28.md`

## Current Evidence

- Restock source view: 608 rows, last modified 2026-05-23.
- Restock recommendations: 608 rows, last modified 2026-05-23.
- Restock profit checks: 608 rows, last modified 2026-05-23.
- Reorder input coverage: 608 rows, with `action_ready_now=0` for all rows.
- Market-refresh candidates: 59 rows, all `candidate_status=ready`.
- Legacy purchase list bridge: 72 rows, split as 51 Restock, 18 No Data, and 3 Drop.
- Purchase orders: 2 header/order rows and 9 PO line rows.
- Purchase order line source mix: 1 `test` line and 8 `legacy_sheet` lines.
- Ordered stock state: 1 sample/test row.
- Receiving events: 3 `phase4_test` rows.
- Send-to-Amazon queue: 0 rows.
- Current active price-proof plan is blocked because H isolation was required before a candidate-only market scan.

## Plain-English Finish Line

The reorder system is finished for v1 when the user can:

1. Open Restock.
2. See supplier-first work, not a mixed product mess.
3. Know whether a supplier is worth ordering from today.
4. Confirm final order quantity and confirmed unit cost.
5. Produce a PO draft or see a clear reason why the row is held.
6. Later record receiving and send-to-Amazon state without manual spreadsheet copying.

## Phase 0 - Research And Tidy The Existing Restock Plans

- [x] Compare the April restock implementation plan against the May O plans.
- [x] Mark each old phase as `done`, `partly done`, `still needed`, or `obsolete`.
- [x] Confirm whether `purchase_orders_live.csv` and `purchase_order_lines_live.csv` are real operator-ready PO drafts or sample/bridge outputs.
- [x] Confirm whether the 72 legacy bridge rows are still the operator source of truth for current buying.
- [x] Confirm why native O can still disagree with Sheet source and list the exact fields causing disagreement.

Proof to collect:
- file row counts: collected on 2026-05-26 by read-only local CSV inspection.
- latest output timestamps: collected from local file metadata.
- exact field mismatch examples: collected for SKU `12-749B-9EB5`.

Phase 0 decision from 2026-05-26:

| April phase | Current status | Decision |
| --- | --- | --- |
| Phase 0 - Foundations | done | Keep. O paths, schemas, source contracts, scripts, and tests exist. |
| Phase 1 - Restock Advisor Data | partly done | Keep. O001/O002/O003 and 608-row outputs exist, but native O currently produces 608 `wait` recommendations and 0 action-ready rows. |
| Phase 2 - Human Decision Capture | partly done | Keep. O010 and decision event flow exist, but current proof still relies on sample and legacy bridge paths. |
| Phase 3 - Minimal UI | partly done | Keep the thin-UI rule, but use the newer supplier-first reorder board blueprint for the actual UI shape. |
| Phase 4 - Purchase Orders | partly done | Keep. O100 can create draft rows, but current PO files are mixed proof output: 1 test line and 8 legacy-sheet lines, not fully native operator-ready PO truth. |
| Phase 5 - Ordered Stock And Receiving | partly done | Keep. O200/O210 artifacts exist with sample/test evidence only; no live receiving lane is proven. |
| Phase 6 - Send To Amazon Handoff | still needed | Keep. Queue file exists but has 0 rows, so no received-stock-to-Amazon handoff is proven. |
| Phase 7 - Runtime Cadence And Evidence | blocked | Keep for later. O runner files exist, but cadence should not become the main work until native price proof, supplier readiness, PO, and receiving states are safe. |

Old or replaced plan noise:

- Old Google Sheets formula logic is obsolete as core logic.
- Old checkbox and delete-row history behavior is obsolete as durable workflow state.
- The legacy Purchase List is useful only as a temporary bridge and operator reference until native O parity is proven.
- The old idea of building UI first is obsolete; the current path is data proof first, UI as a thin operator layer.

Native O versus Sheet bridge mismatch example:

- SKU `12-749B-9EB5` is `Restock` in the legacy bridge with `recommendation_status=full_restock`, `market_price_basis_used=LEGACY_PURCHASE_LIST_ROI_BACKSOLVE`, `forward_roi_pct=36`, and `bridge_note=LEGACY_PURCHASE_LIST_RESTOCK|NATIVE_O_PARITY_PENDING`.
- The native O recommendation for the same SKU is `wait`, with `market_price_gbp` blank, `net_fee_model_status=missing`, `recommended_qty_rounded=0`, and reason codes `SUPPLIER_COST_USER_CONFIRMATION_REQUIRED,LOW_CONFIDENCE_MARKET_CONTEXT,SALE_STATUS_NOT_ACTIVE`.
- The market-refresh queue names the missing proof as `legacy_sheet_market_not_native|missing_native_max_pay|missing_native_fee_model|legacy_sheet_requires_native_market_proof`.

Next safe goal:

- Continue with `GOAL_O-003_clear_market_refresh_blocker.md`.
- Do not build deeper PO, receiving, or send-to-Amazon behavior until the 59-row market-proof blocker is classified and either cleared or parked.

## Phase 1 - Clear The Price-Proof Blocker

- [ ] Decide whether H can be safely paused for the 59-row candidate-only listing-offer scan.
- [ ] If H cannot be paused safely, write the exact reason and park the O market-refresh proof.
- [ ] If H can be paused, run the already planned read-only proof only after approval.
- [ ] Rebuild only the safe local E/O proof chain after the scan.
- [ ] Keep any row without native market proof visible as `check price`, not buy-ready.

Success condition:
- The 59 queued restock candidates either receive native market proof or stay blocked with a plain missing-data reason.

## Phase 2 - Finish Supplier-First Reorder Readiness

- [ ] Lock supplier-worth fields: minimum order, free-delivery threshold, delivery charge, VAT basis, stock source, cadence, friction.
- [ ] Add or verify supplier readiness states: `Ready`, `Building`, `Needs Stock Check`, `Snoozed`, `All`.
- [ ] Make supplier badge count suppliers ready for review, not product rows.
- [ ] Ensure shipping allocation is by line value unless a supplier-specific exception exists.

Success condition:
- The system can explain why a supplier is ready today or not worth attention today.

## Phase 3 - Finish Pack And Quantity Truth

- [ ] Finish pack-aware blocker reporting from `o-restock-pack-and-db-through-use-v1`.
- [ ] Make missing pack truth explicit: missing quantity mode, sell pack qty, supplier case qty, invalid conversion.
- [ ] Keep real-SKU onboarding blocked until the blocker reporting pass is finished.
- [ ] Use a small approved real-SKU sample only after user approval.

Success condition:
- The user does not need mental maths for pack, case, bundle, or repack quantities.

## Phase 4 - Finish PO Draft Path

- [ ] Verify O010 decision events are append-only and safe.
- [ ] Verify O100 turns approved rows into PO draft lines or held reasons.
- [ ] Verify confirmed unit cost above Max pay is blocked before PO draft creation.
- [ ] Verify supplier basket totals reconcile from line data.

Success condition:
- Every approved buy is either in a PO draft or held with a reason the user understands.

## Phase 5 - Receiving And Send-To-Amazon

- [ ] Confirm ordered stock affects effective supply.
- [ ] Confirm partial receipts reduce open quantity correctly.
- [ ] Confirm send-to-Amazon queue only receives received stock.
- [ ] Confirm shipment references survive reruns.

Success condition:
- A buy can be traced from recommendation to PO to receipt to send-to-Amazon queue.

## Stop Conditions

Stop before changing anything if:

- Google Sheets would be written
- local DB would be aligned to Sheet or vice versa
- H is active and the proof needs H-owned market files
- the row source of truth is unclear
- a supplier business rule is unknown
