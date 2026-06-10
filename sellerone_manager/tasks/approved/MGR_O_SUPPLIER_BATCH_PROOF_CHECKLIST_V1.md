# O Supplier Batch Proof Checklist v1

## Manager Authority
- task_id: MGR_O_SUPPLIER_BATCH_PROOF_CHECKLIST_V1
- job_ref: O-SUPPLIER-BATCH-CHECKLIST
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_o_mid_build_work
- luke_action_required: 0

## Plain-English Purpose
Add a supplier proof checklist to each O supplier batch draft line.

This helps the UI show whether a draft supplier basket still needs proof for supplier match, supplier cost, supplier stock, backorder state, pack/MOQ, and supplier-file freshness before any real order work starts.

## Boundary
- allowed_scope: O supplier batch proof checklist fields, local builder logic, UI review columns, health proof, O manager/MOT check coverage, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no real purchase order; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Targeted O checklist/batch/session/UI/MOT tests must pass, the O batch builder must run, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If checklist output is malformed, rebuild through the local O464 builder only.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O464_build_restock_supplier_batch_drafts.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o464_restock_supplier_batch_drafts.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O464_build_restock_supplier_batch_drafts.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q`
- `python scripts\flows\O\O464_build_restock_supplier_batch_drafts.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O supplier batch draft lines show supplier proof status clearly. Missing supplier proof remains visible as `needs_supplier_proof` or `not_verified`, not as a failure and not as approval to buy.
