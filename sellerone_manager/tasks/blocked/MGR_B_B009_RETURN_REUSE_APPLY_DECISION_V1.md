# B B009 Return Reuse Apply Decision v1

## Manager Authority
- task_id: MGR_B_B009_RETURN_REUSE_APPLY_DECISION_V1
- job_ref: B-B009-RETURN-REUSE-APPLY
- flow: B
- task_type: protected_token_repair_decision
- status: blocked_needs_luke
- authority: needs_luke_decision
- priority: high
- luke_action_required: 1

## Plain English
B008 now has returned-pending proof for 22 sellable-return rows. The next repair would let B009 close those returned-pending tokens and create the reusable returned-stock tokens through the normal B009 return path.

That changes local token stock, so it is protected.

## Current Evidence Summary
- B008 protected reproof applied successfully.
- B043 eligible rows: 22
- token rows updated by B043: 25
- refund event rows updated by B043: 22
- B041 now shows B009 order-aware rows: 22
- B042 now has no ready B008 rows left.
- B MOT has 0 active B failures.

## Allowed Work
- inspect B041 preview
- inspect B044 apply safety checks
- confirm B owner/lock safety before any apply
- run B044 only without approval to prove it blocks correctly
- prepare exact before/after evidence for the 22 B009 rows
- retest with B038, B041, B051, and B MOT after any approved repair

## Forbidden Work
- no B run or restart
- no B009 token reuse repair without explicit Luke approval for this repair window
- no stock recovery exception
- no allocation or COGS correction outside B009's normal returned-token path
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no live ROI/restocking use
- no Sellerboard-as-final truth

## Acceptance Proof
- Luke approves or rejects the protected B009 return-reuse repair window.
- If approved, B044 writes only the eligible local B009 returned-token proof rows.
- B044 writes a snapshot before changing files.
- B044 manifest says `applied`.
- B038, B041, B051, and B MOT are rerun after apply.
- The 22-row B009 order-aware lane clears or is reduced by the same MOT check.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before applying any B009 returned-token reuse change unless Luke approves the protected B009 repair window.

