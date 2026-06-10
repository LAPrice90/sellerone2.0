# O Restock Next Proof Hint v1

## Manager Authority
- task_id: MGR_O_RESTOCK_NEXT_PROOF_HINT_V1
- job_ref: O-RESTOCK-NEXT-HINT
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_quiet_continuation
- luke_action_required: 0

## Plain-English Purpose
Add a read-only next-proof action hint under the Restock Session missing-proof worklist filter.

This tells Luke what proof to collect first for the currently selected proof worklist, without saving proof or changing business state.

## Boundary
- allowed_scope: O Restock Session selected-supplier next-proof hint, read-only use of existing row blocker/proof fields, focused UI tests, rendered page proof, O MOT proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening; no cosmetic redesign outside the small next-proof hint area; no proof-event write during render; no readiness or business-fact rewrite.
- proof_required: Focused Restock Session UI tests must pass, Streamlit Restock Session render must show the next-proof hint with 0 exceptions, browser render proof should show the hint on the current Restock Session page when available, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, supplier download/import, supplier file move/delete/rewrite, F061 run, F status rewrite, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, existing PO file write, existing PO hold-file write, receiving, Amazon handoff, output deletion, cosmetic scope widening, proof-event write during render, readiness rewrite, business-fact rewrite, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py`
- `python -m pytest tests\test_o_ui_operator_view.py -q -k "restock or supplier_file or card_control or supplier_proof or proof_history or missing_proof or supplier_readiness or proof_worklist or next_proof"`
- Streamlit AppTest Restock Session Supplier Review render shows next-proof hint with 0 exceptions and no proof-event row writes.
- Browser render check on `http://localhost:8501/?page=restock_session` when the in-app browser path is available.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
Normal Supplier Review tells Luke the next proof to collect for the selected missing-proof worklist without changing any business state.

## Proof Result
- status: proved
- compile: passed for `scripts\flows\O\O400_operator_ui.py`
- focused_tests: 28 passed, 104 deselected
- streamlit_render: 0 exceptions
- proof_event_rows: 0 before render, 0 after render
- browser_render: `Missing proof worklist`, `Next proof to collect`, `Selected supplier readiness`, and `Products to review` visible
- browser_console: 0 relevant warnings/errors
- o_mot: 0 fails, 1 existing stale-proof warning
- protected_actions: none
