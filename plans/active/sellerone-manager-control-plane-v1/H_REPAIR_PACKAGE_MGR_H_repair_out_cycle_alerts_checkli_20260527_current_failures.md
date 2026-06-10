# H Repair Package - Current Active Failures - 2026-05-27

## Manager Task
- Task packet: sellerone_manager/tasks/approved/MGR_H_repair_out_cycle_alerts_checkli.md
- Task id: MGR_H_repair_out_cycle_alerts_checkli
- This package is planning and classification only.
- No worker repair was performed in this packaging step.

## Evidence Read
- out/cycle_alerts/checklist_H.csv
- out/systems/M/manager_task_candidates.csv
- out/systems/M/flow_expectation_reconciliation.csv
- project_control/EXPECTATIONS/H_cycle_expectations.md

## Current Active H Fail Group
The current H checklist confirms 2 active FAIL rows:

| Check | Status | Value | Evidence notes |
|---|---:|---:|---|
| h_ceiling_events_required_fields_non_blank | fail | 3 | blank_required=true_binding_ceiling_gbp:3 |
| h_market_context_fill_nonzero | fail | 5 | zero_fill_cols=buy_box_channel,lowest_fba_price,lowest_fbm_price,offer_count_fba,offer_count_fbm; each listed column has zero fill |

The manager task candidate also says 2 active FAIL/blocker rows were found for H_repair_out_cycle_alerts_checkli.

## Root Cause Summary
The two failures look related by timing and flow ownership, but they should be treated as separate repair tasks until worker-code evidence proves a shared cause.

Plain English summary:
- The first failure means H wrote ceiling event rows where a required ceiling value was blank.
- The second failure means H wrote listing offer snapshot market context with important market fields empty or zero-filled.
- Both are H output-quality problems, and both appeared in the same H checklist snapshot.
- They may share an upstream market-data or write-shaping issue, like two rooms losing water because one pipe is blocked.
- They may also be two separate plumbing faults: one in ceiling-event building and one in listing-offer market-context filling.
- A future repair batch should inspect the source builders for both outputs before deciding whether to apply one shared fix or two narrow fixes.

## Expected Repair Split
- Repair task 1: Find why true_binding_ceiling_gbp is blank in h_ceiling_events rows and fix the earliest H step that builds those rows.
- Repair task 2: Find why buy_box_channel, lowest_fba_price, lowest_fbm_price, offer_count_fba, and offer_count_fbm are zero-filled in listing offer snapshot context and fix the earliest H collection or merge step that should populate them.
- Merge the repair only if the same upstream input join or normalization step is proven to feed both broken outputs.

## Allowed Files For A Future Repair Batch
Future repair may inspect and edit only files directly responsible for H output construction, H checklist mapping, or H proof planning, such as:
- H worker scripts that build or write out/h_ceiling_events.csv.
- H worker scripts that build or write out/listing_offer_snapshot_latest.csv.
- H worker scripts that merge market context into listing offer snapshots.
- H-scoped schema or validation helpers used by those H outputs.
- H-scoped tests or one-off proof-planning files, if needed for isolated validation.
- The active plan package or CODING_PLAN.md for recording proof windows and monitoring rules.

Any future repair must first identify exact file paths from evidence before editing them.

## Forbidden Files And Actions
Do not do any of these inside this package or a future repair unless a separate manager-approved packet explicitly allows it:
- Do not edit worker scripts during this packaging step.
- Do not run H during this packaging step.
- Do not run A015.
- Do not change prices.
- Do not edit queues.
- Do not write Google Sheets.
- Do not change scheduler ownership.
- Do not align or edit the local database.
- Do not delete outputs.
- Do not update approved task status.
- Do not widen repair into A, B, E, F, O, or unrelated manager coverage.

## Proof Path For Future Repair
A future repair is not proved by code edits alone.

Required proof chain:
- Make the smallest source-level fix inside H-owned code.
- Run an isolated local validation for the touched builder or helper, if one exists.
- Plan a guarded H proof window before live validation.
- Use the H-owned proof path, not A015 alone.
- Confirm the H run reaches a terminal marker after the change.
- Confirm publish/finalizer truth is written after the change.
- Read the refreshed H checklist only after the H run finalizes.
- Success means both checks are no longer FAIL:
  - h_ceiling_events_required_fields_non_blank
  - h_market_context_fill_nonzero

## Retest Command
No retest command was run for this packaging task.

Future repair retest must use the manager-approved H proof path. The candidate command must be documented before execution with:

```powershell
python scripts/one_off/P002_plan_forced_proof_window.py --flow h
```

After the proof window is approved and safe, the future repair batch should run the guarded H controlled one-shot or scheduler-owned H proof specified by the generated plan. Do not use A015 alone as proof.

## Rollback Path
This package created only a new markdown planning file, so no worker rollback is needed.

Future repair rollback must include:
- Keep a copy or git diff of every edited H source file before repair.
- Restore only the files changed by the repair batch if proof fails.
- Do not delete business outputs as rollback.
- Do not hand-edit proof CSVs to hide failures.
- Re-run the same H-owned proof path after rollback if a live repair was attempted.

## Stop Condition
Stop this package after the current H active failures, repair boundaries, proof path, rollback path, and Luke-decision status are recorded.

Stop any future repair immediately if:
- The root cause points outside H scope.
- Repair would require price changes.
- Repair would require queue edits.
- Repair would require Google Sheets writes.
- Repair would require scheduler ownership changes without explicit approval.
- Repair would require local DB alignment or edits.
- H ownership is active and no safe guarded proof window exists.
- Evidence shows the two active FAIL checks do not match the package assumptions.

## Whether Luke Is Needed
Luke is not needed for this packaging task.

Luke is needed before any protected future action, including price changes, queue edits, Google Sheets writes, scheduler ownership changes, local DB alignment or edits, output deletion, or a worker run outside an approved H proof window.
