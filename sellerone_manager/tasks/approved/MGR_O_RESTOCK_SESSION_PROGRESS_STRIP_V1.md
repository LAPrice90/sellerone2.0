# O Restock Session Progress Strip v1

## Manager Authority
- task_id: MGR_O_RESTOCK_SESSION_PROGRESS_STRIP_V1
- job_ref: O-RESTOCK-SESSION-PROGRESS
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_quiet_continuation
- luke_action_required: 0

## Plain-English Purpose
Add a visible progress strip to the Restock Session UI.

This makes O's construction movement visible to Luke by showing each local restock stage, its row count, its current state, and the next local step. It is a viewing aid only. It does not create purchase orders, write PO files, commit buying, receive stock, or send anything to Amazon.

## Boundary
- allowed_scope: Restock Session UI progress helper, display panel, focused UI tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Focused O UI tests pass, Restock Session AppTest render passes, and O MOT remains 0 fails.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, PO file write, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py`
- `python -m pytest tests\test_o_ui_operator_view.py -q -k "operator_ui or restock_progress"`
- Restock Session Streamlit AppTest shows `Restock progress` with 0 exceptions.
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
Luke can see whether O is moving by looking at one progress strip instead of opening individual proof files.

## Proof Result
- proved_utc: 2026-06-03T11:36:16Z
- Compile passed for `O400_operator_ui.py`.
- Focused UI proof passed: 5 tests, 95 deselected.
- Wider O UI/MOT regression passed: 136 tests, 65 deselected.
- Streamlit AppTest Restock Session render: 0 exceptions, `Restock progress` visible, and `Next local step:` visible.
- O MOT result: 0 fails, 1 existing stale-proof warning; `o_user_working_readiness=ok`; `o_po_draft_export_preview=ok`.
- No Google Sheets write, price change, queue edit, Product DB/local DB alignment, real PO, PO file write, purchase commitment, receiving, send-to-Amazon, H pause, market scan, output deletion, or live worker cycle was performed.
