# O Restock Card Local Controls v1

## Manager Authority
- task_id: MGR_O_RESTOCK_CARD_LOCAL_CONTROLS_V1
- job_ref: O-RESTOCK-CARD-LOCAL
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_quiet_continuation
- luke_action_required: 0

## Plain-English Purpose
Add local-only draft controls to normal Restock Session Supplier Review product cards.

This lets Luke save Drop, Snooze, or draft quantity from the row he is looking at, instead of using the separate old-style selector form. These controls only write local draft decision proof.

## Boundary
- allowed_scope: O Restock Session card controls, local draft-decision UI wiring, focused UI tests, O MOT proof, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import/download; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening; no cosmetic redesign outside the small card-control area.
- proof_required: Focused Restock Session UI tests must pass, Streamlit Restock Session render must show local-only card controls with 0 exceptions, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, supplier download/import, supplier file move/delete/rewrite, F061 run, F status rewrite, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, existing PO file write, existing PO hold-file write, receiving, Amazon handoff, output deletion, cosmetic scope widening, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py`
- `python -m pytest tests\test_o_ui_operator_view.py -q -k "restock or supplier_file or card_control or next_action"`
- Streamlit AppTest Restock Session Supplier Review render shows local-only card controls with 0 exceptions.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
Normal Supplier Review cards can save local draft decisions without creating real purchase orders or changing business facts.

## Proof Result
- changed: Added local-only draft controls under normal Restock Session Supplier Review cards.
- controls_rendered: `Local note`, `Draft qty`, `Snooze until`, `Save qty draft`, `Snooze`, and `Drop`.
- compile: passed for `scripts\flows\O\O400_operator_ui.py`.
- focused_ui_tests: 14 passed, 98 deselected.
- streamlit_render: passed with 0 exceptions; controls and local-draft safety caption visible.
- o_mot: 0 fails, 1 existing stale-proof warning.
- o_user_working_readiness: ok.
- supplier_file_source_index: ok.
- supplier_file_presence_probe: ok.
- boundary: no Sheet write, price change, queue edit, DB alignment, supplier import/download/rewrite, F061 run, F status rewrite, PO creation, PO file write, purchase commitment, receiving, Amazon handoff, H pause, market scan, output deletion, live worker cycle, or cosmetic redesign outside the card-control area.
