# O Restock Approval Readiness Lane v1

## Manager Authority
- task_id: MGR_O_RESTOCK_APPROVAL_READINESS_LANE_V1
- job_ref: O-RESTOCK-APPROVAL-READINESS-02
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_quiet_continuation
- luke_action_required: 0

## Plain-English Purpose
Add a read-only approval-readiness lane to the Restock Session supplier review page.

This should show which current filtered rows are closest to approval preview, without approving buying or creating purchase orders.

## Boundary
- allowed_scope: O Restock Session supplier review display, read-only use of existing readiness/proof fields, focused UI tests, rendered page proof, O MOT proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening; no proof-event write during render; no draft-event write during render; no approval-event write; no readiness or business-fact rewrite.
- proof_required: Focused Restock Session UI tests must pass, Streamlit Restock Session render must show the approval-readiness lane with 0 exceptions, browser render proof should show the current Restock Session page when available, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, supplier download/import, supplier file move/delete/rewrite, F061 run, F status rewrite, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, approval event write, real PO, existing PO file write, existing PO hold-file write, receiving, Amazon handoff, output deletion, proof-event write during render, draft-event write during render, readiness rewrite, business-fact rewrite, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py`
- `python -m pytest tests\test_o_ui_operator_view.py -q -k "restock or supplier_file or card_control or supplier_proof or proof_history or missing_proof or supplier_readiness or proof_worklist or next_proof or selected_row_proof or safe_save or action_bucket or priority_sort or position_marker or supplier_info_needed or approval_readiness_lane"`
- Streamlit AppTest Restock Session Supplier Review render shows the approval-readiness lane with 0 exceptions and no proof-event or draft-event row writes.
- Browser render check on `http://localhost:8501/?page=restock_session` when the in-app browser path is available.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
The selected supplier view shows which rows are closest to approval preview and which proof lane blocks them, without changing rows, facts, decisions, approvals, or purchase state.

## Proof Result
- Compile passed for `O400_operator_ui.py`.
- Focused O UI proof passed: 44 passed, 114 deselected.
- Streamlit Restock Session Supplier Review render passed with 0 exceptions.
- The rendered page showed the approval-readiness lane and no-order safety note.
- Supplier proof event rows stayed 0 before and after render.
- Pack/MOQ proof event rows stayed 0 before and after render.
- Draft decision event rows stayed 1 before and after render.
- Approval decision event rows stayed 0 before and after render.
- PO review control event rows stayed 0 before and after render.
- PO export gate event rows stayed 0 before and after render.
- Browser render proof showed the Restock Session page with the approval-readiness lane, supplier-info panel, row-position marker, and safe local save guidance.
- Browser console proof had 0 relevant warnings/errors.
- O MOT after the change reported 0 fails and 1 existing stale-proof warning.
- O user-working, restock session readiness, and supplier batch draft checks stayed OK.

## Result
The selected supplier view now shows which rows are closest to approval preview and which proof lane is blocking the rest. This is display-only O construction work, not an approval event, purchase order, or restock commitment.
