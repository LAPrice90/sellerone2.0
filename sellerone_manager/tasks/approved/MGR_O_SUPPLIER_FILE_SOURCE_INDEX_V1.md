# O Supplier File Source Index v1

## Manager Authority
- task_id: MGR_O_SUPPLIER_FILE_SOURCE_INDEX_V1
- job_ref: O-SUPPLIER-FILE-SOURCE
- flow: O
- task_type: bounded_o_construction
- priority: high
- status: proved
- authority: luke_requested_quiet_continuation
- luke_action_required: 0

## Plain-English Purpose
Add a read-only O source index that compares F's supplier source status with the latest files already sitting in the local supplier price-file folders.

This lets O say, for example, "F source status is stale/failed, but a newer local ABGee file is present and can be checked." It must not download supplier files, import files, edit F status, clear supplier proof, or approve buying.

## Boundary
- allowed_scope: O supplier-file source-index contracts, local builder, O492 probe wiring, UI proof panel, O manager/MOT proof, focused tests, and active O plan notes.
- forbidden_actions: no Google Sheets write; no price change; no queue edit; no Product DB or local DB alignment; no supplier file move/delete/rewrite/import; no Gmail fetch or attachment download; no F061 run; no F source-status rewrite; no real purchase order; no purchase order file write; no purchase order hold-file write; no purchase commitment; no receiving action; no send-to-Amazon action; no H pause; no market proof scan; no output deletion; no live worker cycle; no scope widening.
- proof_required: Targeted O source-index/probe/UI/MOT tests must pass, the local source-index and supplier-file probe builders must run once, and O MOT must keep O user-working with 0 unsafe buying actions.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow O
- rollback_path: Use git diff for code rollback. Do not delete O outputs. If local source-index output is malformed, rebuild through O494 only.
- stop_condition: Stop if implementation needs a protected action, live worker cycle, supplier download/import, supplier file move/delete/rewrite, F061 run, F status rewrite, H market proof, Sheet write, queue edit, price change, local DB alignment, Product DB fact change, real PO, existing PO file write, existing PO hold-file write, receiving, Amazon handoff, output deletion, or scope widening.

## Allowed Files
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/O492_build_supplier_file_presence_probe.py`
- `scripts/flows/O/O494_build_supplier_file_source_index.py`
- `scripts/flows/O/_schemas.py`
- `sellerone_manager/hourly_mot.py`
- `tests/test_o492_supplier_file_presence_probe.py`
- `tests/test_o494_supplier_file_source_index.py`
- `tests/test_o_ui_operator_view.py`
- `tests/manager/test_hourly_mot.py`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Acceptance Checks
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\O\O492_build_supplier_file_presence_probe.py scripts\flows\O\O494_build_supplier_file_source_index.py scripts\flows\O\_schemas.py sellerone_manager\hourly_mot.py`
- `python -m pytest tests\test_o494_supplier_file_source_index.py tests\test_o492_supplier_file_presence_probe.py tests\test_o_ui_operator_view.py tests\manager\test_hourly_mot.py -q -k "test_o_ or operator_ui"`
- `python scripts\flows\O\O494_build_supplier_file_source_index.py`
- `python scripts\flows\O\O492_build_supplier_file_presence_probe.py`
- `python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Expected End State
O can refresh a local supplier-file source index from existing folder/file proof, and O492 can use that index before checking drafted rows.

## Proof Result
- proved_utc: 2026-06-03T13:16:00Z
- Compile passed for O494, O492, O400, O schemas, and O MOT.
- Focused O494/O492/UI/MOT tests passed: 15 tests.
- Wider O proof slice passed: 145 tests, 79 deselected.
- Live O494 result: 11 source-index rows, 3 local-file rows, 1 failed-F-but-local-file-available row, health OK.
- Live ABGee source-index proof: F status `fail/error` points at old missing file `ABGee_Stock_Feed_20260522T135514Z_fa74c131f6.xlsx`; O found newer local file `ABGee_Stock_Feed_20260602T103226Z_f11a7d69a5.xlsx`; source handoff state `f_status_failed_local_file_available`.
- O492 used the source index and confirmed `12-749B-9EB5` is still not found by exact supplier SKU/barcode in the latest local ABGee file.
- Full local O proof chain ran once: 1 batch line, 11 source-index rows, 1 supplier-file probe row, 1 approval preview line, 1 export gate row, and local health OK.
- Streamlit Restock Session Admin Proof render passed with 0 exceptions, Supplier file source index visible, and Supplier file probe visible.
- O MOT result: 0 fails, 1 existing warning; `o_supplier_file_source_index=ok`; `o_supplier_file_presence_probe=ok`; `o_user_working_readiness=ok`.
- No supplier file write/move/delete/import/download, F source-status rewrite, Gmail fetch, F061 run, Google Sheets write, price change, queue edit, Product DB/local DB alignment, real PO, PO file write, purchase commitment, receiving, Amazon handoff, H pause, market scan, output deletion, or live worker cycle was performed.
