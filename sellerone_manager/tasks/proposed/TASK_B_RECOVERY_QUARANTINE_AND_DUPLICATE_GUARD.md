# TASK B Recovery Quarantine And Duplicate Guard

Status: proposed

## Goal
Keep recovered orders separate from live order, ROI, and restocking data until manager proof and Luke approval allow the next step.

## Manager Expectation
Recovered orders must be deduped, labelled, and blocked from live use until the manager proof is clean.

## Allowed Scope
- recovery quarantine schema
- duplicate order checks
- live-merge guard checks
- proof labels
- manager MOT checks
- tests for duplicate and protected merge detection

## Forbidden Actions
- no live order merge
- no local DB alignment
- no Google Sheets write
- no output deletion
- no ROI or restocking feed
- no B run
- no B restart
- no marker edit
- no order, refund, fee, shipping, token, or price correction

## Acceptance Checks
- Duplicate order ids are flagged before merge.
- Existing live order ids in quarantine are flagged.
- Any row marked ready for live merge blocks and needs Luke.
- Only approved proof labels are accepted.
- Sellerboard bridge values are never silently treated as API truth.

## Retest Rule
Retest with the B independent MOT and confirm `b_recovery_duplicate_and_merge_guard` and `b_recovery_proof_labels` clear.

## Stop Condition
Stop and return to Luke before any action that would make recovered data affect live orders, ROI, restocking, Sheets, local DB facts, prices, or queues.
