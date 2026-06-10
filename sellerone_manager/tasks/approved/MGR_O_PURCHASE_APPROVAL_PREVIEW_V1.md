# O Purchase Approval Preview v1

## Manager Authority
- task_id: MGR_O_PURCHASE_APPROVAL_PREVIEW_V1
- job_ref: O-PURCHASE-APPROVAL-PREVIEW
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_o_mid_build_work
- luke_action_required: 0

## Plain-English Purpose
Add a local purchase-approval packet preview to the O Restock Session UI.

This lets O group supplier batch draft lines into a review packet that can show which lines are ready for purchase-approval review and which lines are still blocked. It is not a purchase order and does not approve buying.

## Boundary
- allowed_scope: O purchase-approval preview contracts, local builder, UI preview view, O manager/MOT proof, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no real purchase order; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no approval capture; no scope widening.
- proof_required: Targeted O approval-preview/session/UI/MOT tests must pass, the O approval preview builder must run, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If local preview output is malformed, rebuild it through O470 only.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, receiving, Amazon handoff, output deletion, approval capture, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O470_build_purchase_approval_preview.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o470_purchase_approval_preview.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O470_build_purchase_approval_preview.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o470_purchase_approval_preview.py tests\test_o468_restock_pack_moq_proof_events.py tests\test_o466_restock_supplier_proof_events.py tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q`
- `python scripts\flows\O\O470_build_purchase_approval_preview.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O can show a local purchase-approval preview packet for supplier batch draft lines. The preview remains review-only and cannot approve buying or create purchase orders.

## Proof Result
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O470_build_purchase_approval_preview.py scripts\flows\O\O464_build_restock_supplier_batch_drafts.py scripts\flows\O\O468_restock_pack_moq_proof_events.py scripts\flows\O\O466_restock_supplier_proof_events.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py` passed.
- `python -m pytest tests\test_o470_purchase_approval_preview.py tests\test_o468_restock_pack_moq_proof_events.py tests\test_o466_restock_supplier_proof_events.py tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q` passed: 193 tests.
- `python scripts\flows\O\O470_build_purchase_approval_preview.py` passed: 0 approval preview lines, 0 supplier packet summaries, health ok.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O` passed with 0 fails and 1 existing tolerated warning.
- Streamlit AppTest render checks for live and temporary preview data passed with 0 exceptions.
- No protected action was performed.
