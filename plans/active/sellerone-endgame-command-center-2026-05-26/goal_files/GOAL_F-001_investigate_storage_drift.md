# Goal F-001 - Investigate F Storage Drift

Created: 2026-05-26
Status: not started
Priority: Now

## 1. Simple Version For Luke

Find out why the price-list scanner is blocked before trying to scan more products.

## 2. Why This Matters

The scanner is like a conveyor belt. It is currently stopped by a safety guard.

If we force it forward without understanding the guard, we could lose newer scanner evidence or mix old and new data.

## 3. Source Files To Inspect

- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/price_list_manager/live/storage_drift_report.csv`
- `out/housekeeping/storage_health.latest.csv`
- `project_control/EXPECTATIONS/feeder_cycle_expectations.md`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `plans/active/sellerone-endgame-command-center-2026-05-26/F_PRICE_LIST_SCANNER_TODO.md`

## 4. Hard Boundaries

- Research only.
- Do not auto-reconcile storage drift.
- Do not delete files.
- Do not overwrite F active-run files.
- Do not restart FPM130.
- Do not run scanner batches.

## 5. Technical Job Breakdown

- [ ] Confirm current FPM status.
- [ ] Inspect storage drift report.
- [ ] Identify the exact contract/file that blocks F.
- [ ] Compare CSV row count, SQL row count, and timestamps.
- [ ] Decide what evidence is needed before repair.
- [ ] Write the final summary into section 9 of this file.

## 6. Completion Expectation

The goal is complete only when:

- [ ] The blocking drift is clearly named.
- [ ] The likely source authority question is clear.
- [ ] The next goal can decide repair path without guessing.

## 7. Test And Proof Required

Proof must include:

- FPM live status
- blocking contract name
- CSV row count
- SQL row count
- timestamp comparison
- whether repair is safe, unsafe, or unknown

## 8. Delayed Result Tracking Rule

If this goal creates a fix or decision that cannot be proven immediately, do not leave the follow-up only in chat.

Before finishing, add or update a delayed result check in:

- `plans/active/sellerone-endgame-command-center-2026-05-26/RESULT_CHECK_REGISTER.md`
- spreadsheet tab `Result Checks` in `SellerOne_Endgame_Task_Board.xlsx`
- `project_control/DUE_CHECK_REGISTER.csv` if there is a real due time or trigger

A delayed check must include:

- exact trigger or due time
- artifact to inspect
- success condition
- what to do if it fails
## 9. Required Reply Instruction

Do not leave the final answer only in chat.

Before finishing, edit this file and fill in section 9.

## 10. Goal Reply - To Be Filled In By Goal Pursue

Status:

Files changed:

Files inspected:

Evidence found:

Decision made:

Tests or proof:

Remaining blocker:

Recommended next goal:

