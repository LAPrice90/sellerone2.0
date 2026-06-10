# O Restock Missing Proof Worklist Filter v1

## Manager Authority
- task_id: MGR_O_RESTOCK_MISSING_PROOF_WORKLIST_FILTER_V1
- job_ref: O-RESTOCK-MISSING-FILTER
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_quiet_continuation
- luke_action_required: 0

## Plain-English Purpose
Add a read-only missing-proof worklist filter to the normal Restock Session Supplier Review page.

This lets Luke narrow the selected supplier's product cards by proof type, such as supplier stock, supplier cost, refunds, inbound/FBA cost, or old bridge proof.

## Boundary
- allowed_scope: O Restock Session selected-supplier missing-proof filter, read-only use of existing row blocker/proof fields, focused UI tests, rendered page proof, O MOT proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening; no cosmetic redesign outside the small missing-proof filter area; no proof-event write during render; no readiness or business-fact rewrite.
- proof_required: Focused Restock Session UI tests must pass, Streamlit Restock Session render must show the missing-proof worklist filter with 0 exceptions, browser render proof should show the filter on the current Restock Session page when available, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, supplier download/import, supplier file move/delete/rewrite, F061 run, F status rewrite, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, existing PO file write, existing PO hold-file write, receiving, Amazon handoff, output deletion, cosmetic scope widening, proof-event write during render, readiness rewrite, business-fact rewrite, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py`
- `python -m pytest tests\test_o_ui_operator_view.py -q -k "restock or supplier_file or card_control or supplier_proof or proof_history or missing_proof or supplier_readiness or proof_worklist"`
- Streamlit AppTest Restock Session Supplier Review render shows missing-proof worklist filter with 0 exceptions and no proof-event row writes.
- Browser render check on `http://localhost:8501/?page=restock_session` when the in-app browser path is available.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
Normal Supplier Review can filter the selected supplier's visible product cards by missing proof type without changing any business state.

## Proof Result
- changed: Added a read-only `Missing proof worklist` filter to normal Restock Session Supplier Review.
- display_rendered: `Missing proof worklist`, `Selected supplier readiness`, and `Products to review` show on the page.
- filter_logic: focused tests proved filter options count missing-proof labels and filter rows by the same labels shown on cards.
- read_only_boundary: supplier proof event rows stayed 0 before and after render; pack/MOQ proof event rows stayed 0 before and after render.
- compile: passed for `scripts\flows\O\O400_operator_ui.py`.
- focused_ui_tests: 27 passed, 104 deselected.
- streamlit_render: passed with 0 exceptions; missing-proof worklist filter visible.
- browser_render: passed on `http://localhost:8501/?page=restock_session`; missing-proof filter showed on Supplier Review; console warnings/errors were 0.
- o_mot: 0 fails, 1 existing stale-proof warning.
- o_user_working_readiness: ok.
- o_restock_session_readiness: ok.
- o_restock_supplier_batch_drafts: ok.
- boundary: no Sheet write, price change, queue edit, DB alignment, supplier import/download/rewrite, F061 run, F status rewrite, PO creation, PO file write, purchase commitment, receiving, Amazon handoff, H pause, market scan, output deletion, live worker cycle, proof-event write during render, readiness rewrite, business-fact rewrite, or cosmetic redesign outside the missing-proof filter area.
