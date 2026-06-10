# O Restock PO Preview Visibility Bundle v1

## Manager Authority
- task_id: MGR_O_RESTOCK_PO_PREVIEW_VISIBILITY_BUNDLE_V1
- job_ref: O-RESTOCK-PO-PREVIEW
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_all_safe_tasks
- luke_action_required: 0

## Plain-English Purpose
Surface existing PO-preview construction status in the main Restock Session supplier review page.

This should help Luke see where filtered rows sit in the local PO-preview chain without creating PO files, PO holds, purchases, receiving, or Amazon handoff.

## Boundary
- allowed_scope: O Restock Session supplier review display, read-only use of existing PO preview outputs, read-only filters, focused UI tests, rendered page proof, O MOT proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening; no proof-event write during render; no draft-event write during render; no readiness or business-fact rewrite.
- proof_required: Focused Restock Session UI tests must pass, Streamlit Restock Session render must show PO-preview construction status with 0 exceptions, browser render proof should show the current Restock Session page when available, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, supplier download/import, supplier file move/delete/rewrite, F061 run, F status rewrite, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, approval event write, real PO, existing PO file write, existing PO hold-file write, receiving, Amazon handoff, output deletion, proof-event write during render, draft-event write during render, readiness rewrite, business-fact rewrite, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py`
- `python -m pytest tests\test_o_ui_operator_view.py -q -k "restock or supplier_file or card_control or supplier_proof or proof_history or missing_proof or supplier_readiness or proof_worklist or next_proof or selected_row_proof or safe_save or action_bucket or priority_sort or position_marker or supplier_info_needed or approval_readiness_lane or approval_readiness_filter or approval_preview_visibility or approval_preview_status_filter or po_preview_visibility"`
- Streamlit AppTest Restock Session Supplier Review render shows PO-preview construction status with 0 exceptions and no proof-event, draft-event, approval-event, or PO-control row writes.
- Browser render check on `http://localhost:8501/?page=restock_session` when the in-app browser path is available.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
The selected supplier view shows existing local PO-preview construction status and can filter rows by that status, without changing rows, facts, decisions, approvals, PO files, or purchase state.

## Proof Result
- proved_utc: 2026-06-03T19:19:22Z
- compile: passed for `O400_operator_ui.py`
- focused_po_preview_test: passed, 1 passed and 161 deselected
- wider_restock_ui_test: passed, 48 passed and 114 deselected
- streamlit_render: passed with 0 exceptions
- streamlit_visibility: showed `Existing PO preview construction status`, `PO preview:`, and `PO preview status`
- render_write_safety: supplier proof rows 0 to 0; pack/MOQ rows 0 to 0; draft rows 1 to 1; approval decision rows 0 to 0; PO review control rows 0 to 0; PO export gate rows 0 to 0
- browser_render: passed on `http://localhost:8501/?page=restock_session`
- browser_visibility: showed PO-preview panel, card line, status filter, safety note, and `Safe local save`
- browser_console: 0 relevant warnings/errors
- o_mot: 0 fails, 1 existing stale-proof warning
- o_user_working_readiness: ok
- o_restock_session_readiness: ok, rows=608; suppliers=34; blocked=608; summary=426; drafts=1
- o_restock_supplier_batch_drafts: ok, lines=1; batches=1; summary=1

## Boundary Confirmation
- No Google Sheets write.
- No price change.
- No queue edit.
- No Product DB or local DB alignment.
- No supplier file move, delete, rewrite, import, or download.
- No Gmail fetch or attachment download.
- No F061 run.
- No F source-status rewrite.
- No real approval event.
- No real purchase order.
- No purchase order file write.
- No purchase order hold-file write.
- No purchase commitment.
- No receiving action.
- No send-to-Amazon action.
- No H pause.
- No market proof scan.
- No output deletion.
- No live worker cycle.
- No proof-event, draft-event, approval-event, or PO-control event write during render.
- No readiness rewrite.
- No business-fact rewrite.
