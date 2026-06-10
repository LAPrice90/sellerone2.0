# B Direct Sheet Token Count Check v1

## Manager Authority
- task_id: MGR_B_DIRECT_SHEET_TOKEN_COUNT_CHECK_V1
- job_ref: B-SHEET-TOKEN-COUNT-CHECK
- flow: B
- task_type: manager_read_only_proof
- status: proved
- authority: manager_approved_safe_proof
- priority: normal
- luke_action_required: 0

## Plain English
The Sheet batch costs look clean, but two direct Sheet batches have small count differences. This job checks those count differences without changing tokens.

## Current Evidence Summary
- Direct Sheet batch tokens with wrong local cost: 0.
- Count mismatches found:
  - `5Q-LUQ1-L14K`, batch `SR-20260413-009`: Sheet says 11 tokens at 29.96, local stock-receipt tokens found 10.
  - `MY-KL21-NMV5`, batch `SR-20260318-014`: Sheet says 4 tokens at 20.00, local stock-receipt tokens found 7.
- Read-only comparison output:
  - `out/systems/M/b_token_sheet_comparison/sheet_batch_token_comparison.csv`

## Allowed Work
- inspect the read-only Sheet comparison output
- inspect local stock-receipt token rows for the two named batches
- classify each mismatch as duplicate, missing, split-batch, already corrected elsewhere, or needs protected correction preview
- add manager/MOT visibility if this count check should repeat

## Forbidden Work
- no token correction
- no stock correction
- no order edit
- no B run or restart
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no ROI or restocking live use

## Acceptance Proof
- The two direct count mismatches are classified with exact evidence.
- No count mismatch is treated as a cost-pricing issue unless cost evidence changes.
- Any proposed correction is moved to a protected preview job before data is changed.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before any live token, stock, order, Sheet, DB, output, price, queue, ROI, or restocking change.

