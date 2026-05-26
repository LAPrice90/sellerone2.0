# Goal G-001 - Classify Overdue Due Checks

Created: 2026-05-26
Status: not started
Priority: Now

## 1. Simple Version For Luke

Clean up old follow-up reminders so they are not just floating around forever.

## 2. Why This Matters

If follow-ups only live in old chats or stale registers, important blockers get lost.

This goal turns old reminders into clear categories.

## 3. Source Files To Inspect

- `project_control/DUE_CHECK_REGISTER.csv`
- `out/cycle_alerts/due_check_register_status.csv`
- `project_control/TASK_QUEUE.md`
- `project_control/MORNING_MOT_CHECKLIST.md`
- `plans/active/sellerone-endgame-command-center-2026-05-26/GOVERNANCE_EXTERNAL_TODO.md`

## 4. Hard Boundaries

- Research/classification only.
- Do not clear due checks unless proof is present.
- Do not edit due check status just to make the list look clean.
- Do not run cycle scripts.

## 5. Technical Job Breakdown

- [ ] List due or overdue checks.
- [ ] Classify each as `fix now`, `monitor in MOT only`, `stale evidence only`, or `needs user decision`.
- [ ] Identify any due check that blocks O or F money work.
- [ ] Update this goal file reply with the classification.
- [ ] Only update `GOVERNANCE_EXTERNAL_TODO.md` if the classification is clear.

## 6. Completion Expectation

The goal is complete only when:

- [ ] Every overdue due check has a category.
- [ ] Any money-work blocker is highlighted.
- [ ] No due check is silently erased.

## 7. Test And Proof Required

Proof must include:

- due check IDs
- due dates
- classification
- reason for each classification

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

