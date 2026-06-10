# H Repair Package - Storage Cleanup Safety Proof - 2026-06-04

## Task ID
`h_storage_cleanup_safety`

## Manager Task
- Source proof: read-only H MOT warning row.
- This package is manager proof and storage-safety classification only.
- It does not approve H runtime work, cleanup deletion, repricing changes, scheduler changes, or worker repair.

## Current Evidence
The latest independent H MOT shows H is warning-only, not failed:
- H FAIL count: 0
- `h_storage_cleanup_safety`: warn
- cleanup ledger is present
- staged rollback area has `staged_entries=241`

Plain English:
- H has the cleanup receipt, so this is not an emergency failure.
- The staged rollback area is still bigger than the manager wants for a clean long-term operating state.
- The work is to make rollback cleanup proof controlled and visible, not to delete files from the manager.

## Allowed Files For A Future Repair Batch
Future work may inspect only H manager proof, cleanup receipts, and storage policy evidence:
- `out/systems/M/hourly_mot_H.csv`
- `out/systems/M/mot/mot_rollup_latest.md`
- `out/systems/H/live/H_cleanup_ledger.jsonl`
- `out/systems/H/staged`
- `project_control/AGENT_NEW_CYCLE_STORAGE_RULES.md`
- `project_control/EXPECTATIONS/H_cycle_expectations.md`
- `sellerone_manager/hourly_mot.py`, only for read-only cleanup-proof classification
- focused manager tests under `tests/manager/`, only if manager classification code changes
- this package and `CODING_PLAN.md` for proof notes

If a future source-level cleanup hook repair is needed, it must be split into a separate approved packet after the manager proves the exact source and boundary. This packet does not approve deletion.

## Forbidden Files And Actions
- Do not run H.
- Do not pause or resume scheduler ownership.
- Do not publish.
- Do not change prices.
- Do not edit queues.
- Do not write Google Sheets.
- Do not align or edit local DB data.
- Do not delete outputs.
- Do not delete staged rollback snapshots.
- Do not restart workers.
- Do not hand-edit cleanup ledgers, MOT rows, manifests, terminal markers, or H outputs to make the warning disappear.
- Do not widen into A, B, E, F, O, Product DB, scanner, supplier, or finance logic.

## Proof Path For A Future Repair
- Re-read the latest H MOT and confirm the warning still exists.
- Inspect cleanup ledger shape and staged rollback counts from outside H only.
- Confirm the newest rollback snapshots are preserved and the manager can explain which cleanup rule applies.
- If only manager classification changes are made, compile touched manager files and run focused H manager tests.
- Retest with the read-only H MOT.
- Success means `h_storage_cleanup_safety` is `ok`, or remains an explicit non-blocking warning with rollback safety preserved and no hidden deletion risk.

## Retest Command
```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow H
```

## Rollback Path
- Use git diff for manager-code rollback if any manager classification code changes.
- Revert only manager proof wording or MOT classification code touched by the repair.
- Do not delete H outputs, staged rollback snapshots, or cleanup ledgers as rollback.

## Stop Condition
Stop immediately if the work would require H runtime execution, scheduler ownership change, publishing, price change, queue edit, Sheet write, local DB alignment, output deletion, staged snapshot deletion, worker restart, or scope widening.

Stop after the board-visible packet exists and the H manager can explain the cleanup warning without relying on chat memory.
