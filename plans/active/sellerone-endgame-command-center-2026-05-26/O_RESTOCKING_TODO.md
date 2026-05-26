# O Restocking Todo

Created: 2026-05-26
Owner flow: O
Business purpose: reorder existing profitable products and stop stock gaps.

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

- Restock source view: 608 rows.
- Restock recommendations: 608 rows.
- Restock profit checks: 608 rows.
- Market-refresh candidates: 59 rows.
- Legacy purchase list bridge: 72 rows.
- Purchase orders: 2 header/order rows and 9 PO line rows.
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

- [ ] Compare the April restock implementation plan against the May O plans.
- [ ] Mark each old phase as `done`, `partly done`, `still needed`, or `obsolete`.
- [ ] Confirm whether `purchase_orders_live.csv` and `purchase_order_lines_live.csv` are real operator-ready PO drafts or sample/bridge outputs.
- [ ] Confirm whether the 72 legacy bridge rows are still the operator source of truth for current buying.
- [ ] Confirm why native O can still disagree with Sheet source and list the exact fields causing disagreement.

Proof to collect:
- file row counts
- latest output timestamps
- exact field mismatch examples, not general comments

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

