# O PO Draft Packet Review v1

## Manager Authority
- task_id: MGR_O_PO_DRAFT_PACKET_REVIEW_V1
- job_ref: O-PO-DRAFT-PACKET
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_o_mid_build_work
- luke_action_required: 0

## Plain-English Purpose
Add a local PO draft packet review preview to O.

This groups local PO line design rows into a supplier packet that can be reviewed before any real purchase order exists. It is a packet review only. It does not write to `purchase_orders_live.csv`, `purchase_order_lines_live.csv`, or `purchase_order_draft_holds.csv`.

## Boundary
- allowed_scope: O PO draft packet review contracts, local builder, UI preview view, O manager/MOT proof, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no real purchase order; no purchase order file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Targeted O packet-review/session/UI/MOT tests must pass, the O PO draft packet review builder must run, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If local packet-review output is malformed, rebuild it through O478 only.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, existing PO file write, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O478_build_po_draft_packet_review.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o478_po_draft_packet_review.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O478_build_po_draft_packet_review.py scripts\flows\O\O476_build_po_line_design_preview.py scripts\flows\O\O474_build_po_draft_readiness_preview.py scripts\flows\O\O472_build_purchase_approval_guardrails.py scripts\flows\O\O470_build_purchase_approval_preview.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o478_po_draft_packet_review.py tests\test_o476_po_line_design_preview.py tests\test_o474_po_draft_readiness_preview.py tests\test_o472_purchase_approval_guardrails.py tests\test_o470_purchase_approval_preview.py tests\test_o468_restock_pack_moq_proof_events.py tests\test_o466_restock_supplier_proof_events.py tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q`
- `python scripts\flows\O\O478_build_po_draft_packet_review.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O can show a local PO draft packet review for PO-line-design rows. The packet remains review-only and cannot create purchase orders or write to existing PO files.

## Proof Result
- proved_utc: 2026-06-03T09:26:29Z
- Full compile passed for O400, O478, O476, O474, O472, O470, O schemas, and O MOT.
- Focused O proof tests passed: 213 tests.
- Live local builder chain passed: O470 -> O472 -> O474 -> O476 -> O478.
- Live O478 output: 0 line rows, 0 summary rows, 4 health rows, health ok.
- O MOT result: 0 fails, 1 existing parked warning; `o_po_draft_packet_review=ok`; `o_user_working_readiness=ok`.
- Streamlit AppTest live Restock Session: 0 exceptions and `PO draft packet review` visible.
- Streamlit AppTest temporary row proof: 0 exceptions and a fake local packet-review row rendered.
- No Google Sheets write, price change, queue edit, Product DB/local DB alignment, real PO, PO file write, purchase commitment, receiving, send-to-Amazon, H pause, market scan, output deletion, or live worker cycle was performed.
