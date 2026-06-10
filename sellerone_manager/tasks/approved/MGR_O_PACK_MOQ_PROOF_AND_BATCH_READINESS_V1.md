# O Pack MOQ Proof And Batch Readiness v1

## Manager Authority
- task_id: MGR_O_PACK_MOQ_PROOF_AND_BATCH_READINESS_V1
- job_ref: O-PACK-MOQ-AND
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_o_mid_build_work
- luke_action_required: 0

## Plain-English Purpose
Add local pack/MOQ proof capture and a supplier-batch readiness gate to the O Restock Session UI.

This lets the UI record pack size, supplier MOQ, valid order step, proof reference, and a note against a supplier batch draft line. It also labels each batch line as either blocked from purchase approval or ready for purchase-approval review. This is a review label only and does not create a purchase order.

## Boundary
- allowed_scope: O pack/MOQ proof event contract, local validation, supplier batch merge-back, batch readiness labels, UI capture form, O manager/MOT proof, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no real purchase order; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Targeted O pack/MOQ/session/UI/MOT tests must pass, the O pack/MOQ validator and batch builder must run, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If local proof output is malformed, rebuild it through the new validator and O464 builder only.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O464_build_restock_supplier_batch_drafts.py`
- `scripts/flows/O/O468_restock_pack_moq_proof_events.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o468_restock_pack_moq_proof_events.py`
- `tests/test_o464_restock_supplier_batch_drafts.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O464_build_restock_supplier_batch_drafts.py scripts\flows\O\O468_restock_pack_moq_proof_events.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o468_restock_pack_moq_proof_events.py tests\test_o466_restock_supplier_proof_events.py tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q`
- `python scripts\flows\O\O468_restock_pack_moq_proof_events.py`
- `python scripts\flows\O\O464_build_restock_supplier_batch_drafts.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O can capture local pack/MOQ proof for draft batch lines and clearly say whether each draft line is blocked or ready for purchase-approval review. No real buying path is enabled.

## Proof Result
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O464_build_restock_supplier_batch_drafts.py scripts\flows\O\O468_restock_pack_moq_proof_events.py scripts\flows\O\O466_restock_supplier_proof_events.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py` passed.
- `python -m pytest tests\test_o468_restock_pack_moq_proof_events.py tests\test_o466_restock_supplier_proof_events.py tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q` passed: 188 tests.
- `python scripts\flows\O\O468_restock_pack_moq_proof_events.py` passed: 0 pack/MOQ proof event rows, 0 invalid rows.
- `python scripts\flows\O\O466_restock_supplier_proof_events.py` passed: 0 supplier proof event rows, 0 invalid rows.
- `python scripts\flows\O\O464_build_restock_supplier_batch_drafts.py` passed: 0 batch lines, 0 supplier batch summaries, health ok.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O` passed with 0 fails and 1 existing tolerated warning.
- Streamlit AppTest render checks for live and temporary supplier-batch data passed with 0 exceptions.
- No protected action was performed.
