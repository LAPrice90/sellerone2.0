# O Restock Session v1

## Manager Authority
- task_id: MGR_O_RESTOCK_SESSION_V1
- job_ref: O-RESTOCK-SESSION-LOCAL
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_o_mid_build_work
- luke_action_required: 0

## Plain-English Purpose
Build the first O restock-session lane so Luke can review supplier restock work from the UI instead of stitching together the old Purchase List, Product DB, supplier files, supplier websites, and manual notes.

This is not approval to create real purchase orders. It is approval to build the safe local UI/session layer that gathers proof, labels gaps, blocks unsafe rows, and records draft operator decisions.

## Boundary
- allowed_scope: O restock-session view, local proof model, UI review lane, reason-code model, supplier grouping, local draft decision capture, session health proof, tests, and manager/MOT check coverage.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no local DB alignment; no real purchase order; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no automatic Product DB status change from walkthrough notes; no scope widening.
- proof_required: Retest with targeted O UI/session tests and `python -m sellerone_manager.app --hourly-mot --mot-flow O`; confirm O remains user-working only, with no buy/PO/receiving/Amazon action enabled.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Keep the pre-edit plan backup `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.20260602T183149.bak.md`.
- stop_condition: Stop if implementation needs a protected action, a live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, real PO, receiving, Amazon handoff, or output deletion.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O410_product_database_ui.py` only if the restock session needs Product DB viewing links or labels
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/_paths.py`
- `scripts/flows/O/_contract_io.py` only for new O output contracts
- new `scripts/flows/O/O460_build_restock_session_view.py`
- new `scripts/flows/O/O461_build_restock_session_health.py` if a separate health builder is simpler
- `sellerone_manager/hourly_mot.py` only for an O restock-session readiness check
- `tests/test_o460_restock_session_view.py`
- `tests/test_o461_restock_session_health.py` if needed
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/O_RESTOCK_SESSION_V1_TASK_PACKET_20260602.md`

## Forbidden Files And Areas
- Do not change Google Sheets.
- Do not edit F061 queues or scanner queue state.
- Do not run or modify H pause/resume paths for this task.
- Do not run market proof scans.
- Do not run or expand `O010_apply_restock_decisions.py` for live decisions in this task.
- Do not run or expand `O100_build_purchase_orders.py` for real PO creation in this task.
- Do not touch O receiving or send-to-Amazon writers except to keep them blocked in tests if needed.
- Do not update Product DB facts to make the manual walkthrough look cleaner.

## What To Build
1. Create a local restock-session row model.
   - One row should represent one product needing restock review.
   - The row must show source class: `native_o`, `legacy_bridge`, `feeder_review_handoff`, or `manual_walkthrough_fixture`.
   - The row must show supplier, SKU, ASIN, title, supplier SKU, barcode, image if available, old suggested quantity, current proposed quantity, and source proof state.

2. Add supplier proof fields.
   - exact supplier SKU match state
   - barcode match state
   - title-only match state
   - supplier stock state
   - backorder state
   - missing from latest supplier file state
   - likely discontinued candidate state
   - fresh supplier file timestamp or `missing`

3. Add profit and confidence proof fields.
   - current supplier cost proof state
   - current Amazon price proof state
   - fee proof state
   - refund drag proof state
   - inbound or FBA-send cost proof state
   - expected profit per unit
   - expected ROI percent
   - demand confidence
   - action safety state

4. Add pack and order viability fields.
   - pack multiple
   - supplier MOQ
   - supplier order step
   - supplier order value contribution
   - supplier order viable yes/no/unknown
   - reason when order quantity is blocked or rounded

5. Add reason-coded operator states.
   - `order_qty_draft`
   - `snooze`
   - `drop`
   - `likely_discontinued`
   - `needs_fresh_supplier_scan`
   - `backorder_wait`
   - `already_ordered_or_paid`
   - `awaiting_supplier_shipment`
   - `supplier_moq_too_low`
   - `profit_too_low`
   - `proof_missing`

6. Add supplier session grouping.
   - ABGee, Bliss, CLF, Culpitt, DHB, and any future supplier should appear as grouped sessions.
   - The UI should show clean candidates separately from blocked, snoozed, missing-proof, and already-ordered rows.
   - Duplicate handoffs should collapse by supplier plus ASIN plus supplier SKU where possible.

7. Add local-only draft decision capture.
   - Draft decisions may be recorded as O-local event proposals.
   - They must not become purchase orders.
   - They must not write Sheets.
   - They must not update Product DB facts.
   - They must not mark receiving or send-to-Amazon.

8. Add a manager/MOT readiness check.
   - The check should prove the session files exist, have rows in fixture/local mode, have required source labels, and do not claim buy-loop completion.
   - The check should fail if a row is called buy-ready while required proof is missing.
   - The check should warn, not fail, when future stages are not started.

## Manual Walkthrough Lessons To Encode
- Fresh supplier proof outranks old Purchase List history.
- Exact supplier SKU or barcode match is required before a clean buy.
- Similar title is not enough to buy.
- Missing from a fresh supplier file should become likely discontinued candidate, not automatic discontinued.
- Supplier stock zero needs a separate backorder state.
- Profit must use current cost, current price, fees, VAT, refund drag, and inbound/FBA-send cost proof.
- Weak demand estimates should be labelled lower confidence.
- Pack size, MOQ, and supplier order value can block an otherwise profitable product.
- Already ordered or paid stock needs its own state.
- Bliss-style supplier SKU migration must be barcode-led and auditable.
- CLF-style stock must use supplier stock proof, not only converted price-list rows.
- DHB-style repeated handoffs must be deduped for the operator.

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O460_build_restock_session_view.py`
- `python -m pytest tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py -q`
- If MOT check is added: `python -m pytest tests\manager\test_hourly_mot.py -q`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`
- O MOT must keep `o_user_working_readiness=ok`.
- O must still show 0 unsafe buy-ready rows unless all required proof fields are present.
- The UI must not claim O is complete.
- No protected action is performed during proof.

## Protected Decisions For Luke
Luke is needed only if the build step tries to cross one of these lines:
- make Google Sheets part of the normal path
- make a real purchase order
- send anything to Amazon
- change prices
- edit queues
- align Product DB/local DB facts to Sheet facts or vice versa
- pause H or run market proof
- treat a manual walkthrough decision as a live Product DB status change

## Source Evidence
- `plans/active/o-reorder-price-proof-completion-2026-05-23/URGENT_MANUAL_RESTOCK_WALKTHROUGH_20260602.md`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/O_EXPECTED_RESTOCK_PROFIT_RESEARCH_20260601.md`
- `out/systems/M/hourly_mot_O.csv`
- `out/cycle_alerts/checklist_O.csv`
- `project_control/EXPECTATIONS/operations_loop_expectations.md`

## Expected End State
After this task, O should be ready for Luke to do second-check restocking from one UI session, while real supplier order placement remains manual and protected. This is the bridge from "two processes" to "one O-controlled review process"; it is not the finished automated restock loop.
