# O Supplier Proof Work Queue v1

## Manager Authority
- task_id: MGR_O_SUPPLIER_PROOF_WORK_QUEUE_V1
- job_ref: O-SUPPLIER-QUEUE-AND
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_continue_safe_o_tasks_after_supplier_file_coverage_map
- luke_action_required: 0

## Plain-English Purpose
Add a read-only supplier proof work queue.

This groups supplier-file uncovered restock rows by supplier and local action so Luke can see the next practical supplier-proof work without reading every card.

## Boundary
- allowed_scope: Restock Session supplier review display panel, O MOT read-only check, focused UI/MOT tests, rendered page proof, browser render proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download/fetch; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no proof-event write during render; no draft-event write during render; no approval-event write during render; no PO-control event write during render; no readiness or business-fact rewrite.
- proof_required: focused UI and MOT tests must pass, Streamlit render must show the supplier proof work queue with 0 exceptions and no event row writes, browser render should show the panel when available, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs any protected action or if the queue fetches files, clears supplier proof, imports supplier files, changes F/O source status, or creates any live action.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py sellerone_manager\hourly_mot.py`
- focused UI tests for supplier proof work queue.
- focused MOT tests for supplier proof work queue and O user-working readiness.
- Streamlit AppTest Restock Session Supplier Review render shows the supplier proof work queue with 0 exceptions and no proof-event, draft-event, approval-event, or PO-control row writes.
- Browser render check on `http://localhost:8501/?page=restock_session` when available.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
Luke can see the next supplier-proof work queue from the Restock Session page without O fetching files, clearing proof, approving buying, creating purchase orders, receiving, or sending stock to Amazon.

## Proof Result
- status: proved
- `python -m py_compile scripts\flows\O\O400_operator_ui.py sellerone_manager\hourly_mot.py` passed.
- Focused UI proof passed: 3 passed, 169 deselected.
- Focused O MOT proof passed: 5 passed, 132 deselected.
- Wider Restock UI proof passed: 58 passed, 114 deselected.
- Streamlit AppTest render passed with 0 exceptions.
- Render proof showed `Supplier proof work queue`, `Uncovered proof rows`, `Supplier groups to work`, `Top supplier group`, `Current view uncovered`, and the read-only queue safety note.
- Render proof kept event rows unchanged: supplier proof 0, pack/MOQ proof 0, draft decision 1, approval decision 0, PO review control 0, PO export gate 0.
- Browser proof showed supplier proof work queue, uncovered proof rows, supplier groups to work, top supplier group, current view uncovered, supplier-file proof coverage, real-PO gate, and safety note.
- Browser proof had 0 relevant console issues.
- O MOT passed with 0 fails and 1 existing stale-proof warning.
- `o_supplier_proof_work_queue=ok`: `uncovered=607;supplier_groups=35;top_supplier=Stax;top_supplier_rows=78;top_action=check_later_or_mark_drop;top_action_rows=504`.
- `o_supplier_file_proof_coverage_map=ok`: `review_rows=608;covered=1;uncovered=607;suppliers=35;covered_suppliers=1;exact=0;not_found=1`.
- `o_real_po_readiness_gate=ok`: `closed;reasons=4;ready_rows=0;blocked_rows=608`.
- `o_user_working_readiness=ok`.
- Boundary kept: no Sheets write, no price change, no queue edit, no DB alignment, no supplier file fetch/change/import, no Gmail fetch, no F061 run, no F source-status rewrite, no approval event write, no PO creation, no PO file write, no receiving, no Amazon handoff, no H pause, no market scan, no output deletion, and no live worker cycle.
