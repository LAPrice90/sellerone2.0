# H Repair Package - Staged Retention Policy Alignment - 2026-06-04

## Task ID
`h_staged_retention_policy_alignment`

## Manager Task
- Source proof: `h_storage_cleanup_safety` now compares the central manager storage rule with the H cleanup receipt.
- Current manager evidence shows the central rule expects newest 5 staged rollback snapshots, while the H runtime cleanup receipt reports a 240-folder cap.
- This package is for a later bounded source-policy alignment only. It is not part of the proof-only storage safety job.

## Current Evidence
- The central housekeeping registry rule `h_staged_publish_snapshots` keeps the newest 5 H staged rollback folders.
- The H cleanup ledger has `h_staged_retention` receipts using `count_cap=240`.
- The live H staged rollback folder count is above the central manager cap.
- Newest rollback folders are still present, so this is warning-only until a later source repair is opened.

Plain English:
- H still has rollback safety, but two cleanup rulebooks disagree.
- The next repair should align the H cleanup policy source to the manager storage rule, without deleting files from the manager/MOT job.

## Allowed Files For A Future Repair Batch
Future work may inspect and edit only the source-policy proof needed to align H staged retention:
- `scripts/cycles/run_H_pricing_cycle.py`, only the H staged-retention cap/proof-writing source
- `project_control/log_housekeeping_registry.json`, only if evidence proves the manager registry rule is wrong
- `project_control/EXPECTATIONS/H_cycle_expectations.md`, only for wording that reflects proven policy
- focused tests for H storage cleanup proof and H retention policy
- manager packet/status files needed to record proof

This package does not approve deleting staged snapshots. If a proof step would require actual output deletion or a live H run, stop and return it as a protected approval decision.

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
- Do not widen into A, B, E, F, O, Product DB, scanner, supplier, or finance logic.

## Proof Path For A Future Repair
- Confirm the central registry cap and the H runtime cleanup receipt still disagree.
- Repair only the source that writes or chooses the H staged-retention cap.
- Add focused tests proving the manager cap and H receipt cap agree without running H or deleting snapshots.
- Retest with the read-only H MOT.
- Success means `h_storage_cleanup_safety` no longer reports a registry/runtime cap mismatch, or the task is blocked with a clear Luke decision if live deletion approval is required.

## Retest Command
```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow H
```

## Rollback Path
- Use git diff to revert only the source-policy and manager-proof files touched by this repair.
- Do not delete H outputs, staged rollback snapshots, or cleanup ledgers as rollback.

## Stop Condition
Stop immediately if the repair would require H runtime execution, scheduler ownership change, publishing, price change, queue edit, Sheet write, local DB alignment, output deletion, staged snapshot deletion, worker restart, or scope widening.
