# A Manager Proof Coverage Package

## Package Control
- Task packet: `sellerone_manager/tasks/approved/MGR_A_proof_gap_project_control_EXPECTAT.md`
- Flow: A
- Package written UTC: 2026-05-27T07:11:16Z
- Package purpose: record what A manager evidence already covers, what remains not_verified, and how A should be proved later without running A now.
- Luke decision needed: no

This package is a proof map only. It is like marking a building inspection checklist: it records which rooms already have clear inspection photos, which rooms still need a photo, and which doors must not be opened during this package.

## Current Manager Summary
- Manager state for A is calm.
- A active fail count: 0.
- A active warn count: 0.
- A stale evidence count: 1.
- A not_verified count: 2.
- A covered expectations: 9 of 11.
- Manager proof rule: use the next A-owned run or an explicitly approved A-owned proof window. Do not run A015 alone as proof.

The latest inspected A manifest was `out/manifests/A/2026-05-27/20260527T050330Z.json`. It shows final_state `completed`, configured_step_count `11`, recorded_step_count `11`, completed_step_count `10`, verified_step_count `10`, and A scoped health fail_count `0` / warn_count `0`.

## A Expectations Already Covered By Manager Evidence

| A expectation | Manager status | Evidence currently used | Plain-English meaning |
|---|---|---|---|
| Daily orchestration runner | covered | Latest A manifest completed with 11 recorded steps; A scoped health is current with 0 fail and 0 warn | The daily A route ran end-to-end, like the main checklist being walked from start to finish. |
| Listings refresh | covered | Manifest step `A001_run_listings_to_sheet.py` completed and verified; outputs include `out/listings_data_latest.csv` and `out/merchant_listings_latest.csv` | Listings refreshed locally and the expected files were checked. |
| Catalog refresh | covered | Manifest step `A002_run_catalog_items_to_sheet.py` completed and verified; output `out/catalog_items_flat.csv` | Catalog data refreshed and the expected file was checked. |
| Inventory refresh | covered | Manifest step `A003_run_inventory_to_sheet.py` completed and verified; checks `a_inventory_stale_token_gap`, `a_daily_intel_prerequisite_freshness`, `a_daily_intel_coverage_non_parked`, and `a_daily_intel_compliance_nonempty_non_parked` are ok | Inventory and related daily-intel prerequisites are present and not showing a blocker. |
| Fees refresh | covered | Manifest step `A004_run_fees_to_sheet.py` completed and verified; check `a_fees_failed_rows_today` is ok with total_rows `0` | Fees refreshed and there are no failed fee rows recorded for the day. |
| No-Sheets source-fact path | covered | A scoped checks are ok; the legacy stock receipts Sheet step is skipped by config with `A_ENABLE_STOCK_RECEIPTS_SHEET=0`; A001, A002, A003, A004, and A016 produced local proof outputs | The latest A run supports the no-Sheets direction: local proof files refreshed and the Sheet-only stock receipts path stayed disabled. |
| Daily intel refresh | covered | Manifest step `A016_refresh_phase1_daily_intel.py` completed and verified; A daily-intel checks are ok | Daily intel rebuilt for the current local scope. |
| E cycle trigger | covered | Manifest step `run_E_cycle.py` completed and verified; output `out/e_run_log.jsonl` refreshed | A triggered E as part of its normal route. |
| Health gate run | covered | Manifest step `A015_build_system_health_check.py` completed and verified in split mode; `out/cycle_alerts/checklist_A_split.csv` is current-cycle evidence with fail_count `0` and warn_count `0` | A ran its own gate at the end, and the A-only checklist passed. |

## A Expectations Still not_verified

| A expectation | Manager status | Why it remains not_verified | What would close it |
|---|---|---|---|
| Floor table support | not_verified | `flow_expectation_reconciliation.csv` says no manager-readable evidence is mapped to this expectation yet. The A expectations file says A018 is called by the H path and has a daily dependency, but the inspected A manager evidence does not yet map a specific A manifest step, health check, or proof file to floor table support. | Add or confirm a manager-readable proof mapping that names the floor-table artifact or health check, then prove it through a next A-owned run or approved A-owned proof window. |
| Maintenance handoff safety | not_verified | `flow_expectation_reconciliation.csv` says no manager-readable evidence is mapped to this expectation yet. `flow_maintenance_state.csv` states the A proof rule, but it does not itself prove the maintenance marker sequence for A handoff safety. | Add or confirm manager-readable evidence for the maintenance handoff sequence, then prove it through a next A-owned run or approved A-owned proof window. |

These two are proof-coverage gaps, not current A runtime failures. The current A scoped checklist is calm, so no worker repair should start just because these rows are not_verified.

## Exact A Proof Path To Use Later

Do not run A now for this package. The future proof should happen only by one of these two routes:
- Next normal A-owned scheduled run.
- Explicitly approved A-owned proof window.

When that run is available, read proof only after the A run reaches a final manifest state:
- Open the newest `out/manifests/A/<date>/<run_id>.json`.
- Confirm the manifest is newer than this package.
- Confirm `cycle` is `A`.
- Confirm `final_state` is `completed`.
- Confirm `configured_step_count` equals `recorded_step_count`.
- Confirm required A steps are completed and verified, except allowed config skips such as the disabled legacy stock receipts Sheet step.
- Confirm A015 ran as the final health gate step and produced fresh `out/cycle_alerts/checklist_A_split.csv`.
- Confirm the A scoped health summary has fail_count `0` and warn_count `0`.
- Confirm `out/cycle_alerts/checklist_A.csv` and `out/cycle_alerts/checklist_A_split.csv` agree for A checks.
- Confirm `out/systems/M/flow_expectation_reconciliation.csv` updates A to either 11 of 11 covered or names only justified not_verified rows with clear next evidence.
- Confirm `out/systems/M/flow_maintenance_state.csv` still shows A calm, no Luke decision required, and no active A blocker.

The proof must not be claimed from a standalone A015 run. A015 alone is just the final inspection form; it is not the whole A cycle walking the building.

## Safe Future Worker Repair Task Candidates

No A runtime repair is needed from the evidence read in this package. Future task candidates should exist only if the next A-owned proof still cannot close the two not_verified rows.

Candidate 1: floor table support proof mapping
- Trigger: next A-owned proof still reports `Floor table support` as not_verified.
- Safe scope: identify the real floor-table proof artifact, manifest step, or health check and map it into manager expectation reconciliation.
- Forbidden inside candidate: do not run A, do not edit H pricing behavior, do not change floor values, do not write Sheets, do not align local DB data.
- Success condition: manager reconciliation maps `Floor table support` to named evidence and the next A-owned proof shows it covered.

Candidate 2: maintenance handoff safety proof mapping
- Trigger: next A-owned proof still reports `Maintenance handoff safety` as not_verified.
- Safe scope: define the manager-readable evidence for A maintenance request, B boundary readiness, A active ownership, and cleanup after completion.
- Forbidden inside candidate: do not create or delete lock files, do not start B maintenance, do not run B, do not run A, and do not restart any worker.
- Success condition: manager reconciliation maps `Maintenance handoff safety` to named evidence and the next A-owned proof shows it covered.

Candidate 3: A runtime repair packet
- Trigger: a future A-owned run has an A scoped FAIL, missing required output, stale current-cycle evidence, or manifest final_state not completed.
- Safe scope: create a separate manager-approved repair packet from the new failure evidence.
- Forbidden inside candidate: no protected action without Luke approval.
- Success condition: isolated fix plus A-owned proof clears the actual failing evidence. Do not use this candidate for a proof-mapping gap alone.

## Stop Conditions

Stop immediately if the next action would require any of these:
- Running A, A015, worker cycles, or B maintenance from this package.
- Editing worker code.
- Editing approved_task_packets.csv.
- Editing manager task status.
- Writing Google Sheets.
- Changing pricing.
- Editing queues.
- Aligning local DB data to Sheets or Sheets to local DB.
- Deleting outputs.
- Hand-editing health or MOT outputs to make status look better.
- Expanding scope outside A manager proof coverage.

## Forbidden Actions For This Package

- No ad hoc A015 proof.
- No worker cycle run.
- No B overlap.
- No legacy Sheet write.
- No local DB alignment.
- No pricing change.
- No queue change.
- No output deletion.
- No code edit.
- No manager status edit.

## Rollback Note

This package created only this markdown proof file. Packaging rollback is to remove this file and leave the approved manager task packet unchanged. No worker rollback path is needed because no worker files, outputs, Sheets, queues, prices, or local DB records were changed.

## Evidence Read

- `sellerone_manager/tasks/approved/MGR_A_proof_gap_project_control_EXPECTAT.md`
- `project_control/EXPECTATIONS/A_cycle_expectations.md`
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `out/systems/M/flow_expectation_reconciliation.csv`
- `out/systems/M/flow_maintenance_state.csv`
- `out/systems/M/manager_task_candidates.csv`
- `out/systems/M/approved_task_packets.csv`
- `out/manifests/A/2026-05-27/20260527T050330Z.json`
- `out/manifests/A/2026-05-26/20260526T173722Z.json`
- `out/cycle_alerts/checklist_A.csv`
- `out/cycle_alerts/checklist_A_split.csv`
- `out/system_health_checklist.csv`

## Package Close

- Luke decision needed: no.
- Protected boundary hit: no.
- Package stop condition reached: yes. Manager classification, expectation mapping, proof path, safe future candidates, stop conditions, and forbidden actions are recorded.
- Recommended next move: continue with A floor table support and maintenance handoff proof mapping when the manager opens those mapping tasks.
