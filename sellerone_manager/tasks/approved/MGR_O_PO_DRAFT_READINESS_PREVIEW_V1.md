# O PO Draft Readiness Preview v1

## Manager Authority
- task_id: MGR_O_PO_DRAFT_READINESS_PREVIEW_V1
- job_ref: O-PO-DRAFT-READINESS
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_o_mid_build_work
- luke_action_required: 0

## Plain-English Purpose
Add a local PO draft readiness preview to O.

This lets O show whether locally reviewed restock lines are ready for a future PO draft design step. It is not a purchase order, does not write to the existing PO files, and does not commit buying.

## Boundary
- allowed_scope: O PO draft readiness preview contracts, local builder, UI preview view, O manager/MOT proof, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no real purchase order; no purchase order file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Targeted O PO-readiness/session/UI/MOT tests must pass, the O PO readiness preview builder must run, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If local readiness output is malformed, rebuild it through O474 only.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, existing PO file write, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O474_build_po_draft_readiness_preview.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o474_po_draft_readiness_preview.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O474_build_po_draft_readiness_preview.py scripts\flows\O\O472_build_purchase_approval_guardrails.py scripts\flows\O\O470_build_purchase_approval_preview.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o474_po_draft_readiness_preview.py tests\test_o472_purchase_approval_guardrails.py tests\test_o470_purchase_approval_preview.py tests\test_o468_restock_pack_moq_proof_events.py tests\test_o466_restock_supplier_proof_events.py tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q`
- `python scripts\flows\O\O474_build_po_draft_readiness_preview.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O can show a local PO draft readiness preview for accepted local review packets. The preview remains review-only and cannot create purchase orders or write to the existing PO draft files.

## Proof Result
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O474_build_po_draft_readiness_preview.py scripts\flows\O\O472_build_purchase_approval_guardrails.py scripts\flows\O\O470_build_purchase_approval_preview.py scripts\flows\O\O464_build_restock_supplier_batch_drafts.py scripts\flows\O\O468_restock_pack_moq_proof_events.py scripts\flows\O\O466_restock_supplier_proof_events.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py` passed.
- `python -m pytest tests\test_o474_po_draft_readiness_preview.py tests\test_o472_purchase_approval_guardrails.py tests\test_o470_purchase_approval_preview.py tests\test_o468_restock_pack_moq_proof_events.py tests\test_o466_restock_supplier_proof_events.py tests\test_o464_restock_supplier_batch_drafts.py tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q` passed: 203 tests.
- `python scripts\flows\O\O470_build_purchase_approval_preview.py` passed: 0 approval preview lines, 0 supplier packet summaries, health ok.
- `python scripts\flows\O\O472_build_purchase_approval_guardrails.py` passed: 0 approval decision events, 0 approval guardrail rows, health ok.
- `python scripts\flows\O\O474_build_po_draft_readiness_preview.py` passed: 0 PO readiness lines, 0 PO readiness summaries, health ok.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O` passed with 0 fails and 1 existing tolerated warning.
- `o_po_draft_readiness_preview=ok`: files exist, 0 lines, 0 summary rows, 4 health rows, 0 false ready rows, 0 live action rows.
- `o_user_working_readiness=ok`.
- Streamlit AppTest render check for live `page=restock_session` passed with 0 exceptions and showed `PO draft readiness preview`.
- Streamlit AppTest render check against temporary PO readiness data passed with 0 exceptions.
- No protected action was performed.
