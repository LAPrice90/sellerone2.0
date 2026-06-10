# O Supplier Proof Capture v1

## Manager Authority
- task_id: MGR_O_SUPPLIER_PROOF_CAPTURE_V1
- job_ref: O-SUPPLIER-CAPTURE-CREATED
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_o_mid_build_work
- luke_action_required: 0

## Plain-English Purpose
Add local supplier proof capture to the O Restock Session UI.

This lets the UI record supplier stock state, backorder state, supplier file date/reference, and an operator note against a draft batch line. The proof is local only and does not create a purchase order, receiving event, Amazon handoff, price change, queue edit, Sheet write, Product DB change, or DB alignment.

## Boundary
- allowed_scope: O supplier proof event contract, local validation, supplier batch merge-back, UI capture form, O manager/MOT proof, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no real purchase order; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Targeted O supplier-proof/session/UI/MOT tests must pass, the O supplier proof validator and batch builder must run, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If local proof output is malformed, rebuild it through the new validator and O464 builder only.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O464_build_restock_supplier_batch_drafts.py`
- `scripts/flows/O/O466_restock_supplier_proof_events.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o466_restock_supplier_proof_events.py`
- `tests/test_o464_restock_supplier_batch_drafts.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O464_build_restock_supplier_batch_drafts.py scripts\flows\O\O466_restock_supplier_proof_events.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o466_restock_supplier_proof_events.py tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q`
- `python scripts\flows\O\O466_restock_supplier_proof_events.py`
- `python scripts\flows\O\O464_build_restock_supplier_batch_drafts.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O can capture local supplier proof for draft batch lines. Missing proof stays visible, captured proof stays local, and no real buying path is enabled.

## Proof Result
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O464_build_restock_supplier_batch_drafts.py scripts\flows\O\O466_restock_supplier_proof_events.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py` passed.
- `python -m pytest tests\test_o466_restock_supplier_proof_events.py tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q` passed: 178 tests.
- `python scripts\flows\O\O466_restock_supplier_proof_events.py` passed: 0 supplier proof event rows, 0 invalid rows.
- `python scripts\flows\O\O464_build_restock_supplier_batch_drafts.py` passed: 0 batch lines, 0 supplier batch summaries, health ok.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O` passed with 0 fails and 1 existing tolerated warning.
- Streamlit AppTest render check for live `page=restock_session` passed with 0 exceptions.
- Streamlit AppTest render check against temporary supplier-batch data passed with 0 exceptions and showed the supplier proof controls.
- No protected action was performed.
