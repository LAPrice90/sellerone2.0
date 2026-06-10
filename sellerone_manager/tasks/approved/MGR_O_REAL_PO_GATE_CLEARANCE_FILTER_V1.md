# O Real PO Gate Clearance Filter v1

## Manager Authority
- task_id: MGR_O_REAL_PO_GATE_CLEARANCE_FILTER_V1
- job_ref: O-REAL-PO-GATE
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_proceed_after_gate_worklist
- luke_action_required: 0

## Plain-English Purpose
Add a read-only filter for the real-PO gate clearance lanes.

This lets the Restock Session page narrow to rows blocked by supplier stock proof, supplier cost proof, market/profit proof, refund/inbound proof, local quantity proof, or approval/PO gates.

## Boundary
- allowed_scope: Restock Session supplier review display filter, focused UI tests, rendered page proof, browser render proof, O MOT proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no approval-event write; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no proof-event write during render; no draft-event write during render; no approval-event write during render; no PO-control event write during render; no readiness or business-fact rewrite.
- proof_required: focused UI tests must pass, Streamlit render must show the clearance lane filter with 0 exceptions and no event row writes, browser render should show the filter when available, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs any protected action or if the filter changes facts/events instead of filtering the view.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py`
- `python -m pytest tests\test_o_ui_operator_view.py -q -k "real_po_gate_clearance_filter or real_po_gate_clearance_worklist or real_po_readiness_gate or protected_stage_visibility or po_preview_visibility or restock or supplier_file or card_control or supplier_proof or proof_history or missing_proof or supplier_readiness or proof_worklist or next_proof or selected_row_proof or safe_save or action_bucket or priority_sort or position_marker or supplier_info_needed or approval_readiness_lane or approval_readiness_filter or approval_preview_visibility or approval_preview_status_filter"`
- Streamlit AppTest Restock Session Supplier Review render shows the real-PO clearance lane filter with 0 exceptions and no proof-event, draft-event, approval-event, or PO-control row writes.
- Browser render check on `http://localhost:8501/?page=restock_session` when available.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
Luke can filter the Restock Session page by the real-PO gate clearance lane without changing rows, proof, approvals, purchase orders, receiving, or Amazon handoff state.

## Proof Result
- status: proved
- `python -m py_compile scripts\flows\O\O400_operator_ui.py` passed.
- Focused filter/worklist tests passed: 2 passed, 164 deselected.
- Wider Restock UI proof passed: 52 passed, 114 deselected.
- Streamlit AppTest render passed with 0 exceptions.
- Render proof showed `Real PO clearance lane`, `All gate clearance lanes`, supplier stock lane, and the read-only safety note.
- Render proof kept event rows unchanged: supplier proof 0, pack/MOQ proof 0, draft decision 1, approval decision 0, PO review control 0, PO export gate 0.
- Browser proof showed the real-PO gate, clearance worklist, clearance filter, all-lanes option, supplier stock lane, refund/inbound lane, and safety note.
- Browser proof had 0 relevant console issues.
- O MOT passed with 0 fails and 1 existing stale-proof warning.
- `o_real_po_readiness_gate=ok`: `closed;reasons=4;ready_rows=0;blocked_rows=608`.
- `o_real_po_gate_clearance_worklist=ok`: `lanes=6;top=approval_po_gates;supplier_stock=608;supplier_cost=608;market_profit=602;refund_inbound=608;local_qty=607;approval_po_gates=608`.
- `o_user_working_readiness=ok`.
- Boundary kept: no Sheets write, no price change, no queue edit, no DB alignment, no supplier file change, no F061 run, no approval event write, no PO creation, no PO file write, no receiving, no Amazon handoff, no H pause, no market scan, no output deletion, and no live worker cycle.
