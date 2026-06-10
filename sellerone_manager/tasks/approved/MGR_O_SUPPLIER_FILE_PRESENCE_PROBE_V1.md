# O Supplier File Presence Probe v1

## Manager Authority
- task_id: MGR_O_SUPPLIER_FILE_PRESENCE_PROBE_V1
- job_ref: O-SUPPLIER-FILE-PRESENCE
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_quiet_continuation
- luke_action_required: 0

## Plain-English Purpose
Add a read-only O proof check that looks at the latest local supplier price file for drafted restock rows and says whether the exact supplier SKU or barcode is present.

This should stop O asking Luke for supplier facts that the system can already look up. It must not turn a missing supplier-file match into a safe buy.

## Boundary
- allowed_scope: O supplier-file presence proof contracts, local builder, UI proof panel, O manager/MOT proof, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite; no Gmail fetch or attachment download; no F061 run; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Targeted O supplier-file probe/session/UI/MOT tests must pass, the local O supplier proof chain must run once, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If local probe output is malformed, rebuild through O492 only after upstream local batch draft files are safe.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, supplier download, supplier file move/delete/rewrite, F061 run, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, existing PO file write, existing PO hold-file write, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O492_build_supplier_file_presence_probe.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o492_supplier_file_presence_probe.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O492_build_supplier_file_presence_probe.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o492_supplier_file_presence_probe.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q -k "test_o_ or operator_ui"`
- `python scripts\flows\O\O492_build_supplier_file_presence_probe.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O can show whether a drafted restock row was found in the latest local supplier price file without clearing supplier proof, creating a PO, or committing a buy.

## Proof Result
- proved_utc: 2026-06-03T12:38:00Z
- Compile passed for O492, O400, O schemas, and O MOT.
- Focused O492/UI/MOT tests passed: 11 tests.
- Wider O proof slice passed: 142 tests, 75 deselected.
- Live O492 result: 1 supplier-file probe row, 0 found rows, 1 not-found row, health OK.
- Live ABGee proof: latest local file `ABGee_Stock_Feed_20260602T103226Z_f11a7d69a5.xlsx`, 8793 rows searched, exact supplier SKU/barcode not found for `12-749B-9EB5`.
- Full local O proof chain ran once: 1 batch line, 1 supplier-file probe row, 1 approval preview line, 1 export gate row, and local health OK.
- Streamlit Restock Session Admin Proof render passed with 0 exceptions and Supplier file probe visible.
- O MOT result: 0 fails, 1 existing warning; `o_supplier_file_presence_probe=ok`; `o_user_working_readiness=ok`.
- No supplier file write/move/delete, Gmail fetch, F061 run, Google Sheets write, price change, queue edit, Product DB/local DB alignment, real PO, PO file write, purchase commitment, receiving, Amazon handoff, H pause, market scan, output deletion, or live worker cycle was performed.
