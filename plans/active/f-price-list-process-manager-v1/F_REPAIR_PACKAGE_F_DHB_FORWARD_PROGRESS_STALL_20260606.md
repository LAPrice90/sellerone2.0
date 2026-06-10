# F Repair Package - DHB Forward Progress Stall - 2026-06-06

- job_ref: F-DHB-FORWARD-PROGRESS

## Plain-English Summary

The F price-list scanner is alive, but DHB is not moving cleanly.

The manager evidence shows repeated tiny DHB chunks being marked as scanner success while the pending count barely changes and memory import proof is blocked. That means F can look busy while it keeps circling the same tail rows.

This repair is about making F stop the bad loop and classify it honestly. It is not approval to restart the scanner, switch supplier, edit the queue, or rewrite scanner outputs.

## Approved Check

`f_live_owner_status`

## Allowed Files For A Future Repair Batch

- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/_scanner_state.py`
- focused F scanner tests under `tests/`
- `sellerone_manager/hourly_mot.py` and focused manager tests only if the manager proof wording needs a narrow adjustment
- this repair package and `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md` for proof notes

## Forbidden Files And Actions

- Do not run F061.
- Do not restart FPM or F061.
- Do not edit F061 queue state.
- Do not switch the active supplier manually.
- Do not approve scanner handoff.
- Do not rewrite active scanner output rows to make progress look better.
- Do not fetch Gmail, download supplier files, or delete supplier files.
- Do not write Google Sheets.
- Do not change prices.
- Do not align local DB facts.
- Do not delete outputs.
- Do not open a separate Chrome login window.
- Do not widen into A, B, E, H, or O work.

## Proof Path For A Future Repair

- Add or adjust scanner tests so repeated `scanner_chunk` success rows with no pending-count drop cannot be treated as clean progress.
- Add or adjust scanner tests so `f061_memory_import` blocked evidence cannot leave the live owner reporting clean success.
- If the right behaviour is to park/reclassify the DHB tail row, prove it through code-level tests first.
- Retest the manager layer with `python -m sellerone_manager.app --hourly-mot --mot-flow F`.
- Live proof can happen only through a separate approved F proof window. Until then, the MOT failure should stay visible.

## Retest Command

python -m sellerone_manager.app --hourly-mot --mot-flow F

## Rollback Path

- Use git diff for code rollback.
- Do not edit F queue files or scanner outputs during rollback.
- Rerun the read-only F MOT after rollback.

## Stop Condition

Stop immediately if the fix requires a live scanner run, scanner restart, queue edit, supplier switch, output rewrite, separate browser login, Sheet write, price change, local DB alignment, output deletion, or business judgement.

Stop successfully when code-level proof prevents the DHB no-progress loop from being called healthy, and F MOT continues to show the live scanner truth without hiding the active failure.
