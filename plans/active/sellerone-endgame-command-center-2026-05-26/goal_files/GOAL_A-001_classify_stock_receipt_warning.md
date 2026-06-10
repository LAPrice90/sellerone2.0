# Goal A-001 - Classify Stock Receipt Warning

Created: 2026-05-26
Status: not started
Priority: Now

## 1. Simple Version For Luke

Understand whether the A warning about duplicate stock receipt batches is harmless or needs cleanup.

## 2. Why This Matters

Restocking needs trustworthy received-stock truth.

If stock receipts are duplicated, we must know whether the system safely ignored them or whether the source needs repair.

## 3. Source Files To Inspect

- `out/cycle_alerts/checklist_A.csv`
- `out/system_health_checklist.csv`
- `out/stock_receipt_duplicate_batches.csv`
- latest A manifest named by the warning if present
- `plans/active/sellerone-endgame-command-center-2026-05-26/A_CYCLE_TODO.md`

## 4. Hard Boundaries

- Research only.
- Do not run A015 ad hoc.
- Do not run A scripts.
- Do not edit stock receipt data.
- Do not write Google Sheets.

## 5. Technical Job Breakdown

- [ ] Inspect the A warning text.
- [ ] Inspect duplicate batch rows.
- [ ] Check whether duplicate rows are already applied safely or still dangerous.
- [ ] Classify as `harmless idempotent history`, `needs user cleanup`, or `source-data fix required`.
- [ ] Write the final summary into section 9 of this file.

## 6. Completion Expectation

The goal is complete only when:

- [ ] A warning is classified clearly.
- [ ] If user cleanup is needed, the exact rows are named.
- [ ] If no action is needed, the reason is evidence-backed.

## 7. Test And Proof Required

Proof must include:

- duplicate row count
- affected batch IDs
- status of those rows
- classification

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

Status: Complete - research only. No A015 run, no A scripts run, no stock receipt data edits, and no Google Sheets writes.

Files changed:
- `plans/active/sellerone-endgame-command-center-2026-05-26/goal_files/GOAL_A-001_classify_stock_receipt_warning.md`

Files inspected:
- `out/cycle_alerts/checklist_A.csv`
- `out/system_health_checklist.csv`
- `out/stock_receipt_duplicate_batches.csv`
- `out/manifests/A/2026-05-25/20260525T050108Z.json`
- `out/stock_receipts_latest.csv`
- `out/stock_receipt_summary.csv`
- `out/token_ledger_live.csv`
- `plans/active/sellerone-endgame-command-center-2026-05-26/A_CYCLE_TODO.md`
- `scripts/tools/process_stock_receipts_sheet.py`
- `scripts/flows/A/A015_build_system_health_check.py` read only, not run

Evidence found:
- A warning text: `a_stock_receipts_collection_health` is `warn` because `process_stock_receipts_sheet.py` was skipped by the guardrail: duplicate `batch_id` values were found in the intake sheet.
- Latest named A manifest: `20260525T050108Z.json`. The A run final state was `completed`; the stock receipt step had `rc=1`, `step_status=skipped`, and `verification_status=guardrail_blocked`.
- Duplicate row count: 2.
- Affected duplicate rows:
  - Row 77 - `SR-20260318-014`, SKU `MY-KL21-NMV5`, qty `4`, status `APPLIED`, error `idempotent_existing_order_key`, tokens_created `8`, OrderKey `571289f8-b7a9-4297-a6df-4c84e54c8c15`.
  - Row 79 - `SR-20260318-024`, SKU `8W-I703-VOFQ`, qty `12`, status `APPLIED`, error `idempotent_existing_order_key`, tokens_created `12`, OrderKey `2ec1affe-febf-4902-baa4-d3ee06ed5071`.
- Token ledger evidence exists for both order keys/SKUs:
  - `MY-KL21-NMV5` has 8 existing live tokens for the same order key: 7 under `SR-20260318-014` and 1 under `SR-20260318-025`.
  - `8W-I703-VOFQ` has 12 existing live tokens under `SR-20260318-024`: 10 available and 2 allocated.
- Local code evidence: the receipt script pre-scans all intake rows for duplicate `batch_id` values before it skips already-`APPLIED` rows. That means safe historical rows can still keep the guardrail warning active.

Decision made:
Classification: `harmless idempotent history` for received-stock truth. These two rows are not showing dangerous duplicate token creation; they are already applied and backed by existing tokens. The warning itself is still real as an operational guardrail because those historical duplicate batch IDs remain in the intake sheet and will keep the receipt step skipped until an approved follow-up records them as an accepted non-blocking exception, cleans the historical duplicate intake rows, or updates the guardrail to ignore safe `APPLIED` plus `idempotent_existing_order_key` duplicates.

Tests or proof:
- Read-only CSV and manifest inspection completed.
- Read-only token ledger check completed for both affected order keys.
- No delayed result check was added because this goal made a classification only, and the classification is proven immediately from existing artifacts.

Remaining blocker:
No blocker to classifying the A warning. The warning will remain visible until a separate approved follow-up chooses one cleanup/exception path.

Recommended next goal:
continue with GOAL_O-001_compare_o_plans
