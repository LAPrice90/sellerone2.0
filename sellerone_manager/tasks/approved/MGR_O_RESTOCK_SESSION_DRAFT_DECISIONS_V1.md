# O Restock Session Draft Decisions v1

## Manager Authority
- task_id: MGR_O_RESTOCK_SESSION_DRAFT_DECISIONS_V1
- job_ref: O-RESTOCK-SESSION-DRAFT
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_o_mid_build_work
- luke_action_required: 0

## Plain-English Purpose
Add local draft decision capture to the O Restock Session UI so Luke can record what he intends to do next without using the old method.

This is not approval to buy stock. It is only a safe local notes-and-quantity lane.

## Boundary
- allowed_scope: O restock-session draft decision contract, local validation, UI capture form, session view merge-back, session health proof, O manager/MOT check coverage, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no real purchase order; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Targeted O draft/session/UI/MOT tests must pass, the O460 local session builder must run, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If local draft output is malformed, rebuild it through the new validator only.
- stop_condition: Stop if implementation needs a protected action, a live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O460_build_restock_session_view.py`
- new `scripts/flows/O/O462_restock_session_draft_decisions.py`
- `scripts/flows/O/_schemas.py`
- `scripts/flows/O/_contract_io.py` only if needed for contract handling
- `sellerone_manager/hourly_mot.py`
- `tests/test_o460_restock_session_view.py`
- new `tests/test_o462_restock_session_draft_decisions.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O460_build_restock_session_view.py scripts\flows\O\O462_restock_session_draft_decisions.py scripts\flows\O\_schemas.py`
- `python -m pytest tests\test_o462_restock_session_draft_decisions.py tests\test_o460_restock_session_view.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q`
- `python scripts\flows\O\O460_build_restock_session_view.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O can capture local restock draft decisions from the UI. Every captured decision remains labelled local-only and cannot create a purchase order, receiving event, Amazon handoff, price change, queue edit, Sheet write, or Product DB fact change.
