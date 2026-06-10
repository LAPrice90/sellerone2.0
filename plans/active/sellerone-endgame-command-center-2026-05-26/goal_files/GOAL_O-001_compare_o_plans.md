# Goal O-001 - Compare O Restocking Plans

Created: 2026-05-26
Status: complete
Priority: Now

## 1. Simple Version For Luke

Work out which restocking plans are still useful and which ones are old noise.

This is like sorting a messy pile of building plans into:

- keep this
- already done
- still needed
- no longer relevant

## 2. Why This Matters

Restocking is the quickest cash-facing path because it helps reorder products already in the business.

Before coding, we need one clear restocking map so we do not rebuild something that already exists or trust a plan that is out of date.

## 3. Source Files To Inspect

- `project_control/OPERATIONS_LOOP_RESTOCK_IMPLEMENTATION_PLAN_2026-04-03.md`
- `project_control/OPERATIONS_LOOP_RESTOCK_BLUEPRINT_2026-04-03.md`
- `project_control/O_REORDER_BOARD_BLUEPRINT.md`
- `project_control/O_REORDER_INPUT_RULES.md`
- `project_control/EXPECTATIONS/operations_loop_expectations.md`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`
- `plans/active/o-net-fee-restock-bridge-2026-05-19/CODING_PLAN.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/PLAN_STATUS.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/RESTOCK_OVERALL_PLAN_2026-04-28.md`
- `plans/active/sellerone-endgame-command-center-2026-05-26/O_RESTOCKING_TODO.md`

## 4. Hard Boundaries

- Planning and research only.
- Do not edit scripts.
- Do not run O scripts.
- Do not write Google Sheets.
- Do not change local DB.
- Do not mark anything complete unless the inspected files prove it.

## 5. Technical Job Breakdown

- [x] Read the source files above.
- [x] Build a phase-by-phase comparison of the April plan against the May plans.
- [x] Mark each O restocking phase as `done`, `partly done`, `still needed`, `blocked`, or `obsolete`.
- [x] Identify the next safe coding phase.
- [x] Update `O_RESTOCKING_TODO.md` only if the comparison is clear.
- [x] Write the final summary into the goal reply section of this file.

## 6. Completion Expectation

The goal is complete only when:

- [x] O restocking has one clear next phase.
- [x] Old plan items are not mixed with current work.
- [x] Any blocker is named exactly.
- [x] The next goal can be chosen without Luke needing to understand the technical files.

## 7. Test And Proof Required

No runtime test is required because this is a research goal.

Proof must include:

- files inspected
- which phases are current
- which phases are old or replaced
- exact next recommended goal

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

Completion note: the goal reply summary is filled in section 10 below.

## 10. Goal Reply - To Be Filled In By Goal Pursue

Status: complete

Files changed:
- `plans/active/sellerone-endgame-command-center-2026-05-26/O_RESTOCKING_TODO.md`
- `plans/active/sellerone-endgame-command-center-2026-05-26/goal_files/GOAL_O-001_compare_o_plans.md`
- backup snapshot created at `project_control/backups/o001_compare_o_plans_before_20260526T101004Z`

Files inspected:
- `project_control/OPERATIONS_LOOP_RESTOCK_IMPLEMENTATION_PLAN_2026-04-03.md`
- `project_control/OPERATIONS_LOOP_RESTOCK_BLUEPRINT_2026-04-03.md`
- `project_control/O_REORDER_BOARD_BLUEPRINT.md`
- `project_control/O_REORDER_INPUT_RULES.md`
- `project_control/EXPECTATIONS/operations_loop_expectations.md`
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/CODING_PLAN.md`
- `plans/active/o-net-fee-restock-bridge-2026-05-19/CODING_PLAN.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/PLAN_STATUS.md`
- `plans/active/o-restock-pack-and-db-through-use-v1/RESTOCK_OVERALL_PLAN_2026-04-28.md`
- `plans/active/sellerone-endgame-command-center-2026-05-26/O_RESTOCKING_TODO.md`
- read-only support evidence from `out/systems/O/live/*.csv`, `scripts/flows/O`, and O-related tests

Evidence found:
- April's backbone is still useful: foundation, advisor data, decision capture, UI, PO, receiving, send-to-Amazon, then cadence.
- Current O files prove partial implementation, not full operational completion.
- O source, recommendation, and profit-check outputs each have 608 rows.
- Native recommendations currently group as 608 `wait` rows, and reorder coverage has 608 rows with `action_ready_now=0`.
- Legacy Purchase List bridge has 72 rows: 51 Restock, 18 No Data, and 3 Drop.
- Market-refresh queue has 59 ready candidates waiting for native market proof.
- Current PO output has 2 draft headers and 9 lines, but the line source mix is 1 `test` and 8 `legacy_sheet`, so it is proof/bridge output rather than fully native operator-ready PO truth.
- Ordered stock has 1 sample/test row, receiving has 3 `phase4_test` events, and send-to-Amazon queue has 0 rows.
- Exact mismatch example: SKU `12-749B-9EB5` is `full_restock` in the legacy bridge using `LEGACY_PURCHASE_LIST_ROI_BACKSOLVE`, while native O says `wait` because market price, native Max pay, and net fee proof are missing and sale status is not active.

Decision made:
- Phase 0 Foundations: `done`.
- Phase 1 Restock Advisor Data: `partly done`.
- Phase 2 Human Decision Capture: `partly done`.
- Phase 3 Minimal UI: `partly done`; the April thin-UI rule remains, but the May supplier-first board blueprint is the current UI direction.
- Phase 4 Purchase Orders: `partly done`.
- Phase 5 Ordered Stock And Receiving: `partly done`.
- Phase 6 Send To Amazon Handoff: `still needed`.
- Phase 7 Runtime Cadence And Evidence: `blocked` until native price proof, supplier readiness, PO, and receiving states are safe.
- Old Google Sheets formulas, checkbox state, delete-row history, and UI-first sequencing are `obsolete` as core implementation patterns.

Tests or proof:
- No runtime test was required or run because this was a research goal.
- No O scripts were run.
- No Google Sheets writes were performed.
- No local DB changes were performed.
- Proof came from read-only markdown inspection, read-only CSV row counts, read-only local file timestamps, and read-only source/test file presence checks.

Remaining blocker:
- The next O blocker is the 59-row market-refresh proof. H owns the market/listing-offer files, so the candidate-only read-only scan cannot be run until the H-safe proof path is confirmed or parked.
- Native O parity with the legacy Sheet bridge is still pending for current buying rows.

Recommended next goal:
- `GOAL_O-003_clear_market_refresh_blocker.md`
