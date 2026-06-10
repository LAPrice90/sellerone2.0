# B B008 Refund Token Reproof Apply Decision v1

## Manager Authority
- task_id: MGR_B_B008_REFUND_TOKEN_REPROOF_APPLY_DECISION_V1
- job_ref: B-B008-REPROOF-APPLY
- flow: B
- task_type: protected_token_repair_decision
- status: proved
- authority: needs_luke_decision
- priority: high
- luke_action_required: 0

## Plain English
B has 22 refunded sellable-return rows where the refund event says B008 already applied, but the live token ledger no longer shows the matching token as `returned_pending`.

That means the manager can see the likely repair route, but applying it would change local token state. That is protected.

## Current Evidence Summary
- B042 preview rows: 28
- ready B008 state-reproof rows: 22
- token-ledger gap rows: 5
- token-state conflict rows: 1
- live-write allowed rows in the preview: 0
- ROI/restocking allowed rows in the preview: 0
- Sellerboard-final-truth rows in the preview: 0

## Allowed Work
- inspect B042 preview
- inspect B043 apply safety checks
- confirm B owner/lock safety before any apply
- run B043 only without approval to prove it blocks correctly
- prepare exact before/after evidence for the 22 ready rows
- retest with B041, B038, B051, and B MOT after any approved repair

## Forbidden Work
- no B run or restart
- no token correction without explicit Luke approval for this repair window
- no stock recovery exception
- no allocation or COGS correction
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no live ROI/restocking use
- no Sellerboard-as-final truth

## Acceptance Proof
- Luke approves or rejects the protected B008 reproof window.
- If approved, B043 writes only the 22 eligible local B008/token proof rows.
- B043 writes a snapshot before changing files.
- B043 manifest says `applied`.
- B042, B041, B038, B051, and B MOT are rerun after apply.
- The 22-row returned-pending gap clears or is reduced by the same MOT check.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before applying any token-state change unless Luke approves the protected B008 reproof window.

