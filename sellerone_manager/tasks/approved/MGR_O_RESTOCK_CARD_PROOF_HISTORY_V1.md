# O Restock Card Proof History v1

## Manager Authority
- task_id: MGR_O_RESTOCK_CARD_PROOF_HISTORY_V1
- job_ref: O-RESTOCK-CARD-HISTORY
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_quiet_continuation
- luke_action_required: 0

## Plain-English Purpose
Show the latest saved supplier-proof and pack/MOQ proof history directly on normal Restock Session Supplier Review product cards.

This lets Luke see what has already been recorded for a row without opening the lower technical proof tables.

## Boundary
- allowed_scope: O Restock Session card proof-history display, read-only merge from existing local supplier-proof and pack/MOQ proof fields, focused UI tests, O MOT proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening; no cosmetic redesign outside the small card-history area; no proof-event write during render.
- proof_required: Focused Restock Session UI tests must pass, Streamlit Restock Session render must show the proof-history area with 0 exceptions, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, supplier download/import, supplier file move/delete/rewrite, F061 run, F status rewrite, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, existing PO file write, existing PO hold-file write, receiving, Amazon handoff, output deletion, cosmetic scope widening, proof-event write during render, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py`
- `python -m pytest tests\test_o_ui_operator_view.py -q -k "restock or supplier_file or card_control or supplier_proof or proof_history"`
- Streamlit AppTest Restock Session Supplier Review render shows proof-history display with 0 exceptions.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
Normal Supplier Review cards show latest local supplier and pack/MOQ proof history without writing new events or changing business facts.

## Proof Result
- changed: Added a read-only `Latest local proof` area to normal Restock Session Supplier Review cards.
- display_rendered: latest supplier-proof detail, latest pack/MOQ proof detail, and no-proof fallback messages.
- read_only_boundary: supplier proof event rows stayed 0 before and after render; pack/MOQ proof event rows stayed 0 before and after render.
- compile: passed for `scripts\flows\O\O400_operator_ui.py`.
- focused_ui_tests: 18 passed, 99 deselected.
- streamlit_render: passed with 0 exceptions; proof-history text visible.
- o_mot: 0 fails, 1 existing stale-proof warning.
- o_user_working_readiness: ok.
- supplier_file_source_index: ok.
- supplier_file_presence_probe: ok.
- boundary: no Sheet write, price change, queue edit, DB alignment, supplier import/download/rewrite, F061 run, F status rewrite, PO creation, PO file write, purchase commitment, receiving, Amazon handoff, H pause, market scan, output deletion, live worker cycle, proof-event write during render, or cosmetic redesign outside the card-history area.
