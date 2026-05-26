# SellerOne Endgame Goals - Simple Index

Created: 2026-05-26
Purpose: simple owner-facing goal list.

## How This Works

This is the simple list for Luke.

The detailed technical instructions live in `goal_files/`.

Use one goal file at a time. Send that one file as the Goal Pursue goal. The goal file tells Codex what to inspect, what not to touch, what proof is needed, and where to write the reply.

## Important Rule

Each goal file has a section called:

`Goal Reply - To Be Filled In By Goal Pursue`

The goal runner must write its final reply into that section before the job is considered complete. Chat alone is not enough.

## Delayed Result Rule

If a fix cannot be proven until tomorrow, the next cycle, the next morning MOT, or another later trigger, the goal runner must add a delayed result check.

Use:

- spreadsheet tab: `Result Checks`
- markdown register: [RESULT_CHECK_REGISTER.md](</C:/Users/Luke/Desktop/SellerOne 2.0/plans/active/sellerone-endgame-command-center-2026-05-26/RESULT_CHECK_REGISTER.md>)
- repo due register when there is a real due time: `project_control/DUE_CHECK_REGISTER.csv`

## A To Z Work Order

We will work through the system in letter order.

Some later rows say `not created yet`. That means the job is real, but the detailed Goal Pursue MD file should be created when we reach that row.

| Order | Area | Simple meaning | Goal bot file reference | Owner |
|---:|---|---|---|---|
| 1 | A | Understand the duplicate stock receipt warning | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_A-001_classify_stock_receipt_warning.md` | Codex |
| 2 | A | Keep A as the stock and health foundation | `not created yet` | Morning MOT |
| 3 | B | Keep B owner-safe | `not created yet` | Morning MOT |
| 4 | B | Prepare B token rules for O receiving | `not created yet` | Codex |
| 5 | E | Keep E scoped proof separate | `not created yet` | Morning MOT |
| 6 | E | Confirm O uses net ROI, not gross shortcut | `not created yet` | Codex |
| 7 | F | Find why the price-list scanner is blocked | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_F-001_investigate_storage_drift.md` | Codex |
| 8 | F | Decide whether SQL or CSV is the true scanner source before any repair | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_F-002_decide_scanner_source_authority.md` | Joint |
| 9 | F | Plan Seller Central SMS 2FA path for scanner login recovery | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_F-009_plan_seller_central_sms_2fa_path.md` | Joint |
| 10 | F | Review scanner split-production rollout | `not created yet` | Codex |
| 11 | F | Confirm review handoff gates | `not created yet` | Codex |
| 12 | F | Complete profile fields for Kensington and JVC | `not created yet` | Luke |
| 13 | F | Fix Product DB destination schema gap | `not created yet` | Codex |
| 14 | F | Define token-safe handoff checks | `not created yet` | Codex |
| 15 | F | Finish dropped and discontinued handling | `not created yet` | Codex |
| 16 | G | Clean up overdue follow-up checks so nothing is hidden in chat | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_G-001_classify_due_checks.md` | Codex |
| 17 | G | Understand the storage housekeeping FAIL with 281 unclassified items | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_G-002_investigate_storage_housekeeping_fail.md` | Codex |
| 18 | G | Review controlled restart ownership | `not created yet` | Codex |
| 19 | G | Create external integration inventory | `not created yet` | Codex |
| 20 | H | Sort H repricer failures into real blockers, stale evidence, or monitor-only | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_H-001_classify_h_failures.md` | Codex |
| 21 | H | Plan how to get fresh H terminal and publish proof | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_H-002_restore_h_fresh_evidence_plan.md` | Codex |
| 22 | H | Decide whether H can be paused safely for the O price check | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_H-003_choose_h_pause_path.md` | Joint |
| 23 | H | Reduce non-blocking H noise | `not created yet` | Codex |
| 24 | O | Work out what restocking plans are old, current, or still needed | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_O-001_compare_o_plans.md` | Codex |
| 25 | O | Check if the current PO files are real working outputs or sample/test outputs | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_O-002_confirm_po_outputs.md` | Codex |
| 26 | O | Work out what is blocking the 59 restock price checks | `C:\Users\Luke\Desktop\SellerOne 2.0\plans\active\sellerone-endgame-command-center-2026-05-26\goal_files\GOAL_O-003_clear_market_refresh_blocker.md` | Joint |
| 27 | O | Lock supplier-worth fields | `not created yet` | Codex |
| 28 | O | Finish pack and quantity blocker reporting | `not created yet` | Codex |
| 29 | O | Verify decision-to-PO draft path | `not created yet` | Codex |
| 30 | O | Plan receiving and send-to-Amazon finish | `not created yet` | Codex |

## Recommended Starting Point

Start with:

`goal_files/GOAL_A-001_classify_stock_receipt_warning.md`

Reason:
- It is the first A-to-Z item.
- It is research-only.
- It does not require live scripts.
- It keeps the daily stock and health foundation clear before we move onward.
