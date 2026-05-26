# Goal F-002 - Decide Scanner Source Authority

Created: 2026-05-26
Status: not started
Priority: Now

## 1. Simple Version For Luke

Decide which copy of the scanner data is the real one before repairing the scanner block.

## 2. Why This Matters

There are two versions of a scanner file: CSV and SQL.

One has fewer rows. One is newer. We must not choose by guesswork.

## 3. Source Files To Inspect

- `out/systems/F/price_list_manager/live/storage_drift_report.csv`
- the CSV path named in that report
- the SQL table named in that report
- any latest scanner completion or stage manifests connected to that contract
- `plans/active/sellerone-endgame-command-center-2026-05-26/goal_files/GOAL_F-001_investigate_storage_drift.md`

## 4. Hard Boundaries

- Research and decision only.
- Do not reconcile or write data unless Luke explicitly approves after the decision.
- Do not delete files.
- Do not restart scanner ownership.

## 5. Technical Job Breakdown

- [ ] Read the completed reply from F-001 first.
- [ ] Inspect whether SQL has newer rows that CSV does not have.
- [ ] Inspect whether CSV is a stale export or an intentionally smaller current view.
- [ ] Identify rollback path required before any future repair.
- [ ] Decide one of: `SQL authority`, `CSV authority`, `needs deeper investigation`, or `user decision needed`.
- [ ] Write the final summary into section 9 of this file.

## 6. Completion Expectation

The goal is complete only when:

- [ ] Source authority is decided or explicitly blocked.
- [ ] The future repair path is safe and reversible.
- [ ] No data is changed by this goal.

## 7. Test And Proof Required

Proof must include:

- exact row counts
- timestamps
- evidence of which side is newer or authoritative
- rollback requirement for future repair

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

