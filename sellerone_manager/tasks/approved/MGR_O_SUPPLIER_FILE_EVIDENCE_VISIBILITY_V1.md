# O Supplier File Evidence Visibility v1

## Manager Authority
- task_id: MGR_O_SUPPLIER_FILE_EVIDENCE_VISIBILITY_V1
- job_ref: O-SUPPLIER-FILE-EVIDENCE
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_continue_safe_o_tasks_after_supplier_gate_clearance
- luke_action_required: 0

## Plain-English Purpose
Move read-only supplier-file evidence into the main Restock Session supplier review area.

This helps Luke see whether O already has local supplier-file proof for the visible rows before working card-level supplier proof.

## Boundary
- allowed_scope: Restock Session supplier review display panel, O MOT read-only check, focused UI/MOT tests, rendered page proof, browser render proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download/fetch; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no proof-event write during render; no draft-event write during render; no approval-event write during render; no PO-control event write during render; no readiness or business-fact rewrite.
- proof_required: focused UI and MOT tests must pass, Streamlit render must show the supplier file evidence panel with 0 exceptions and no event row writes, browser render should show the panel when available, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs any protected action or if the panel clears supplier proof, imports supplier files, or changes F/O source status.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py sellerone_manager\hourly_mot.py`
- focused UI tests for supplier file evidence visibility.
- focused MOT tests for supplier file evidence visibility and O user-working readiness.
- Streamlit AppTest Restock Session Supplier Review render shows the supplier file evidence panel with 0 exceptions and no proof-event, draft-event, approval-event, or PO-control row writes.
- Browser render check on `http://localhost:8501/?page=restock_session` when available.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
Luke can see local supplier-file evidence in the main Restock Session workflow without O importing files, clearing proof, approving buying, creating purchase orders, receiving, or sending stock to Amazon.

## Proof Result
- status: proved
- `python -m py_compile scripts\flows\O\O400_operator_ui.py sellerone_manager\hourly_mot.py` passed.
- Focused UI proof passed: 5 passed, 164 deselected.
- Focused O MOT proof passed: 4 passed, 127 deselected.
- Wider Restock UI proof passed: 55 passed, 114 deselected.
- Streamlit AppTest render passed with 0 exceptions.
- Render proof showed `Supplier file evidence`, `Probe rows`, `Exact matches found`, `Not found`, and the read-only supplier-file safety note.
- Render proof kept event rows unchanged: supplier proof 0, pack/MOQ proof 0, draft decision 1, approval decision 0, PO review control 0, PO export gate 0.
- Browser proof showed supplier-file evidence, probe rows, exact matches, not-found state, real-PO gate, supplier gate clearance, and safety note.
- Browser proof had 0 relevant console issues.
- O MOT passed with 0 fails and 1 existing stale-proof warning.
- `o_supplier_file_evidence_visibility=ok`: `review_rows=608;probe_rows=1;files_checked=1;exact=0;not_found=1;no_file=0;read_error=0`.
- `o_supplier_file_presence_probe=ok`: `probes=1;found=0;not_found=1;not_checked=0`.
- `o_real_po_readiness_gate=ok`: `closed;reasons=4;ready_rows=0;blocked_rows=608`.
- `o_user_working_readiness=ok`.
- Boundary kept: no Sheets write, no price change, no queue edit, no DB alignment, no supplier file fetch/change/import, no Gmail fetch, no F061 run, no F source-status rewrite, no approval event write, no PO creation, no PO file write, no receiving, no Amazon handoff, no H pause, no market scan, no output deletion, and no live worker cycle.
