# O Supplier File Proof Coverage Map v1

## Manager Authority
- task_id: MGR_O_SUPPLIER_FILE_PROOF_COVERAGE_MAP_V1
- job_ref: O-SUPPLIER-FILE-COVERAGE
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_continue_safe_o_tasks_after_supplier_file_evidence_visibility
- luke_action_required: 0

## Plain-English Purpose
Add a read-only supplier-file proof coverage map.

This shows how many restock rows already have local supplier-file probe evidence and how many still have no probe evidence before supplier proof can be cleared.

## Boundary
- allowed_scope: Restock Session supplier review display panel, O MOT read-only check, focused UI/MOT tests, rendered page proof, browser render proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download/fetch; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no proof-event write during render; no draft-event write during render; no approval-event write during render; no PO-control event write during render; no readiness or business-fact rewrite.
- proof_required: focused UI and MOT tests must pass, Streamlit render must show the coverage map with 0 exceptions and no event row writes, browser render should show the panel when available, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs any protected action or if the map fetches files, clears supplier proof, imports supplier files, changes F/O source status, or creates any live action.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py sellerone_manager\hourly_mot.py`
- focused UI tests for supplier-file proof coverage.
- focused MOT tests for supplier-file proof coverage and O user-working readiness.
- Streamlit AppTest Restock Session Supplier Review render shows the supplier-file proof coverage map with 0 exceptions and no proof-event, draft-event, approval-event, or PO-control row writes.
- Browser render check on `http://localhost:8501/?page=restock_session` when available.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
Luke can see supplier-file probe coverage across the restock list without O fetching files, clearing proof, approving buying, creating purchase orders, receiving, or sending stock to Amazon.

## Proof Result
- status: proved
- `python -m py_compile scripts\flows\O\O400_operator_ui.py sellerone_manager\hourly_mot.py` passed.
- Focused UI proof passed: 4 passed, 167 deselected.
- Focused O MOT proof passed: 5 passed, 128 deselected.
- Wider Restock UI proof passed: 57 passed, 114 deselected.
- Streamlit AppTest render passed with 0 exceptions.
- Render proof showed `Supplier file proof coverage`, `Rows with probe evidence`, `Rows without probe evidence`, `Current view coverage`, and the read-only coverage safety note.
- Render proof kept event rows unchanged: supplier proof 0, pack/MOQ proof 0, draft decision 1, approval decision 0, PO review control 0, PO export gate 0.
- Browser proof showed supplier-file proof coverage, rows with probe evidence, rows without probe evidence, current view coverage, supplier-file evidence, real-PO gate, and safety note.
- Browser proof had 0 relevant console issues.
- O MOT passed with 0 fails and 1 existing stale-proof warning.
- `o_supplier_file_proof_coverage_map=ok`: `review_rows=608;covered=1;uncovered=607;suppliers=35;covered_suppliers=1;exact=0;not_found=1`.
- `o_supplier_file_evidence_visibility=ok`: `review_rows=608;probe_rows=1;files_checked=1;exact=0;not_found=1;no_file=0;read_error=0`.
- `o_real_po_readiness_gate=ok`: `closed;reasons=4;ready_rows=0;blocked_rows=608`.
- `o_user_working_readiness=ok`.
- Boundary kept: no Sheets write, no price change, no queue edit, no DB alignment, no supplier file fetch/change/import, no Gmail fetch, no F061 run, no F source-status rewrite, no approval event write, no PO creation, no PO file write, no receiving, no Amazon handoff, no H pause, no market scan, no output deletion, and no live worker cycle.
