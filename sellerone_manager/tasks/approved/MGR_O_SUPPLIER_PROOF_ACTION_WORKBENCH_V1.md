- job_ref: O-SUPPLIER-ACTION-WORKBENCH-02
# MGR_O_SUPPLIER_PROOF_ACTION_WORKBENCH_V1

## Title
O Supplier Proof Action Workbench v1

## Flow
O

## Status
proved

## Authority
luke_requested_continue_safe_o_tasks_after_supplier_proof_queue_filter

## Purpose
Add a read-only supplier proof action workbench to the Restock Session UI so O can show which supplier proof fields need checking next: exact match, stock/backorder, cost, file/reference, and drop/check-later.

## Allowed Scope
- `scripts/flows/O/O400_operator_ui.py`
- `sellerone_manager/hourly_mot.py`
- focused O UI tests under `tests/test_o_ui_operator_view.py`
- focused O MOT tests under `tests/manager/test_hourly_mot.py`
- active O plan notes under `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`

## Forbidden Actions
- no Google Sheets write
- no price change
- no queue edit
- no Product DB or local DB alignment
- no supplier file move/delete/rewrite/import/download/fetch
- no Gmail fetch or attachment download
- no F061 run
- no F source-status rewrite
- no approval-event write
- no real purchase order
- no purchase order file write
- no purchase order hold-file write
- no purchase commitment
- no receiving action
- no send-to-Amazon action
- no H pause
- no market proof scan
- no output deletion
- no live worker cycle
- no proof-event write during render
- no draft-event write during render
- no approval-event write during render
- no PO-control event write during render
- no readiness or business-fact rewrite

## Proof Required
- focused UI and MOT tests pass
- Streamlit render shows the supplier proof action workbench with 0 exceptions and no event row writes
- browser render shows the panel on the Restock Session page
- O MOT keeps O user-working with 0 unsafe buying actions

## Retest Command
`python -m sellerone_manager.app --hourly-mot --mot-flow O`

## Rollback
Use git diff for code rollback. Do not delete O outputs.

## Stop Condition
Stop if implementation needs any protected action or if the workbench saves proof, fetches supplier files, clears supplier proof, imports supplier files, changes F/O source status, creates a PO, commits buying, receives stock, or sends anything to Amazon.
