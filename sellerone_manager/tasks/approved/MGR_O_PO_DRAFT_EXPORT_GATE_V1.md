# O PO Draft Export Gate v1

## Manager Authority
- task_id: MGR_O_PO_DRAFT_EXPORT_GATE_V1
- job_ref: O-PO-DRAFT-EXPORT
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_quiet_continuation
- luke_action_required: 0

## Plain-English Purpose
Add a final local approval gate after the PO draft export preview.

This lets the UI record a local decision that an export preview needs more proof, should stay on local hold, or is candidate-ready for future PO consideration. It is still not a purchase order and does not create or write any PO file.

## Boundary
- allowed_scope: O PO draft export-gate contracts, local event capture, local builder, UI control/view, O manager/MOT proof, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Targeted O export-gate/session/UI/MOT tests must pass, the full local O preview builder chain must run once, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If local export-gate output is malformed, rebuild through O490 only after upstream local preview files are safe.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, existing PO file write, existing PO hold-file write, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O490_build_po_draft_export_gate.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o490_po_draft_export_gate.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O490_build_po_draft_export_gate.py scripts\flows\O\O488_build_po_draft_export_preview.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o490_po_draft_export_gate.py tests\test_o488_po_draft_export_preview.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q -k "test_o_ or operator_ui"`
- `python scripts\flows\O\O490_build_po_draft_export_gate.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O can show and record a final local export-gate decision without creating a purchase order or committing a buy.

## Proof Result
- proved_utc: 2026-06-03T11:51:33Z
- Compile passed for O400, O490, O488, O schemas, and O MOT.
- Focused O490 tests passed: 4 tests.
- O-scoped O490/UI/MOT proof passed: 138 tests, 72 deselected.
- Live local builder chain passed: O470 -> O472 -> O474 -> O476 -> O478 -> O480 -> O482 -> O484 -> O486 -> O488 -> O490.
- Live O490 output: 0 gate-event rows, 0 gate rows, 4 health rows, health ok.
- O MOT result: 0 fails, 1 existing stale-proof warning; `o_po_draft_export_gate=ok`; `o_user_working_readiness=ok`.
- Streamlit AppTest Restock Session render: 0 exceptions, `Restock progress` visible, and `PO draft export gate` visible.
- No Google Sheets write, price change, queue edit, Product DB/local DB alignment, real PO, PO file write, existing PO hold-file write, purchase commitment, receiving, send-to-Amazon, H pause, market scan, output deletion, or live worker cycle was performed.
