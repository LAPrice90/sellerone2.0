# Goal G-002 - Investigate Storage Housekeeping FAIL

Created: 2026-05-26
Status: not started
Priority: Now

## 1. Simple Version For Luke

Find out what the 281 unclassified storage items are and whether they are harmless, need rules, or need cleanup.

## 2. Why This Matters

Storage rules stop the project from becoming a messy attic where important files are mixed with junk.

But cleanup must never delete live/current data.

## 3. Source Files To Inspect

- `out/housekeeping/storage_health.latest.csv`
- `out/housekeeping/storage_housekeeping_report.latest.csv`
- `out/housekeeping/storage_housekeeping_summary.latest.json`
- `project_control/AGENT_NEW_CYCLE_STORAGE_RULES.md`
- `project_control/storage_housekeeping/CODING_PLAN.md`
- `plans/active/sellerone-endgame-command-center-2026-05-26/GOVERNANCE_EXTERNAL_TODO.md`

## 4. Hard Boundaries

- Research only.
- Do not delete files.
- Do not move files.
- Do not add cleanup automation without a separate approved implementation goal.
- Do not classify live/current data as junk.

## 5. Technical Job Breakdown

- [ ] Inspect the storage health FAIL.
- [ ] Find examples of unclassified output families.
- [ ] Group them by owner flow if possible.
- [ ] Decide whether the next action is `add rule`, `cleanup old debris`, `monitor only`, or `needs deeper investigation`.
- [ ] Write the final summary into section 9 of this file.

## 6. Completion Expectation

The goal is complete only when:

- [ ] The 281 count is explained at a useful category level.
- [ ] No deletion happens.
- [ ] The next storage goal is clear and safe.

## 7. Test And Proof Required

Proof must include:

- storage health row
- example unclassified paths or families
- category counts if available
- proposed next action

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

