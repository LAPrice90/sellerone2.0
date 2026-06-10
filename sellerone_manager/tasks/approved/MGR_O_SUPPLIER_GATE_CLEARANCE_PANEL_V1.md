# O Supplier Gate Clearance Panel v1

## Manager Authority
- task_id: MGR_O_SUPPLIER_GATE_CLEARANCE_PANEL_V1
- job_ref: O-SUPPLIER-GATE-CLEARANCE
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_continue_safe_o_tasks_after_real_po_gate_filter
- luke_action_required: 0

## Plain-English Purpose
Add a read-only supplier clearance panel after the real-PO gate worklist.

This helps Luke see which visible restock rows are blocked by supplier stock proof, supplier cost proof, or both supplier proof lanes before any approval or PO step can be trusted.

## Boundary
- allowed_scope: Restock Session supplier review display panel, O MOT read-only check, focused UI/MOT tests, rendered page proof, browser render proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no proof-event write during render; no draft-event write during render; no approval-event write during render; no PO-control event write during render; no readiness or business-fact rewrite.
- proof_required: focused UI and MOT tests must pass, Streamlit render must show the supplier gate clearance panel with 0 exceptions and no event row writes, browser render should show the panel when available, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs any protected action or if the panel changes facts/events instead of summarising the view.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py sellerone_manager\hourly_mot.py`
- focused UI tests for supplier gate clearance and real-PO clearance.
- focused MOT tests for O mid-build and supplier gate clearance.
- Streamlit AppTest Restock Session Supplier Review render shows the supplier gate clearance panel with 0 exceptions and no proof-event, draft-event, approval-event, or PO-control row writes.
- Browser render check on `http://localhost:8501/?page=restock_session` when available.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
Luke can see a supplier-only gate clearance summary from the Restock Session page without changing rows, proof, approvals, purchase orders, receiving, or Amazon handoff state.

## Proof Result
- status: proved
- `python -m py_compile scripts\flows\O\O400_operator_ui.py sellerone_manager\hourly_mot.py` passed.
- Focused UI proof passed: 4 passed, 163 deselected.
- Focused O MOT proof passed: 5 passed, 122 deselected.
- Wider Restock UI proof passed: 53 passed, 114 deselected.
- Streamlit AppTest render passed with 0 exceptions.
- Render proof showed `Supplier gate clearance`, `Stock proof lane`, `Cost proof lane`, and the read-only supplier safety note.
- Render proof kept event rows unchanged: supplier proof 0, pack/MOQ proof 0, draft decision 1, approval decision 0, PO review control 0, PO export gate 0.
- Browser proof showed the real-PO gate, clearance worklist, clearance filter, supplier gate clearance panel, stock lane, cost lane, both-supplier-lanes card, and safety note.
- Browser proof had 0 relevant console issues.
- O MOT passed with 0 fails and 1 existing stale-proof warning.
- `o_real_po_supplier_gate_clearance=ok`: `stock=608;cost=608;both=608;stock_only=0;cost_only=0;supplier_clear=0`.
- `o_real_po_readiness_gate=ok`: `closed;reasons=4;ready_rows=0;blocked_rows=608`.
- `o_user_working_readiness=ok`.
- Boundary kept: no Sheets write, no price change, no queue edit, no DB alignment, no supplier file fetch/change, no Gmail fetch, no F061 run, no approval event write, no PO creation, no PO file write, no receiving, no Amazon handoff, no H pause, no market scan, no output deletion, and no live worker cycle.
