# H Repair Package - MGR_H_repair_out_cycle_alerts_checkli

Created UTC: 2026-05-26T19:43:31Z

## Status
- Package only.
- H has not been repaired.
- H has not been run.
- Prices, scheduler ownership, Sheets, queues, and local DB alignment were not changed.

## Manager Packet Source
- Packet: `sellerone_manager/tasks/approved/MGR_H_repair_out_cycle_alerts_checkli.md`
- Task id: `MGR_H_repair_out_cycle_alerts_checkli`
- Flow: `H`
- Authority: `manager_task_packaging_only`
- Source artifact: `out/cycle_alerts/checklist_H.csv`
- Packet scope: manager classification, H expectation mapping, H repair package creation, and proof planning
- Packet stop condition: stop after manager classification, task packaging, and proof path are recorded for this flow

## Root Cause Summary
- The active H FAIL group is one checklist row: `h_strategy_outcome_daily_count_integrity`.
- The failing daily row is:
  - `asof_date=2026-05-13`
  - `scenario_type=multi_seller_ladder_cap`
  - `chosen_tactic=MULTI_SELLER_LADDER_CAP`
- The daily summary is internally out of balance:
  - `decision_rows=52`
  - `applied_rows + no_write_rows = 52`, so the write/no-write split balances
  - `resolved_rows + pending_rows = 53`, so the resolved/pending split is one too high
  - `success_rows + failed_rows + expired_rows + aborted_rows = 53`, so terminal outcomes are one too high
- The source H outcome log for the same date, scenario, and tactic has 53 unique source rows:
  - `APPLIED=34`
  - `NO_WRITE_REQUIRED=19`
  - `success=11`
  - `failed=10`
  - `expired=32`
  - duplicate `tactic_case_id` count: `0`
- Plain-English cause: the daily summary ledger is missing one decision count while still counting that decision's final result. The source receipt ledger has 53 receipts, but the daily till total says 52 decisions and 53 outcomes.
- This is a rollup/integrity problem in H strategy outcome reporting. It is not currently evidenced as a price-write failure, API failure, stale H runtime failure, terminal-marker failure, or publish-marker failure.

## H Expectation Mapping
- `Repricing decision logic`: blocked by `h_strategy_outcome_daily_count_integrity`.
- `Publish updates`: blocked because publish truth includes strategy daily outcome truth.
- `Boundary truth handling`: blocked because resolved/pending and terminal outcome counts must be internally consistent.
- `H launcher and guard runtime`: covered/OK in manager evidence.
- `Offer and market collection`: covered/OK in manager evidence.
- `Runtime lock safety`: covered/OK in manager evidence.
- `Health reporting`: covered/OK in manager evidence.
- `Storage self-cleaning`: not verified by this package.

## Allowed Files For A Future Repair Batch
- Read-only evidence files:
  - `sellerone_manager/tasks/approved/MGR_H_repair_out_cycle_alerts_checkli.md`
  - `out/cycle_alerts/checklist_H.csv`
  - `out/systems/M/approved_task_packets.csv`
  - `out/systems/M/manager_task_candidates.csv`
  - `out/systems/M/flow_expectation_reconciliation.csv`
  - `out/manifests/H/2026-05-26/H_20260526T184539Z.json`
  - `out/h_strategy_outcome_log.csv`
  - `out/h_strategy_outcome_daily.csv`
  - `project_control/EXPECTATIONS/H_cycle_expectations.md`
  - `project_control/ROADMAP_SYSTEM_MAP.md`
- Repair-code candidates, only if the next repair batch is approved:
  - `scripts/phase1/phase1_main_loop.py`
  - `scripts/phase1/phase1_storage.py`
  - `scripts/one_off/H162_rebuild_strategy_outcome_daily.py`
  - focused H rollup tests under `tests/`
- Repair-output candidates, only with timestamped backups first:
  - `out/h_strategy_outcome_daily.csv`
  - `out/h_strategy_outcome_log.csv` only if the approved repair explicitly needs source-log normalization, not just daily rebuild
- Backup target for future repair:
  - `out/backups/h_strategy_outcome_daily_integrity/<UTC_TIMESTAMP>/`

## Forbidden Files And Actions
- Do not change prices.
- Do not write Google Sheets.
- Do not edit queues.
- Do not change scheduler ownership.
- Do not run H without an approved H proof window.
- Do not hand-edit health outputs to make the FAIL disappear.
- Do not manually edit `out/cycle_alerts/checklist_H.csv`.
- Do not edit lock or ownership files, including H lock files and files under `out/locks/`.
- Do not edit Product DB, local DB alignment files, or SQL migration state.
- Do not edit F061 queue state or any F scanner queue files.
- Do not edit A, B, E, F, or O worker scripts as part of this H package.
- Do not change H publisher, price writer, or Amazon-write behavior unless Luke explicitly approves a wider H repair packet.

## Proof Path For A Future Repair
- Step 1 - preflight:
  - Confirm the active manager packet is still approved.
  - Confirm the H FAIL is still `h_strategy_outcome_daily_count_integrity`.
  - Confirm no H overlap or unsafe ownership condition exists before any repair proof.
- Step 2 - isolated data proof:
  - Re-aggregate `out/h_strategy_outcome_log.csv` by `asof_date`, `scenario_type`, and `chosen_tactic`.
  - Confirm the failing group still proves the same mismatch.
  - Confirm the rebuilt daily row would satisfy:
    - `applied_rows + no_write_rows == decision_rows`
    - `resolved_rows + pending_rows == decision_rows`
    - `success_rows + failed_rows + expired_rows + aborted_rows <= decision_rows`
- Step 3 - repair proof, if approved:
  - Create timestamped backups before any output write.
  - Use a generated rebuild path, not a hand edit, to rebuild the daily strategy summary from the source log.
  - If code is changed, run focused compile and H rollup tests.
- Step 4 - flow-owned H proof:
  - Use guarded H isolation or scheduler-owned proof exactly as the manager packet requires.
  - Do not claim success from A015 or a mid-cycle read alone.
  - Confirm terminal truth after finalization.
  - Confirm publish truth after finalization.
  - Confirm the scoped H checklist no longer has `h_strategy_outcome_daily_count_integrity=fail`.
- Step 5 - manager closure:
  - Mark the task `fixed_needs_retest` only after repair and isolated proof.
  - Mark the task `proved` only after manager/MOT evidence confirms the H FAIL cleared after the proper H proof window.

## Rollback Path
- Packaging rollback: remove this package file and leave the approved manager task packet unchanged.
- Future repair rollback:
  - Restore timestamped backups of `out/h_strategy_outcome_daily.csv`.
  - Restore `out/h_strategy_outcome_log.csv` only if that file was changed by the approved repair.
  - Revert any code edits in the allowed repair-code candidate files.
  - Re-run the same isolated aggregation check to confirm the rollback returned files to the backed-up state.
- No price rollback, Sheet rollback, scheduler rollback, or queue rollback should be needed because those actions are outside this package and forbidden.

## Stop Condition
- Stop now because manager classification, task packaging, allowed files, forbidden files, proof path, rollback path, and Luke-decision state are recorded.
- Stop future repair immediately if the required action crosses into prices, Sheets, queues, scheduler ownership, local DB alignment, output deletion, worker expansion, or a live H run without an approved proof window.
- Stop future repair if the source log no longer reconciles to the daily mismatch described here; that would mean the root cause evidence changed.

## Whether Luke Is Needed
- Luke is not needed for this packaging task. The approved packet says `luke_action_required=0`.
- Luke is not needed for a future narrow technical repair if it stays inside the allowed files and uses an already-approved safe H proof window.
- Luke is needed if the next step requires price changes, scheduler ownership changes, Sheets, queues, local DB alignment, output deletion, scope widening, or a live H proof window that has not already been approved.

