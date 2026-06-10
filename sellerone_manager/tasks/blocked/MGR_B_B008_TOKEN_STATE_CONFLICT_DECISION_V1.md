# B B008 Token State Conflict Decision v1

## Manager Authority
- task_id: MGR_B_B008_TOKEN_STATE_CONFLICT_DECISION_V1
- job_ref: B-B008-TOKEN-STATE-CONFLICT
- flow: B
- task_type: protected_token_state_decision
- status: blocked_needs_luke
- authority: needs_luke_decision
- priority: high
- luke_action_required: 1

## Plain English
B has 1 refund-token row where the original token is visible, but it is no longer in a simple allocated or returned-pending state.

That cannot be auto-fixed. The manager must prove what happened first, then Luke only needs to decide if Codex proposes changing historical token state.

## Allowed Work
- inspect the single B042 token-state-conflict row
- inspect token ledger, allocation, refund event, and return-token ledgers
- prepare a read-only evidence summary
- keep ROI/restocking blocked from using this stock recovery

## Forbidden Work
- no B run or restart
- no token correction without explicit Luke approval
- no stock recovery exception
- no allocation or COGS correction
- no Google Sheets write
- no local DB alignment
- no output deletion
- no price or queue change
- no live ROI/restocking use
- no Sellerboard-as-final truth

## Acceptance Proof
- The row is explained in plain English.
- If correction is needed, Luke sees the exact business choice before any live data changes.
- If no correction is safe, the row remains parked and blocked from stock-recovery trust.

## Retest
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow B

## Stop Condition
Stop before any token-state change or exception that treats the row as reusable stock.

