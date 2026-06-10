# B MOT: original returned-token live-status repair needs protected decision

## Manager Authority
- task_id: MOT_B_B_ORIGINAL_RETURN_STATUS_APPLY_DECISION
- job_ref: B-ORIGINAL-TOKEN-02
- status: proved
- authority: luke_approved_protected_window
- luke_action_required: 0

## Plain English
Luke approved the protected B046 original returned-token status repair window.

B046 applied the 10 approved original returned-token status corrections after a matching B maintenance-ready handoff. The 10-row B046 batch is now proved by the same independent B MOT rows that found it.

## Manager Status Correction - 2026-06-04
- This packet is no longer a live Luke blocker.
- It remains in the history as a proved protected window.
- Any further B token-status correction needs a separate protected packet.

## What B Now Proves
- B046 manifest says `applied`.
- 10 token rows were updated.
- 9 moved from live stock status to `returned_complete`.
- 1 moved from live stock status to `unsellable`.
- 0 rows were blocked.
- B045 original-token conflict preview is now 0 rows.
- B063 original-token apply preview is now 0 rows.
- The matching maintenance request and ready markers were cleared.
- 0 rows are allowed into live ROI/restocking from this preview.
- 0 rows are allowed to use Sellerboard as final truth.
- B MOT has 0 FAIL.

## Applied Window
- request_id: `CODEX_B046_ORIGINAL_RETURN_STATUS_20260604T0655Z`
- B maintenance-ready proof matched this request.
- snapshot was written before the live token-status change.
- no B run or restart was performed.
- no Google Sheets write was performed.
- no local DB alignment was performed.
- no output deletion was performed beyond clearing the matching maintenance markers.
- no price or queue change was performed.
- no ROI/restocking use was enabled.

## What Remains Parked
- 15 Amazon return coverage proof rows.
- 5 protected disposition conflict rows.
- 4 protected return COGS residual conflict rows.
- 1 separate protected original-return status/B009 path conflict.

## What Codex Must Not Do Without Separate Approval
- run or restart B
- write Google Sheets
- align local DB facts
- delete outputs
- change prices or queues
- feed Sellerboard or weak bridge values into ROI/restocking
- widen into the remaining parked lanes

## Proof Completed
- B046 manifest says `applied`.
- Applied proof shows 10 token rows updated and 0 blocked rows.
- B045 original-token conflict preview dropped from 10 rows to 0 rows.
- B063 apply preview dropped from 10 ready rows to 0 rows.
- B051 warning workpack remains classified with 0 unclassified rows.
- B MOT has 0 FAIL and keeps remaining bridge gaps warning-labelled.

## Next Verifier
- trigger: next manager-approved packet for the remaining protected return COGS residual or Amazon coverage lanes.
- inspect: B038 bridge, B041 repair preview, B051 warning workpack, and B MOT.
- success condition: remaining rows either gain direct proof, are corrected in an approved protected window, or stay explicitly blocked from stock recovery and ROI/restocking.
