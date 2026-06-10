# O Restock Supplier Batch Drafts v1

## Manager Authority
- task_id: MGR_O_RESTOCK_SUPPLIER_BATCH_DRAFTS_V1
- job_ref: O-RESTOCK-SUPPLIER-BATCH
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_o_mid_build_work
- luke_action_required: 0

## Plain-English Purpose
Add supplier batch draft review to the O Restock Session UI.

This lets saved local draft quantities group by supplier so Luke can see a possible supplier order batch before any real purchase order exists.

## Boundary
- allowed_scope: O supplier batch draft contracts, local builder, UI review view, health proof, O manager/MOT check coverage, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no real purchase order; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Targeted O batch/session/UI/MOT tests must pass, the O batch builder must run, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If batch output is malformed, rebuild it through the new local builder only.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O460_build_restock_session_view.py`
- `scripts/flows/O/O462_restock_session_draft_decisions.py`
- new `scripts/flows/O/O464_build_restock_supplier_batch_drafts.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o462_restock_session_draft_decisions.py`
- new `tests/test_o464_restock_supplier_batch_drafts.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O460_build_restock_session_view.py scripts\flows\O\O462_restock_session_draft_decisions.py scripts\flows\O\O464_build_restock_supplier_batch_drafts.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q`
- `python scripts\flows\O\O464_build_restock_supplier_batch_drafts.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O can show local supplier batch drafts from saved local order-quantity decisions. Every batch and line remains review-only and cannot create a purchase order, receiving event, Amazon handoff, price change, queue edit, Sheet write, or Product DB fact change.
