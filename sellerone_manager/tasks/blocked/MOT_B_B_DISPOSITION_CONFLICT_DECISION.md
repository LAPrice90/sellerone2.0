# B MOT: disposition conflict decision is superseded by original-token review

## Manager Authority
- task_id: MOT_B_B_DISPOSITION_CONFLICT_DECISION
- job_ref: B-ORIGINAL-TOKEN
- status: parked
- authority: manager_controlled_after_protected_apply
- luke_action_required: 0

## Plain English
The earlier non-sellable duplicate-token decision packet has been reduced. Luke approved the protected correction path, and B062 applied the four rows that had clean replacement-token proof.

The remaining problem is now clearer: B has 10 original returned tokens still showing as live allocated stock after return proof. That is a protected original-token lifecycle issue, not a simple duplicate-token disposition swap.

## Manager Status Correction - 2026-06-04
- This packet is no longer a live Luke blocker.
- The B062 replacement-token swap lane is proved.
- Later original-token work moved into its own protected packet and was separately proved.

## What B Now Proves
- B062 applied 4 protected replacement-token swaps.
- The 4 swaps updated token proof, allocation proof, and COGS proof together.
- B062 wrote a snapshot and manifest before replacing live local token/allocation/COGS proof.
- The old disposition correction apply preview now has 0 remaining rows.
- The old disposition conflict preview now has 0 remaining rows.
- The refund-return warning workpack is classified with 0 unclassified lanes.
- The remaining warnings are blocked from live ROI/restocking use.
- Sellerboard remains a witness only, not final truth.

## Current Remaining Lanes
- 15 Amazon return coverage proof rows:
  - These have stock-movement clues but not direct order-level Amazon customer-return proof.
- 10 protected original returned-token live-status conflict rows:
  - The original returned token is still live allocated stock after return proof.
  - 5 also have reusable duplicate-token evidence.
  - 5 do not have reusable duplicate-token evidence.

## Proof Run
- B062 manifest: applied.
- B062 applied rows: 4.
- B062 blocked rows: 0.
- B disposition conflict preview: 0 rows.
- B disposition correction apply preview: 0 rows.
- B original returned-token conflict preview: 10 rows.
- B refund-return warning workpack: 25 rows, 2 lanes, 0 unclassified rows.
- B MOT: 0 FAIL, 6 WARN.

## What Remains Parked
- No further live token correction is approved in this packet.
- Original returned-token live-status correction needs a separate protected packet before any live write.
- Amazon return coverage rows need direct proof or an approved exception before stock recovery can be trusted.
- ROI and restocking must not use these warning rows as clean stock recovery.

## Forbidden Actions
- no B run or restart
- no live token correction without a separate protected apply approval
- no downstream order correction without approval
- no return COGS correction without approval
- no Google Sheets write
- no local DB alignment
- no output deletion
- no ROI/restocking use
- no price or queue change
- no scope widening

## Next Verifier
- trigger: next manager-approved B packet for original returned-token live-status conflicts or Amazon return coverage proof.
- inspect: B045 original returned-token conflict preview, B051 warning workpack, B038 refund-return bridge, and read-only B MOT.
- success condition: remaining rows either gain direct proof, are corrected in an approved protected window, or stay explicitly labelled as blocked from stock recovery and ROI/restocking.
- remediation if it fails: keep the rows warning-labelled and do not create stock, hand-patch outputs, or use bridge evidence as live ROI truth.
