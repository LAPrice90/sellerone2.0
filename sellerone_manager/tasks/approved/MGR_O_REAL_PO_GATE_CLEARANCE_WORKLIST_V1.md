# O Real PO Gate Clearance Worklist v1

## Manager Authority
- task_id: MGR_O_REAL_PO_GATE_CLEARANCE_WORKLIST_V1
- job_ref: O-REAL-PO-GATE-02
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_proceed_after_real_po_gate
- luke_action_required: 0

## Plain-English Purpose
Move O forward by turning the closed real-PO gate into a worklist.

The worklist should show which proof lanes keep the gate closed and what should be cleared first.

## Current Decision
O is still not ready to create real purchase orders.

This build must not fake readiness. It should make the blocker lanes obvious so O can work down them safely.

## Boundary
- allowed_scope: read-only real-PO gate clearance worklist in O manager/MOT and Restock Session UI, focused tests, rendered page proof, browser render proof, O MOT proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no proof-event write during render; no draft-event write during render; no approval-event write during render; no PO-control event write during render; no readiness or business-fact rewrite.
- proof_required: focused UI/MOT tests must pass, Streamlit render must show the clearance worklist with 0 exceptions and no event row writes, browser render should show the worklist when available, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs any protected action or if the worklist hides a blocker or claims real PO readiness without clean proof.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q -k "real_po_gate_clearance_worklist or real_po_readiness_gate or protected_stage_visibility or po_preview_visibility or restock or supplier_file or card_control or supplier_proof or proof_history or missing_proof or supplier_readiness or proof_worklist or next_proof or selected_row_proof or safe_save or action_bucket or priority_sort or position_marker or supplier_info_needed or approval_readiness_lane or approval_readiness_filter or approval_preview_visibility or approval_preview_status_filter"`
- Streamlit AppTest Restock Session Supplier Review render shows the real-PO gate clearance worklist with 0 exceptions and no proof-event, draft-event, approval-event, or PO-control row writes.
- Browser render check on `http://localhost:8501/?page=restock_session` when available.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O shows a clear, automatic list of the proof lanes that must be cleared before the real-PO gate can open.

## Proof Result
- proved_utc: 2026-06-03T19:56:37Z
- compile: passed for `O400_operator_ui.py` and `hourly_mot.py`
- focused_real_po_worklist_test: passed, 3 passed and 288 deselected
- wider_o_ui_mot_test: passed, 62 passed and 229 deselected
- streamlit_render: passed with 0 exceptions
- streamlit_visibility: showed `Real PO readiness gate`, `Real PO gate clearance worklist`, blocker lanes, and read-only safety note
- render_write_safety: supplier proof rows 0 to 0; pack/MOQ rows 0 to 0; draft rows 1 to 1; approval decision rows 0 to 0; PO review control rows 0 to 0; PO export gate rows 0 to 0
- browser_render: passed on `http://localhost:8501/?page=restock_session`
- browser_visibility: showed real-PO gate, clearance worklist, supplier stock lane, refund/inbound lane, safety note, and `Safe local save`
- browser_console: 0 relevant warnings/errors
- o_mot: 0 fails, 1 existing stale-proof warning
- o_real_po_readiness_gate: ok, `closed;reasons=4;ready_rows=0;blocked_rows=608`
- o_real_po_gate_clearance_worklist: ok, `lanes=6;top=approval_po_gates;supplier_stock=608;supplier_cost=608;market_profit=602;refund_inbound=608;local_qty=607;approval_po_gates=608`
- o_user_working_readiness: ok
- o_restock_session_readiness: ok, rows=608; suppliers=34; blocked=608; summary=426; drafts=1

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
